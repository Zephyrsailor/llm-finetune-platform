"""Minimal gRPC bridge for the inference service.

该模块提供一个 lightweight gRPC server，避免强制依赖代码生成工具。
"""

from __future__ import annotations

from concurrent import futures
from contextlib import contextmanager
from typing import Callable, Iterable

import grpc
from google.protobuf import json_format, struct_pb2
from sqlmodel import Session

from app.core.database import engine
from app.services.inference import InferenceService, InferenceActor
from app.services.errors import AccessDeniedError, ModelRegistryError, RateLimitExceeded, WorkspaceNotFoundError


MetadataPairs = Iterable[tuple[str, str]]


@contextmanager
def _session_scope() -> Iterable[Session]:
    with Session(engine) as session:
        yield session


def _metadata_to_dict(metadata: MetadataPairs) -> dict[str, str]:
    return {key.lower(): value for key, value in metadata}


class InferenceGrpcHandler:
    """Adapter that exposes :class:`InferenceService` over gRPC."""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self._session_factory = session_factory or (lambda: Session(engine))

    def invoke(self, request: struct_pb2.Struct, context: grpc.ServicerContext) -> struct_pb2.Struct:
        payload = json_format.MessageToDict(request, preserving_proto_field_name=True)
        if "workspace_id" not in payload:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "缺少 workspace_id")
        workspace_id = int(payload.get("workspace_id"))
        deployment_id = payload.get("deployment_id")
        model_version_id = payload.get("model_version_id")
        inputs = payload.get("inputs", [])
        parameters = payload.get("parameters", {})
        if not deployment_id and not model_version_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "必须提供 deployment_id 或 model_version_id")
        if not inputs:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "inputs 不能为空")

        metadata = _metadata_to_dict(context.invocation_metadata())
        with self._session_factory() as session:
            service = InferenceService(session)
            api_key_value = metadata.get("x-llmft-api-key")
            if api_key_value:
                api_key = service.authenticate_api_key(api_key_value)
                if api_key is None or not api_key.is_active:
                    context.abort(grpc.StatusCode.UNAUTHENTICATED, "API Key 无效或已停用")
                actor = InferenceActor(user=None, api_key_id=api_key.id)
            else:
                context.abort(grpc.StatusCode.UNAUTHENTICATED, "缺少 X-LLMFT-API-Key 元数据")

            try:
                result = service.invoke_inference(
                    workspace_id=workspace_id,
                    deployment_id=int(deployment_id) if deployment_id is not None else None,
                    model_version_id=int(model_version_id) if model_version_id is not None else None,
                    inputs=[str(item) for item in inputs],
                    parameters=parameters,
                    actor=actor,
                )
            except WorkspaceNotFoundError as exc:
                context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
            except AccessDeniedError as exc:
                context.abort(grpc.StatusCode.PERMISSION_DENIED, str(exc))
            except (ModelRegistryError, ValueError) as exc:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
            except RateLimitExceeded as exc:
                context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, str(exc))

        response = struct_pb2.Struct()
        response.update(
            {
                "call_id": result["call_id"],
                "deployment_id": result["deployment_id"],
                "model_version_id": result["model_version_id"],
                "latency_ms": result["latency_ms"],
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "outputs": result["outputs"],
            }
        )
        return response


def add_inference_service(server: grpc.Server, handler: InferenceGrpcHandler) -> None:
    method = grpc.unary_unary_rpc_method_handler(
        handler.invoke,
        request_deserializer=struct_pb2.Struct.FromString,
        response_serializer=struct_pb2.Struct.SerializeToString,
    )
    generic_handler = grpc.method_handlers_generic_handler(
        "llmft.inference.Inference",
        {"Invoke": method},
    )
    server.add_generic_rpc_handlers((generic_handler,))


def serve(address: str = "[::]:50051") -> grpc.Server:
    """Start a standalone gRPC server bound to *address*."""

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    add_inference_service(server, InferenceGrpcHandler())
    server.add_insecure_port(address)
    server.start()
    return server


__all__ = ["InferenceGrpcHandler", "add_inference_service", "serve"]
