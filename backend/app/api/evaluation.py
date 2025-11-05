"""Evaluation template and job API endpoints."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, File, Response, status
from fastapi.responses import FileResponse, StreamingResponse

from app.api.deps import (
    get_current_user,
    get_evaluation_service,
)
from app.core.config import settings
from app.models import User, EvaluationFeedbackKind, EvaluationFeedbackStatus
from app.schemas.evaluation import (
    EvaluationTemplateResponse,
    EvaluationJobResponse,
    EvaluationReportResponse,
    EvaluationReportShareResponse,
    EvaluationFeedbackResponse,
    EvaluationFeedbackCreateRequest,
    EvaluationFeedbackUpdateRequest,
    EvaluationFeedbackExportResponse,
)
from app.services.evaluation import EvaluationService, UploadedEvaluationDataset
from app.services.errors import (
    DatasetNotFoundError,
    TrainingJobError,
    TrainingValidationError,
    WorkspaceNotFoundError,
    AccessDeniedError,
)

router = APIRouter(prefix="/v1/evaluations", tags=["evaluations"])


@router.get(
    "/templates",
    response_model=List[EvaluationTemplateResponse],
)
async def list_evaluation_templates(
    workspace_id: int = Query(..., description="工作空间 ID"),
    current_user: User = Depends(get_current_user),
    service: EvaluationService = Depends(get_evaluation_service),
) -> list[EvaluationTemplateResponse]:
    try:
        templates = service.list_templates(workspace_id=workspace_id, current_user=current_user)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [EvaluationTemplateResponse.model_validate(template) for template in templates]


@router.get(
    "/templates/{template_id}",
    response_model=EvaluationTemplateResponse,
)
async def get_evaluation_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationTemplateResponse:
    try:
        template = service.get_template(template_id, current_user=current_user)
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return EvaluationTemplateResponse.model_validate(template)


@router.post(
    "/jobs",
    response_model=EvaluationJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluation_job(
    workspace_id: int = Form(..., description="工作空间 ID"),
    evaluation_template_id: int = Form(..., description="评估模板 ID"),
    project_id: int | None = Form(None, description="项目 ID"),
    training_run_id: int | None = Form(None, description="关联训练运行 ID"),
    dataset_version_id: int | None = Form(None, description="引用的数据版本 ID"),
    dataset_file: UploadFile | None = File(
        None, description="自定义评估测试集（JSONL/CSV 等）"
    ),
    current_user: User = Depends(get_current_user),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationJobResponse:
    uploaded_dataset: UploadedEvaluationDataset | None = None
    if dataset_file is not None:
        content = await dataset_file.read()
        uploaded_dataset = UploadedEvaluationDataset(
            filename=dataset_file.filename or "evaluation-dataset.jsonl",
            content=content,
            content_type=dataset_file.content_type,
        )

    try:
        job = service.create_job(
            workspace_id=workspace_id,
            project_id=project_id,
            training_run_id=training_run_id,
            evaluation_template_id=evaluation_template_id,
            dataset_version_id=dataset_version_id,
            dataset_file=uploaded_dataset,
            current_user=current_user,
            ip_address=None,
            user_agent=None,
        )
    except (
        WorkspaceNotFoundError,
        TrainingValidationError,
        TrainingJobError,
        DatasetNotFoundError,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EvaluationJobResponse.model_validate(job)


@router.get(
    "/jobs",
    response_model=List[EvaluationJobResponse],
)
async def list_evaluation_jobs(
    workspace_id: int = Query(..., description="工作空间 ID"),
    training_run_id: int | None = Query(None, description="关联的训练运行 ID"),
    current_user: User = Depends(get_current_user),
    service: EvaluationService = Depends(get_evaluation_service),
) -> list[EvaluationJobResponse]:
    try:
        jobs = service.list_jobs(
            workspace_id=workspace_id,
            current_user=current_user,
            training_run_id=training_run_id,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [EvaluationJobResponse.model_validate(job) for job in jobs]


@router.get(
    "/jobs/{job_id}",
    response_model=EvaluationJobResponse,
)
async def get_evaluation_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationJobResponse:
    try:
        job = service.get_job(job_id, current_user=current_user)
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return EvaluationJobResponse.model_validate(job)


@router.get(
    "/reports/{job_id}",
    response_model=EvaluationReportResponse,
)
async def get_evaluation_report(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationReportResponse:
    try:
        payload = service.get_report_payload(job_id, current_user=current_user)
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return EvaluationReportResponse.model_validate(payload)


@router.post(
    "/reports/{job_id}/share",
    response_model=EvaluationReportShareResponse,
)
async def create_report_share_link(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationReportShareResponse:
    try:
        token, expires_at = service.create_share_token(job_id=job_id, current_user=current_user)
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    share_path = f"/api/v1/evaluations/reports/shared/{token}"
    return EvaluationReportShareResponse(token=token, share_path=share_path, expires_at=expires_at)


@router.get(
    "/reports/shared/{token}",
    response_model=EvaluationReportResponse,
    include_in_schema=False,
)
async def get_shared_evaluation_report(
    token: str,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationReportResponse:
    try:
        job_id = service.resolve_shared_report_token(token)
        payload = service.get_report_payload(job_id, current_user=None, from_share_link=True)
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EvaluationReportResponse.model_validate(payload)


@router.get(
    "/jobs/{job_id}/feedback",
    response_model=list[EvaluationFeedbackResponse],
)
async def list_evaluation_feedback(
    job_id: int,
    status_filter: EvaluationFeedbackStatus | None = Query(None, alias="status"),
    kind_filter: EvaluationFeedbackKind | None = Query(None, alias="kind"),
    tag: str | None = Query(None, description="按标签过滤"),
    current_user: User = Depends(get_current_user),
    service: EvaluationService = Depends(get_evaluation_service),
) -> list[EvaluationFeedbackResponse]:
    try:
        entries = service.list_feedback(
            job_id,
            current_user=current_user,
            status=status_filter,
            kind=kind_filter,
            tag=tag,
        )
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return [EvaluationFeedbackResponse.model_validate(entry) for entry in entries]


@router.post(
    "/jobs/{job_id}/feedback",
    response_model=EvaluationFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluation_feedback(
    job_id: int,
    payload: EvaluationFeedbackCreateRequest,
    current_user: User = Depends(get_current_user),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationFeedbackResponse:
    try:
        entry = service.create_feedback(
            job_id,
            workspace_id=payload.workspace_id,
            current_user=current_user,
            kind=payload.kind,
            body=payload.body,
            tags=payload.tags,
            status=payload.status,
            training_run_id=payload.training_run_id,
            metric_name=payload.metric_name,
            metric_value=payload.metric_value,
            ip_address=None,
            user_agent=None,
        )
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return EvaluationFeedbackResponse.model_validate(entry)


@router.patch(
    "/jobs/{job_id}/feedback/{feedback_id}",
    response_model=EvaluationFeedbackResponse,
)
async def update_evaluation_feedback(
    job_id: int,
    feedback_id: int,
    payload: EvaluationFeedbackUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationFeedbackResponse:
    try:
        entry = service.update_feedback(
            job_id=job_id,
            feedback_id=feedback_id,
            current_user=current_user,
            body=payload.body,
            status=payload.status,
            tags=payload.tags,
            metric_name=payload.metric_name,
            metric_value=payload.metric_value,
            ip_address=None,
            user_agent=None,
        )
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return EvaluationFeedbackResponse.model_validate(entry)


@router.delete(
    "/jobs/{job_id}/feedback/{feedback_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_evaluation_feedback(
    job_id: int,
    feedback_id: int,
    current_user: User = Depends(get_current_user),
    service: EvaluationService = Depends(get_evaluation_service),
) -> Response:
    try:
        service.delete_feedback(
            job_id=job_id,
            feedback_id=feedback_id,
            current_user=current_user,
            ip_address=None,
            user_agent=None,
        )
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/jobs/{job_id}/feedback:export",
    response_model=EvaluationFeedbackExportResponse,
)
async def export_evaluation_feedback(
    job_id: int,
    format: str = Query("markdown", description="导出格式：markdown 或 json"),
    status_filter: EvaluationFeedbackStatus | None = Query(None, alias="status"),
    kind_filter: EvaluationFeedbackKind | None = Query(None, alias="kind"),
    tag: str | None = Query(None, description="按标签过滤"),
    current_user: User = Depends(get_current_user),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationFeedbackExportResponse:
    try:
        payload = service.export_feedback(
            job_id=job_id,
            current_user=current_user,
            fmt=format,
            status=status_filter,
            kind=kind_filter,
            tag=tag,
        )
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return EvaluationFeedbackExportResponse.model_validate(payload)


@router.get(
    "/jobs/{job_id}/export",
    response_class=FileResponse,
)
async def export_evaluation_job(
    job_id: int,
    format: str = Query("markdown", description="导出格式：markdown、json 或 pdf"),
    current_user: User = Depends(get_current_user),
    service: EvaluationService = Depends(get_evaluation_service),
) -> Response:
    try:
        job = service.get_job(job_id, current_user=current_user)
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    storage_root = Path(settings.workspace_storage_root).expanduser()
    artifact_root = storage_root / (job.artifact_path or "")

    if format.lower() == "json":
        candidate = artifact_root / "results.json"
        if not candidate.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估结果文件不存在")
        service.record_report_export(job=job, fmt="json", user=current_user)
        return FileResponse(candidate, filename=candidate.name, media_type="application/json")

    if format.lower() == "pdf":
        payload = service.get_report_payload(job.id, current_user=current_user)
        pdf_bytes = service.generate_pdf_report(job, payload)
        buffer = BytesIO(pdf_bytes)
        headers = {"Content-Disposition": f"attachment; filename=evaluation-report-{job.id}.pdf"}
        service.record_report_export(job=job, fmt="pdf", user=current_user)
        return StreamingResponse(buffer, media_type="application/pdf", headers=headers)

    report_path = job.report_path
    if not report_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="评估任务尚未生成报告")
    candidate = storage_root / report_path
    if not candidate.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估报告文件不存在")
    service.record_report_export(job=job, fmt="markdown", user=current_user)
    return FileResponse(candidate, filename=candidate.name, media_type="text/markdown")
