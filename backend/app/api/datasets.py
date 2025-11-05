"""Dataset ingestion API endpoints."""

from __future__ import annotations

import json
from typing import Any, Sequence

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import get_current_user, get_data_hub_service
from app.models import DatasetFormatType, DatasetSourceType, User
from app.schemas.datasets import (
    CleaningAssignmentResponse,
    CleaningSummaryResponse,
    CleaningTemplateResponse,
    DataCleaningJobResponse,
    DatasetFormatVersionResponse,
    DatasetResponse,
    DatasetVersionCreateResponse,
    DatasetVersionResponse,
    QualityEvaluationJobResponse,
    QualitySummaryResponse,
)
from app.services.data_hub import (
    CleaningTemplatePayload,
    DataHubService,
    DatasetCreatePayload,
)
from app.services.errors import (
    DatasetConflictError,
    DatasetNotFoundError,
    DatasetSizeExceededError,
    DatasetVersionError,
    WorkspaceNotFoundError,
)

router = APIRouter(prefix="/v1/datasets", tags=["datasets"])


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


@router.get("", response_model=list[DatasetResponse])
async def list_datasets(
    workspace_id: int = Query(..., description="工作空间 ID"),
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
) -> list[DatasetResponse]:
    try:
        datasets: Sequence = service.list_datasets(
            workspace_id=workspace_id,
            current_user=current_user,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return [DatasetResponse.model_validate(dataset) for dataset in datasets]


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    workspace_id: int = Form(..., description="目标工作空间 ID"),
    name: str = Form(..., description="数据集名称"),
    description: str | None = Form(None, description="数据集描述"),
    data_type: str | None = Form(None, description="数据类型（例如 conversation/jsonl 等）"),
    tags: str | None = Form(None, description="标签集合，逗号分隔或 JSON 数组"),
    notes: str | None = Form(None, description="补充备注"),
    source_type: DatasetSourceType = Form(DatasetSourceType.UPLOAD, description="数据来源类型"),
    source_uri: str | None = Form(None, description="对象存储路径或外部链接"),
    reference_dataset_id: int | None = Form(None, description="引用已有数据集 ID"),
    upload_file: UploadFile | None = File(None, description="上传文件（当 source_type=upload 时必填）"),
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
) -> DatasetResponse:
    """Create dataset via upload, external URI, or existing dataset reference."""
    try:
        dataset = service.create_dataset(
            payload=DatasetCreatePayload(
                workspace_id=workspace_id,
                name=name,
                description=description,
                data_type=data_type,
                tags=_parse_tags(tags),
                notes=notes,
                source_type=source_type,
                source_uri=source_uri,
                reference_dataset_id=reference_dataset_id,
                upload_file=upload_file,
            ),
            current_user=current_user,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DatasetConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DatasetSizeExceededError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except (DatasetNotFoundError, DatasetVersionError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return DatasetResponse.model_validate(dataset)


class DatasetVersionCreateRequest(BaseModel):
    """Incoming payload when creating dataset versions."""

    notes: str | None = None
    template_id: int | None = None


class DatasetFormatRunRequest(BaseModel):
    """Payload for triggering format conversion."""

    formats: list[DatasetFormatType] | None = None


class CleaningTemplateCreateRequest(BaseModel):
    """Payload for creating cleaning templates."""

    workspace_id: int
    name: str
    description: str | None = None
    steps: list[dict[str, Any]]
    is_active: bool = True


class CleaningTemplateUpdateRequest(BaseModel):
    """Payload for updating cleaning templates."""

    name: str | None = None
    description: str | None = None
    steps: list[dict[str, Any]] | None = None
    is_active: bool | None = None


class CleaningAssignmentRequest(BaseModel):
    """Payload to assign a template to dataset."""

    template_id: int | None = None
    enabled: bool = True


@router.post(
    "/{dataset_id}/versions",
    response_model=DatasetVersionCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset_version(
    dataset_id: int,
    payload: DatasetVersionCreateRequest = Body(default_factory=DatasetVersionCreateRequest),
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
) -> DatasetVersionCreateResponse:
    """Create a dataset version entry and schedule cleaning task."""
    try:
        version, job, quality_job = service.create_dataset_version(
            dataset_id=dataset_id,
            current_user=current_user,
            notes=payload.notes,
            template_id=payload.template_id,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (DatasetVersionError, WorkspaceNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    response_payload = DatasetVersionCreateResponse(
        version=DatasetVersionResponse.model_validate(version),
        job=DataCleaningJobResponse.model_validate(job),
        quality_job=QualityEvaluationJobResponse.model_validate(quality_job) if quality_job else None,
    )
    return response_payload


@router.get(
    "/{dataset_id}/versions",
    response_model=list[DatasetVersionResponse],
)
async def list_dataset_versions(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
) -> list[DatasetVersionResponse]:
    try:
        versions: Sequence = service.list_dataset_versions(
            dataset_id=dataset_id,
            current_user=current_user,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return [DatasetVersionResponse.model_validate(version) for version in versions]


@router.post(
    "/cleaning/templates",
    response_model=CleaningTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_cleaning_template(
    payload: CleaningTemplateCreateRequest,
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
) -> CleaningTemplateResponse:
    try:
        template = service.create_cleaning_template(
            payload=CleaningTemplatePayload(
                workspace_id=payload.workspace_id,
                name=payload.name,
                description=payload.description,
                steps=payload.steps,
                is_active=payload.is_active,
            ),
            current_user=current_user,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DatasetVersionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return CleaningTemplateResponse.model_validate(template)


@router.get("/cleaning/templates", response_model=list[CleaningTemplateResponse])
async def list_cleaning_templates(
    workspace_id: int = Query(..., description="工作空间 ID"),
    active_only: bool = Query(False, description="仅返回启用模板"),
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
) -> list[CleaningTemplateResponse]:
    try:
        templates: Sequence = service.list_cleaning_templates(
            workspace_id=workspace_id,
            current_user=current_user,
            active_only=active_only,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return [CleaningTemplateResponse.model_validate(template) for template in templates]


@router.patch(
    "/cleaning/templates/{template_id}",
    response_model=CleaningTemplateResponse,
)
async def update_cleaning_template(
    template_id: int,
    payload: CleaningTemplateUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
) -> CleaningTemplateResponse:
    try:
        template = service.update_cleaning_template(
            template_id=template_id,
            current_user=current_user,
            name=payload.name,
            description=payload.description,
            steps=payload.steps,
            is_active=payload.is_active,
        )
    except DatasetVersionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return CleaningTemplateResponse.model_validate(template)


@router.post(
    "/{dataset_id}/cleaning/assignment",
    response_model=CleaningAssignmentResponse | None,
)
async def assign_cleaning_template(
    dataset_id: int,
    payload: CleaningAssignmentRequest,
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
) -> CleaningAssignmentResponse | None:
    try:
        assignment = service.assign_cleaning_template(
            dataset_id=dataset_id,
            template_id=payload.template_id,
            enabled=payload.enabled,
            current_user=current_user,
        )
    except (DatasetNotFoundError, DatasetVersionError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if assignment is None:
        return None
    return CleaningAssignmentResponse.model_validate(assignment)


@router.get(
    "/{dataset_id}/cleaning/assignment",
    response_model=CleaningAssignmentResponse | None,
)
async def get_cleaning_assignment(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
) -> CleaningAssignmentResponse | None:
    try:
        assignment = service.get_cleaning_assignment(
            dataset_id=dataset_id,
            current_user=current_user,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if assignment is None:
        return None
    return CleaningAssignmentResponse.model_validate(assignment)


@router.get(
    "/{dataset_id}/versions/{version_id}/cleaning/summary",
    response_model=CleaningSummaryResponse,
)
async def get_cleaning_summary(
    dataset_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
) -> CleaningSummaryResponse:
    try:
        summary = service.get_cleaning_summary(
            dataset_version_id=version_id,
            current_user=current_user,
        )
    except (DatasetNotFoundError, DatasetVersionError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if summary.get("dataset_id") != dataset_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集版本不匹配")

    return CleaningSummaryResponse.model_validate(summary)


@router.get(
    "/{dataset_id}/versions/{version_id}/cleaning/export",
    response_class=FileResponse,
)
async def download_cleaning_export(
    dataset_id: int,
    version_id: int,
    fmt: str = Query("jsonl", pattern="^(jsonl|csv)$", description="导出格式"),
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
):
    try:
        summary = service.get_cleaning_summary(
            dataset_version_id=version_id,
            current_user=current_user,
        )
    except (DatasetNotFoundError, DatasetVersionError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if summary.get("dataset_id") != dataset_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集版本不匹配")

    try:
        file_path, mime = service.get_cleaning_export(
            dataset_version_id=version_id,
            fmt=fmt,
            current_user=current_user,
        )
    except DatasetVersionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    filename = file_path.name
    return FileResponse(path=file_path, media_type=mime, filename=filename)


@router.post(
    "/{dataset_id}/versions/{version_id}/quality/run",
    response_model=QualityEvaluationJobResponse,
)
async def trigger_quality_evaluation(
    dataset_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
) -> QualityEvaluationJobResponse:
    try:
        job = service.run_quality_evaluation(
            dataset_version_id=version_id,
            current_user=current_user,
        )
    except (DatasetNotFoundError, DatasetVersionError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return QualityEvaluationJobResponse.model_validate(job)


@router.get(
    "/{dataset_id}/versions/{version_id}/quality/summary",
    response_model=QualitySummaryResponse,
)
async def get_quality_summary(
    dataset_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
) -> QualitySummaryResponse:
    try:
        summary = service.get_quality_summary(
            dataset_version_id=version_id,
            current_user=current_user,
        )
    except (DatasetNotFoundError, DatasetVersionError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if summary.get("dataset_id") != dataset_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集版本不匹配")

    return QualitySummaryResponse.model_validate(summary)


@router.get(
    "/{dataset_id}/versions/{version_id}/quality/export",
    response_class=FileResponse,
)
async def download_quality_export(
    dataset_id: int,
    version_id: int,
    fmt: str = Query("json", pattern="^(json|csv)$", description="导出格式"),
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
):
    try:
        summary = service.get_quality_summary(
            dataset_version_id=version_id,
            current_user=current_user,
        )
    except (DatasetNotFoundError, DatasetVersionError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if summary.get("dataset_id") != dataset_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集版本不匹配")

    try:
        file_path, mime = service.get_quality_export(
            dataset_version_id=version_id,
            fmt=fmt,
            current_user=current_user,
        )
    except DatasetVersionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    filename = file_path.name
    return FileResponse(path=file_path, media_type=mime, filename=filename)


@router.post(
    "/{dataset_id}/versions/{version_id}/formats/run",
    response_model=list[DatasetFormatVersionResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_format_conversion(
    dataset_id: int,
    version_id: int,
    payload: DatasetFormatRunRequest | None = Body(None),
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
) -> list[DatasetFormatVersionResponse]:
    format_values: list[str] | None = None
    if payload and payload.formats:
        format_values = [fmt.value for fmt in payload.formats]

    try:
        records = service.run_format_conversion(
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            formats=format_values,
            current_user=current_user,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DatasetVersionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return [DatasetFormatVersionResponse.model_validate(record) for record in records]


@router.get(
    "/{dataset_id}/versions/{version_id}/formats",
    response_model=list[DatasetFormatVersionResponse],
)
async def list_format_versions(
    dataset_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
) -> list[DatasetFormatVersionResponse]:
    try:
        records = service.list_format_versions(
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            current_user=current_user,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DatasetVersionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return [DatasetFormatVersionResponse.model_validate(record) for record in records]


@router.post(
    "/{dataset_id}/versions/{version_id}/formats/{format_id}/activate",
    response_model=DatasetFormatVersionResponse,
)
async def activate_format_version(
    dataset_id: int,
    version_id: int,
    format_id: int,
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
) -> DatasetFormatVersionResponse:
    try:
        record = service.set_active_format(
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            format_id=format_id,
            current_user=current_user,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DatasetVersionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return DatasetFormatVersionResponse.model_validate(record)


@router.get(
    "/{dataset_id}/versions/{version_id}/formats/export",
    response_class=FileResponse,
)
async def download_format_export(
    dataset_id: int,
    version_id: int,
    fmt: DatasetFormatType = Query(..., description="需要导出的目标格式"),
    current_user: User = Depends(get_current_user),
    service: DataHubService = Depends(get_data_hub_service),
):
    try:
        file_path, mime = service.get_format_export(
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            format_value=fmt.value,
            current_user=current_user,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DatasetVersionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    filename = file_path.name
    return FileResponse(path=file_path, media_type=mime, filename=filename)
