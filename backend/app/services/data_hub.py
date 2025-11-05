"""DataHub domain service handling dataset ingestion and cleaning workflow."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Sequence
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile
from sqlmodel import Session

from app.core.config import settings
from app.models import (
    DataCleaningJob,
    DataCleaningJobStatus,
    Dataset,
    DatasetCleaningAssignment,
    DatasetCleaningTemplate,
    CleaningStepType,
    DatasetSourceType,
    DatasetStatus,
    DatasetVersion,
    DatasetVersionStatus,
    QualityEvaluationJob,
    QualityEvaluationStatus,
    DatasetFormatVersion,
    DatasetFormatType,
    DatasetFormatStatus,
    User,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.cleaning import (
    DatasetCleaningAssignmentRepository,
    DatasetCleaningTemplateRepository,
)
from app.repositories.dataset import (
    DataCleaningJobRepository,
    DatasetRepository,
    DatasetVersionRepository,
)
from app.repositories.format import DatasetFormatVersionRepository
from app.repositories.quality import QualityEvaluationJobRepository
from app.repositories.workspace import WorkspaceRepository
from app.services.errors import (
    DatasetConflictError,
    DatasetNotFoundError,
    DatasetSizeExceededError,
    DatasetVersionError,
    WorkspaceNotFoundError,
)
from app.services.permissions import PermissionService
from app.services.roles import RoleOperation
from app.tasks.data_cleaning import (
    run_initial_cleaning,
    run_quality_evaluation,
    run_format_standardization,
)


DEFAULT_FORMATS: tuple[DatasetFormatType, ...] = (
    DatasetFormatType.JSONL,
    DatasetFormatType.SFT,
    DatasetFormatType.PARQUET,
)


@dataclass(slots=True)
class DatasetCreatePayload:
    """DTO representing dataset creation metadata."""

    workspace_id: int
    name: str
    description: str | None
    data_type: str | None
    tags: list[str]
    notes: str | None
    source_type: DatasetSourceType
    source_uri: str | None
    reference_dataset_id: int | None
    upload_file: UploadFile | None


@dataclass(slots=True)
class CleaningTemplatePayload:
    """DTO for cleaning template definition."""

    workspace_id: int
    name: str
    description: str | None
    steps: list[dict]
    is_active: bool = True


class DataHubService:
    """Provide dataset ingestion, versioning, and cleaning orchestration."""

    def __init__(self, session: Session):
        self._session = session
        self._datasets = DatasetRepository(session)
        self._versions = DatasetVersionRepository(session)
        self._jobs = DataCleaningJobRepository(session)
        self._templates = DatasetCleaningTemplateRepository(session)
        self._assignments = DatasetCleaningAssignmentRepository(session)
        self._quality_jobs = QualityEvaluationJobRepository(session)
        self._formats = DatasetFormatVersionRepository(session)
        self._workspaces = WorkspaceRepository(session)
        self._audits = AuditLogRepository(session)
        self._permissions = PermissionService(session)

    @contextmanager
    def _transaction(self):
        if self._session.in_transaction():
            with self._session.begin_nested():
                yield
        else:
            with self._session.begin():
                yield

    # ------------------------------------------------------------------ #
    # Dataset management
    # ------------------------------------------------------------------ #

    def create_dataset(self, *, payload: DatasetCreatePayload, current_user: User) -> Dataset:
        """Create a dataset entry and persist uploaded artefacts if necessary."""
        workspace = self._workspaces.get(payload.workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("工作空间不存在")

        self._permissions.require_operation(
            workspace_id=payload.workspace_id,
            user=current_user,
            operation=RoleOperation.DATA_IMPORT,
            ip_address=None,
            user_agent=None,
        )

        existing = self._datasets.get_by_name(
            workspace_id=payload.workspace_id,
            name=payload.name,
        )
        if existing is not None:
            raise DatasetConflictError("同名数据集已存在")

        reference_dataset: Dataset | None = None
        if payload.source_type == DatasetSourceType.REFERENCE:
            if payload.reference_dataset_id is None:
                raise DatasetNotFoundError("必须指定引用的数据集 ID")
            reference_dataset = self._datasets.get(payload.reference_dataset_id)
            if reference_dataset is None or reference_dataset.workspace_id != payload.workspace_id:
                raise DatasetNotFoundError("引用的数据集不存在或不属于当前工作空间")

        if payload.source_type == DatasetSourceType.UPLOAD and payload.upload_file is None:
            raise DatasetVersionError("上传模式需要提供文件")
        if payload.source_type == DatasetSourceType.EXTERNAL and not payload.source_uri:
            raise DatasetVersionError("外部模式需要提供对象存储地址")

        dataset = Dataset(
            workspace_id=payload.workspace_id,
            name=payload.name,
            description=payload.description,
            source_type=payload.source_type,
            source_uri=payload.source_uri,
            data_type=payload.data_type,
            tags=payload.tags,
            notes=payload.notes,
            reference_dataset_id=payload.reference_dataset_id,
            created_by=current_user.id,
        )

        with self._transaction():
            dataset = self._datasets.create(dataset)

            if payload.source_type == DatasetSourceType.UPLOAD and payload.upload_file is not None:
                (
                    storage_path,
                    file_size,
                    checksum,
                    mime_type,
                ) = self._store_upload_file(
                    dataset=dataset,
                    upload_file=payload.upload_file,
                )
                dataset.storage_path = storage_path
                dataset.file_size_bytes = file_size
                dataset.checksum_sha256 = checksum
                dataset.mime_type = mime_type
                dataset.updated_at = datetime.utcnow()
                self._session.add(dataset)
                self._session.flush()
            elif payload.source_type == DatasetSourceType.REFERENCE and reference_dataset is not None:
                dataset.storage_path = reference_dataset.storage_path
                dataset.file_size_bytes = reference_dataset.file_size_bytes
                dataset.checksum_sha256 = reference_dataset.checksum_sha256
                dataset.mime_type = reference_dataset.mime_type
                dataset.source_uri = reference_dataset.source_uri or dataset.source_uri
                dataset.updated_at = datetime.utcnow()
                self._session.add(dataset)
                self._session.flush()

        self._audits.record(
            event_type="dataset.created",
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "dataset_id": dataset.id,
                "workspace_id": dataset.workspace_id,
                "source_type": dataset.source_type.value,
            },
        )

        return dataset

    # ------------------------------------------------------------------ #
    # Dataset version management
    # ------------------------------------------------------------------ #

    def create_dataset_version(
        self,
        *,
        dataset_id: int,
        current_user: User,
        notes: str | None = None,
        template_id: int | None = None,
    ) -> tuple[DatasetVersion, DataCleaningJob]:
        """Create a dataset version entry and schedule cleaning job."""
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            raise DatasetNotFoundError("数据集不存在")

        self._permissions.require_operation(
            workspace_id=dataset.workspace_id,
            user=current_user,
            operation=RoleOperation.DATA_IMPORT,
            ip_address=None,
            user_agent=None,
        )

        assignment = self._assignments.get(dataset.id)
        selected_template: DatasetCleaningTemplate | None = None
        if template_id is not None:
            candidate = self._templates.get(template_id)
            if candidate is None or candidate.workspace_id != dataset.workspace_id:
                raise DatasetVersionError("清洗模板不存在或不属于当前工作空间")
            if not candidate.is_active:
                raise DatasetVersionError("清洗模板已停用，无法使用")
            selected_template = candidate
        elif assignment and assignment.enabled:
            candidate = self._templates.get(assignment.template_id)
            if candidate is not None and candidate.is_active:
                selected_template = candidate

        latest_version = self._versions.get_latest_version_number(dataset_id)
        next_version = (latest_version or 0) + 1

        version_root, location_uri = self._prepare_version_directory(dataset, next_version)

        version = DatasetVersion(
            dataset_id=dataset.id,
            version=next_version,
            status=DatasetVersionStatus.PENDING,
            location_uri=location_uri,
            created_by=current_user.id,
        )

        job = DataCleaningJob(
            dataset_version_id=0,  # placeholder until version persisted
            status=DataCleaningJobStatus.PENDING,
            template_id=selected_template.id if selected_template else None,
            template_snapshot=(
                {
                    "id": selected_template.id,
                    "name": selected_template.name,
                    "version": selected_template.version,
                    "steps": selected_template.steps,
                }
                if selected_template
                else None
            ),
        )
        quality_job = QualityEvaluationJob(
            dataset_version_id=0,
            status=QualityEvaluationStatus.PENDING,
        )

        with self._transaction():
            version = self._versions.create(version)
            job.dataset_version_id = version.id
            job = self._jobs.create(job)
            quality_job.dataset_version_id = version.id
            quality_job = self._quality_jobs.create(quality_job)

            logs_path = version_root / "logs" / f"job-{job.id}.log"
            logs_path.parent.mkdir(parents=True, exist_ok=True)
            job.logs_path = str(logs_path.relative_to(self._storage_root()))
            self._session.add(job)
            self._session.flush()

            quality_logs = version_root / "quality" / f"job-{quality_job.id}.log"
            quality_logs.parent.mkdir(parents=True, exist_ok=True)
            quality_job.logs_path = str(quality_logs.relative_to(self._storage_root()))
            self._session.add(quality_job)
            self._session.flush()

        # Run Celery task (synchronous when task_always_eager is enabled)
        run_initial_cleaning.delay(job.id, notes or "")

        self._audits.record(
            event_type="dataset.version.created",
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "dataset_id": dataset.id,
                "version_id": version.id,
                "version": version.version,
                "template_id": job.template_id,
                "quality_job_id": quality_job.id,
            },
        )

        return version, job, quality_job

    # ------------------------------------------------------------------ #
    # Cleaning template management
    # ------------------------------------------------------------------ #

    def create_cleaning_template(
        self,
        *,
        payload: CleaningTemplatePayload,
        current_user: User,
    ) -> DatasetCleaningTemplate:
        workspace = self._workspaces.get(payload.workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("工作空间不存在")

        self._permissions.require_operation(
            workspace_id=payload.workspace_id,
            user=current_user,
            operation=RoleOperation.APPROVAL_MANAGE,
            ip_address=None,
            user_agent=None,
        )

        validated_steps = self._validate_cleaning_steps(payload.steps)

        with self._transaction():
            template = self._templates.create(
                workspace_id=payload.workspace_id,
                name=payload.name,
                description=payload.description,
                steps=validated_steps,
                is_active=payload.is_active,
            )

        self._audits.record(
            event_type="dataset.cleaning.template.created",
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "workspace_id": payload.workspace_id,
                "template_id": template.id,
            },
        )
        return template

    def list_cleaning_templates(
        self,
        *,
        workspace_id: int,
        current_user: User,
        active_only: bool = False,
    ) -> Sequence[DatasetCleaningTemplate]:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("工作空间不存在")

        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=current_user,
            operation=RoleOperation.DATA_IMPORT,
            ip_address=None,
            user_agent=None,
        )

        return self._templates.list_by_workspace(workspace_id, active_only=active_only)

    def list_datasets(
        self,
        *,
        workspace_id: int,
        current_user: User,
    ) -> Sequence[Dataset]:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("工作空间不存在")

        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=current_user,
            operation=RoleOperation.DATA_IMPORT,
            ip_address=None,
            user_agent=None,
        )

        return self._datasets.list_for_workspace(workspace_id)

    def list_dataset_versions(
        self,
        *,
        dataset_id: int,
        current_user: User,
    ) -> Sequence[DatasetVersion]:
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            raise DatasetNotFoundError("数据集不存在")

        self._permissions.require_operation(
            workspace_id=dataset.workspace_id,
            user=current_user,
            operation=RoleOperation.DATA_IMPORT,
            ip_address=None,
            user_agent=None,
        )

        return self._versions.list_for_dataset(dataset_id)

    def update_cleaning_template(
        self,
        *,
        template_id: int,
        current_user: User,
        name: str | None = None,
        description: str | None = None,
        steps: list[dict] | None = None,
        is_active: bool | None = None,
    ) -> DatasetCleaningTemplate:
        template = self._templates.get(template_id)
        if template is None:
            raise DatasetVersionError("清洗模板不存在")

        self._permissions.require_operation(
            workspace_id=template.workspace_id,
            user=current_user,
            operation=RoleOperation.APPROVAL_MANAGE,
            ip_address=None,
            user_agent=None,
        )

        validated_steps = None
        if steps is not None:
            validated_steps = self._validate_cleaning_steps(steps)

        with self._transaction():
            updated = self._templates.update(
                template,
                name=name,
                description=description,
                steps=validated_steps,
                is_active=is_active,
            )

        self._audits.record(
            event_type="dataset.cleaning.template.updated",
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "template_id": updated.id,
                "workspace_id": updated.workspace_id,
            },
        )
        return updated

    def assign_cleaning_template(
        self,
        *,
        dataset_id: int,
        template_id: int | None,
        enabled: bool,
        current_user: User,
    ) -> DatasetCleaningAssignment | None:
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            raise DatasetNotFoundError("数据集不存在")

        self._permissions.require_operation(
            workspace_id=dataset.workspace_id,
            user=current_user,
            operation=RoleOperation.DATA_IMPORT,
            ip_address=None,
            user_agent=None,
        )

        assignment: DatasetCleaningAssignment | None
        with self._transaction():
            if template_id is None or not enabled:
                self._assignments.disable(dataset_id)
                assignment = None
            else:
                template = self._templates.get(template_id)
                if template is None or template.workspace_id != dataset.workspace_id:
                    raise DatasetVersionError("清洗模板不存在或不属于该工作空间")
                assignment = self._assignments.upsert(
                    dataset_id=dataset_id,
                    template_id=template.id,
                    enabled=True,
                )

        self._audits.record(
            event_type="dataset.cleaning.template.assigned",
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "dataset_id": dataset_id,
                "template_id": template_id,
                "enabled": enabled,
            },
        )
        return assignment

    def get_cleaning_assignment(
        self,
        *,
        dataset_id: int,
        current_user: User,
    ) -> DatasetCleaningAssignment | None:
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            raise DatasetNotFoundError("数据集不存在")

        self._permissions.require_operation(
            workspace_id=dataset.workspace_id,
            user=current_user,
            operation=RoleOperation.DATA_IMPORT,
            ip_address=None,
            user_agent=None,
        )

        assignment = self._assignments.get(dataset_id)
        return assignment

    # ------------------------------------------------------------------ #
    # Cleaning results
    # ------------------------------------------------------------------ #

    def get_cleaning_summary(
        self,
        *,
        dataset_version_id: int,
        current_user: User,
    ) -> dict:
        version = self._versions.get(dataset_version_id)
        if version is None:
            raise DatasetVersionError("数据集版本不存在")

        dataset = self._datasets.get(version.dataset_id)
        if dataset is None:
            raise DatasetNotFoundError("数据集不存在")

        self._permissions.require_operation(
            workspace_id=dataset.workspace_id,
            user=current_user,
            operation=RoleOperation.DATA_IMPORT,
            ip_address=None,
            user_agent=None,
        )

        job = self._jobs.get_by_version(version.id)
        return {
            "dataset_id": dataset.id,
            "dataset_version_id": version.id,
            "status": (job.status.value if job else None),
            "stats": version.stats_json or {},
            "template": job.template_snapshot if job else None,
            "logs_path": job.logs_path if job else None,
            "summary_path": job.summary_path if job else None,
            "export_manifest": job.export_manifest if job else None,
        }

    def get_cleaning_export(
        self,
        *,
        dataset_version_id: int,
        fmt: str,
        current_user: User,
    ) -> tuple[Path, str]:
        summary = self.get_cleaning_summary(dataset_version_id=dataset_version_id, current_user=current_user)
        manifest = summary.get("export_manifest") or {}
        relative_path = manifest.get(fmt)
        if relative_path is None:
            raise DatasetVersionError("未找到指定格式的导出文件")

        root = self._storage_root()
        file_path = root / relative_path
        if not file_path.exists():
            raise DatasetVersionError("导出文件尚未生成或已被清理")

        mime = "text/csv" if fmt == "csv" else "application/json"

        self._audits.record(
            event_type="dataset.cleaning.export",
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "dataset_version_id": dataset_version_id,
                "format": fmt,
                "path": relative_path,
            },
        )

        return file_path, mime

    # ------------------------------------------------------------------ #
    # Quality evaluation management
    # ------------------------------------------------------------------ #

    def run_quality_evaluation(
        self,
        *,
        dataset_version_id: int,
        current_user: User,
    ) -> QualityEvaluationJob:
        version = self._versions.get(dataset_version_id)
        if version is None:
            raise DatasetVersionError("数据集版本不存在")
        dataset = self._datasets.get(version.dataset_id)
        if dataset is None:
            raise DatasetNotFoundError("数据集不存在")

        self._permissions.require_operation(
            workspace_id=dataset.workspace_id,
            user=current_user,
            operation=RoleOperation.DATA_IMPORT,
            ip_address=None,
            user_agent=None,
        )

        job = self._quality_jobs.get_by_version(version.id)
        if job is None:
            with self._transaction():
                job = QualityEvaluationJob(dataset_version_id=version.id)
                job = self._quality_jobs.create(job)

        if job.logs_path is None:
            quality_dir = self._quality_dir(version)
            quality_dir.mkdir(parents=True, exist_ok=True)
            logs_path = quality_dir / f"job-{job.id}.log"
            job.logs_path = str(logs_path.relative_to(self._storage_root()))
            self._session.add(job)
            self._session.flush()
        run_quality_evaluation.delay(job.id)
        return job

    def get_quality_summary(
        self,
        *,
        dataset_version_id: int,
        current_user: User,
    ) -> dict:
        version = self._versions.get(dataset_version_id)
        if version is None:
            raise DatasetVersionError("数据集版本不存在")

        dataset = self._datasets.get(version.dataset_id)
        if dataset is None:
            raise DatasetNotFoundError("数据集不存在")

        self._permissions.require_operation(
            workspace_id=dataset.workspace_id,
            user=current_user,
            operation=RoleOperation.DATA_IMPORT,
            ip_address=None,
            user_agent=None,
        )

        job = self._quality_jobs.get_by_version(version.id)
        return {
            "dataset_id": dataset.id,
            "dataset_version_id": version.id,
            "status": (job.status.value if job else None),
            "stats": (version.stats_json or {}).get("quality", {}),
            "summary_path": version.quality_summary_path,
            "report_manifest": version.quality_report_manifest,
            "logs_path": job.logs_path if job else None,
        }

    def get_quality_export(
        self,
        *,
        dataset_version_id: int,
        fmt: str,
        current_user: User,
    ) -> tuple[Path, str]:
        summary = self.get_quality_summary(
            dataset_version_id=dataset_version_id,
            current_user=current_user,
        )
        manifest = summary.get("report_manifest") or {}
        relative_path = manifest.get(fmt)
        if relative_path is None:
            raise DatasetVersionError("未找到指定格式的评估报告")

        root = self._storage_root()
        file_path = root / relative_path
        if not file_path.exists():
            raise DatasetVersionError("评估报告尚未生成或已被清理")

        mime = "text/csv" if fmt == "csv" else "application/json"

        dataset = self._datasets.get(summary["dataset_id"])
        version = self._versions.get(dataset_version_id)
        self._audits.record(
            event_type="dataset.quality.export",
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "dataset_id": dataset.id if dataset else None,
                "dataset_version_id": dataset_version_id,
                "format": fmt,
                "path": relative_path,
            },
        )

        return file_path, mime

    # ------------------------------------------------------------------ #
    # Helper utilities
    # ------------------------------------------------------------------ #

    def _quality_dir(self, version: DatasetVersion) -> Path:
        root = self._storage_root()
        location = version.location_uri or ""
        return root / location / "quality"

    def _format_dir(self, version: DatasetVersion, fmt: DatasetFormatType) -> Path:
        root = self._storage_root()
        location = version.location_uri or ""
        return root / location / "standard" / fmt.value

    # ------------------------------------------------------------------ #
    # Format standardisation management
    # ------------------------------------------------------------------ #

    def run_format_conversion(
        self,
        *,
        dataset_id: int,
        dataset_version_id: int,
        formats: Sequence[str] | None,
        current_user: User,
    ) -> list[DatasetFormatVersion]:
        version = self._versions.get(dataset_version_id)
        if version is None:
            raise DatasetVersionError("数据集版本不存在")

        dataset = self._datasets.get(version.dataset_id)
        if dataset is None:
            raise DatasetNotFoundError("数据集不存在")
        if dataset.id != dataset_id:
            raise DatasetVersionError("数据集与版本不匹配")

        if version.quality_summary_path is None:
            raise DatasetVersionError("请先完成质量评估后再进行格式转换")

        self._permissions.require_operation(
            workspace_id=dataset.workspace_id,
            user=current_user,
            operation=RoleOperation.DATA_IMPORT,
            ip_address=None,
            user_agent=None,
        )

        requested_formats: list[DatasetFormatType] = []
        if formats:
            for format_str in formats:
                try:
                    requested_formats.append(DatasetFormatType(format_str))
                except ValueError as exc:
                    raise DatasetVersionError("不支持的格式类型") from exc
        else:
            requested_formats = list(DEFAULT_FORMATS)

        record_ids: list[int] = []
        with self._transaction():
            for fmt in requested_formats:
                record = self._formats.create(
                    dataset_version_id=version.id,
                    format=fmt,
                )
                log_path = self._ensure_format_log_file(version, record.id)
                record.logs_path = log_path
                self._session.add(record)
                self._session.flush()
                record_ids.append(record.id)

        records: list[DatasetFormatVersion] = []
        for record_id in record_ids:
            run_format_standardization.delay(record_id)
            record = self._formats.get(record_id)
            if record is not None:
                records.append(record)

        self._audits.record(
            event_type="dataset.format.run",
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "dataset_version_id": dataset_version_id,
                "formats": [fmt.value for fmt in requested_formats],
            },
        )

        return records

    def list_format_versions(
        self,
        *,
        dataset_id: int,
        dataset_version_id: int,
        current_user: User,
    ) -> list[DatasetFormatVersion]:
        version = self._versions.get(dataset_version_id)
        if version is None:
            raise DatasetVersionError("数据集版本不存在")
        dataset = self._datasets.get(version.dataset_id)
        if dataset is None:
            raise DatasetNotFoundError("数据集不存在")
        if dataset.id != dataset_id:
            raise DatasetVersionError("数据集与版本不匹配")

        self._permissions.require_operation(
            workspace_id=dataset.workspace_id,
            user=current_user,
            operation=RoleOperation.DATA_IMPORT,
            ip_address=None,
            user_agent=None,
        )

        return list(self._formats.list_for_version(version.id))

    def set_active_format(
        self,
        *,
        dataset_id: int,
        dataset_version_id: int,
        format_id: int,
        current_user: User,
    ) -> DatasetFormatVersion:
        record = self._formats.get(format_id)
        if record is None:
            raise DatasetVersionError("格式记录不存在")

        version = self._versions.get(record.dataset_version_id)
        if version is None:
            raise DatasetVersionError("数据集版本不存在")
        if version.id != dataset_version_id:
            raise DatasetVersionError("格式记录与数据集版本不匹配")
        dataset = self._datasets.get(version.dataset_id)
        if dataset is None:
            raise DatasetNotFoundError("数据集不存在")
        if dataset.id != dataset_id:
            raise DatasetVersionError("数据集与版本不匹配")

        self._permissions.require_operation(
            workspace_id=dataset.workspace_id,
            user=current_user,
            operation=RoleOperation.DATA_IMPORT,
            ip_address=None,
            user_agent=None,
        )

        updated = self._formats.set_active(format_id)
        self._audits.record(
            event_type="dataset.format.rollback",
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "dataset_version_id": version.id,
                "format": updated.format.value,
                "format_id": updated.id,
            },
        )
        return updated

    def get_format_export(
        self,
        *,
        dataset_id: int,
        dataset_version_id: int,
        format_value: str,
        current_user: User,
    ) -> tuple[Path, str]:
        version = self._versions.get(dataset_version_id)
        if version is None:
            raise DatasetVersionError("数据集版本不存在")
        dataset = self._datasets.get(version.dataset_id)
        if dataset is None:
            raise DatasetNotFoundError("数据集不存在")
        if dataset.id != dataset_id:
            raise DatasetVersionError("数据集与版本不匹配")

        self._permissions.require_operation(
            workspace_id=dataset.workspace_id,
            user=current_user,
            operation=RoleOperation.DATA_IMPORT,
            ip_address=None,
            user_agent=None,
        )

        try:
            fmt = DatasetFormatType(format_value)
        except ValueError as exc:
            raise DatasetVersionError("不支持的格式类型") from exc

        records = self._formats.list_for_version(version.id)
        active = next((record for record in records if record.format == fmt and record.is_active), None)
        if active is None:
            active = next((record for record in records if record.format == fmt and record.status == DatasetFormatStatus.COMPLETED), None)
        if active is None or not active.path:
            raise DatasetVersionError("指定格式尚未生成")

        root = self._storage_root()
        file_path = root / active.path
        if not file_path.exists():
            raise DatasetVersionError("格式文件已被删除或尚未生成")

        mime = {
            DatasetFormatType.JSONL: "application/json",
            DatasetFormatType.SFT: "application/json",
            DatasetFormatType.PARQUET: "application/octet-stream",
        }[fmt]

        self._audits.record(
            event_type="dataset.format.export",
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "dataset_version_id": version.id,
                "format": fmt.value,
                "path": active.path,
            },
        )

        return file_path, mime

    # ------------------------------------------------------------------ #
    # Helper utilities
    # ------------------------------------------------------------------ #

    def _storage_root(self) -> Path:
        return Path(settings.workspace_storage_root).expanduser()

    def _dataset_root(self, dataset: Dataset) -> Path:
        return self._storage_root() / "workspaces" / str(dataset.workspace_id) / "datasets" / str(dataset.id)

    def _version_root(self, version: DatasetVersion) -> Path:
        location = version.location_uri
        if not location:
            raise DatasetVersionError("数据集版本缺少存储目录")
        root = self._storage_root() / location
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _ensure_format_log_file(self, version: DatasetVersion, record_id: int) -> str:
        version_root = self._version_root(version)
        logs_dir = version_root / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / f"format-{record_id}.log"
        if not log_file.exists():
            log_file.touch()
        return str(log_file.relative_to(self._storage_root()))

    def _store_upload_file(self, *, dataset: Dataset, upload_file: UploadFile) -> tuple[str, int, str, str | None]:
        """Persist uploaded file to workspace storage and return metadata."""
        chunk_size = settings.dataset_upload_chunk_size
        max_bytes = settings.max_dataset_size_bytes

        dataset_root = self._dataset_root(dataset)
        raw_dir = dataset_root / "v0" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        filename = upload_file.filename or f"dataset-{dataset.id}"
        target_path = raw_dir / filename

        hasher = hashlib.sha256()
        written = 0

        upload_file.file.seek(0)
        with target_path.open("wb") as buffer:
            while True:
                chunk = upload_file.file.read(chunk_size)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    upload_file.file.close()
                    buffer.close()
                    target_path.unlink(missing_ok=True)
                    raise DatasetSizeExceededError("上传的数据集超出允许大小")
                buffer.write(chunk)
                hasher.update(chunk)

        relative_path = str(target_path.relative_to(self._storage_root()))
        checksum = hasher.hexdigest()
        mime_type = upload_file.content_type
        upload_file.file.seek(0, 0)
        upload_file.file.close()

        return relative_path, written, checksum, mime_type

    def _prepare_version_directory(self, dataset: Dataset, version_number: int) -> tuple[Path, str]:
        """Create directory tree for a dataset version and copy raw artefacts if available."""
        dataset_root = self._dataset_root(dataset)
        version_root = dataset_root / f"v{version_number}"
        raw_dir = version_root / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        if dataset.storage_path:
            source_path = self._storage_root() / dataset.storage_path
            if source_path.exists():
                target_path = raw_dir / source_path.name
                if not target_path.exists():
                    shutil.copy2(source_path, target_path)

        return version_root, str(version_root.relative_to(self._storage_root()))

    def _validate_cleaning_steps(self, steps: list[dict]) -> list[dict]:
        """Ensure provided cleaning steps are well-formed."""
        validated: list[dict] = []
        for index, step in enumerate(steps or []):
            if not isinstance(step, dict):
                raise DatasetVersionError(f"清洗步骤 {index} 格式无效")
            step_type = step.get("type")
            if step_type not in {item.value for item in CleaningStepType}:
                raise DatasetVersionError(f"清洗步骤 {index} 使用了未支持的类型: {step_type}")
            validated.append(step)
        return validated
