"""Training experiment metadata aggregation, comparison, and export service."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sqlmodel import Session, select

from app.core.config import settings
from app.models import (
    Dataset,
    DatasetVersion,
    TrainingAlert,
    TrainingAlertRule,
    TrainingJob,
    TrainingRun,
    TrainingSnapshot,
    TrainingTemplate,
    Workspace,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.dataset import DatasetRepository, DatasetVersionRepository
from app.repositories.training import (
    TrainingAlertRepository,
    TrainingAlertRuleRepository,
    TrainingJobRepository,
    TrainingMetricRepository,
    TrainingRunRepository,
    TrainingSnapshotRepository,
    TrainingTemplateRepository,
)
from app.repositories.workspace import WorkspaceRepository
from app.services.errors import (
    TrainingExperimentError,
    TrainingJobError,
    WorkspaceNotFoundError,
)
from app.services.permissions import PermissionService
from app.services.roles import RoleOperation


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


class TrainingExperimentService:
    """Coordinates training experiment metadata recording, comparison, and export."""

    def __init__(self, session: Session):
        self._session = session
        self._workspaces = WorkspaceRepository(session)
        self._jobs = TrainingJobRepository(session)
        self._runs = TrainingRunRepository(session)
        self._metrics = TrainingMetricRepository(session)
        self._snapshots = TrainingSnapshotRepository(session)
        self._alerts = TrainingAlertRepository(session)
        self._alert_rules = TrainingAlertRuleRepository(session)
        self._datasets = DatasetRepository(session)
        self._versions = DatasetVersionRepository(session)
        self._templates = TrainingTemplateRepository(session)
        self._audits = AuditLogRepository(session)
        self._permissions = PermissionService(session)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def list_runs(
        self,
        *,
        workspace_id: int,
        current_user,
        job_id: int | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return recent training runs with metadata for a workspace."""
        workspace = self._ensure_workspace(workspace_id)
        self._require_permission(workspace.id, current_user)

        statement = (
            select(TrainingRun, TrainingJob)
            .join(TrainingJob, TrainingRun.job_id == TrainingJob.id)
            .where(TrainingJob.workspace_id == workspace.id)
            .order_by(TrainingRun.started_at.desc())
        )
        if job_id is not None:
            statement = statement.where(TrainingRun.job_id == job_id)
        if limit:
            statement = statement.limit(limit)

        rows = self._session.exec(statement).all()
        runs: list[dict[str, Any]] = []
        for run, job in rows:
            metadata = run.metadata_json or self._build_run_metadata(run, job)
            runs.append(self._serialize_run_summary(run, job, metadata))
        return runs

    def get_run_detail(
        self,
        run_id: int,
        *,
        current_user,
    ) -> dict[str, Any]:
        """Return full metadata for a specific training run."""
        run, job = self._load_run_with_job(run_id)
        self._require_permission(job.workspace_id, current_user)
        metadata = run.metadata_json or self._build_run_metadata(run, job)
        return self._serialize_run_detail(run, job, metadata)

    def compare_runs(
        self,
        run_a_id: int,
        run_b_id: int,
        *,
        current_user,
    ) -> dict[str, Any]:
        """Compare two runs and return configuration/metric differences."""
        run_a, job_a = self._load_run_with_job(run_a_id)
        run_b, job_b = self._load_run_with_job(run_b_id)

        if job_a.workspace_id != job_b.workspace_id:
            raise TrainingExperimentError("只能比较同一工作空间下的训练运行。")

        self._require_permission(job_a.workspace_id, current_user)

        metadata_a = run_a.metadata_json or self._build_run_metadata(run_a, job_a)
        metadata_b = run_b.metadata_json or self._build_run_metadata(run_b, job_b)

        diff = {
            "parameters": self._diff_dicts(metadata_a.get("parameters", {}), metadata_b.get("parameters", {})),
            "final_metrics": self._diff_dicts(
                metadata_a.get("metrics", {}).get("final", {}),
                metadata_b.get("metrics", {}).get("final", {}),
                numeric_delta=True,
            ),
            "resource": self._diff_dicts(metadata_a.get("resource", {}), metadata_b.get("resource", {}), numeric_delta=True),
            "dataset": self._diff_dicts(metadata_a.get("dataset", {}), metadata_b.get("dataset", {})),
        }

        comparison = {
            "run_a": self._serialize_run_summary(run_a, job_a, metadata_a),
            "run_b": self._serialize_run_summary(run_b, job_b, metadata_b),
            "diff": diff,
            "snapshots": {
                "run_a": metadata_a.get("snapshots", []),
                "run_b": metadata_b.get("snapshots", []),
            },
            "alerts": {
                "run_a": metadata_a.get("alerts", []),
                "run_b": metadata_b.get("alerts", []),
            },
        }
        return comparison

    def export_runs(
        self,
        run_ids: Iterable[int],
        *,
        workspace_id: int,
        export_format: str,
        current_user,
    ) -> dict[str, Any]:
        """Export run metadata (and optional comparison) to file."""
        export_format = export_format.lower()
        if export_format not in {"json", "csv", "markdown"}:
            raise TrainingExperimentError("导出格式仅支持 json/csv/markdown。")

        workspace = self._ensure_workspace(workspace_id)
        self._require_permission(workspace.id, current_user)

        run_ids = list(dict.fromkeys(run_ids))
        if not run_ids:
            raise TrainingExperimentError("请至少提供一个训练运行 ID。")

        runs = [self.get_run_detail(run_id, current_user=current_user) for run_id in run_ids]
        for run in runs:
            if run["workspace_id"] != workspace.id:
                raise TrainingExperimentError("运行不属于指定的工作空间。")
        comparison = None
        if len(run_ids) == 2:
            comparison = self.compare_runs(run_ids[0], run_ids[1], current_user=current_user)

        export_dir = (
            Path(settings.workspace_storage_root)
            .expanduser()
            .joinpath("training", str(workspace.id), "experiments", "exports")
        )
        export_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        filename = f"experiments-{timestamp}.{export_format if export_format != 'markdown' else 'md'}"
        export_path = export_dir / filename

        if export_format == "json":
            payload = {
                "workspace_id": workspace.id,
                "generated_at": _isoformat(datetime.utcnow()),
                "runs": runs,
            }
            if comparison:
                payload["comparison"] = comparison
            export_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        elif export_format == "csv":
            self._write_csv_export(export_path, runs)
        else:
            self._write_markdown_export(export_path, workspace, runs, comparison)

        self._audits.record(
            event_type="training.experiment.exported",
            user_id=getattr(current_user, "id", None),
            ip_address=None,
            user_agent=None,
            payload={
                "workspace_id": workspace.id,
                "run_ids": run_ids,
                "format": export_format,
                "path": str(export_path),
            },
        )

        return {
            "workspace_id": workspace.id,
            "format": export_format,
            "path": str(export_path),
            "generated_at": _isoformat(datetime.utcnow()),
            "size_bytes": export_path.stat().st_size,
        }

    def refresh_run_metadata(self, run_id: int) -> dict[str, Any]:
        """Rebuild metadata for a run and persist it."""
        run, job = self._load_run_with_job(run_id)
        metadata = self._build_run_metadata(run, job)
        return metadata

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _ensure_workspace(self, workspace_id: int) -> Workspace:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("工作空间不存在")
        return workspace

    def _require_permission(self, workspace_id: int, current_user) -> None:
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=current_user,
            operation=RoleOperation.TRAINING_LAUNCH,
            ip_address=None,
            user_agent=None,
        )

    def _load_run_with_job(self, run_id: int) -> tuple[TrainingRun, TrainingJob]:
        run = self._runs.get(run_id)
        if run is None:
            raise TrainingExperimentError("训练运行不存在")
        job = self._jobs.get(run.job_id)
        if job is None:
            raise TrainingJobError("关联的训练任务不存在")
        return run, job

    def _build_run_metadata(self, run: TrainingRun, job: TrainingJob) -> dict[str, Any]:
        dataset_version = self._versions.get(job.dataset_version_id)
        dataset = self._datasets.get(dataset_version.dataset_id) if dataset_version else None
        template = self._templates.get(job.training_template_id) if job.training_template_id else None

        metrics_summary = dict(run.metrics_json or {})
        metric_samples = self._metrics.list_for_run(run.id)
        metrics_history = self._serialize_metric_history(metric_samples)

        snapshots = [self._serialize_snapshot(snapshot) for snapshot in self._snapshots.list_for_run(run.id)]
        alerts = [self._serialize_alert(alert) for alert in self._alerts.list_for_run(run.id)]

        duration_seconds = None
        if run.finished_at:
            duration_seconds = max(int((run.finished_at - run.started_at).total_seconds()), 0)

        cost_estimate = None
        if duration_seconds is not None:
            hours = duration_seconds / 3600
            cost_estimate = round(hours * job.requested_gpus * 2.5, 2)

        metadata = {
            "workspace_id": job.workspace_id,
            "job_id": job.id,
            "run_id": run.id,
            "status": run.status.value,
            "started_at": _isoformat(run.started_at),
            "finished_at": _isoformat(run.finished_at),
            "base_model": job.base_model,
            "adapter_type": job.adapter_type.value,
            "parameters": dict(job.params_json or {}),
            "dataset": self._serialize_dataset(dataset, dataset_version),
            "template": self._serialize_template(template),
            "resource": {
                "requested_gpus": job.requested_gpus,
                "queue": job.queue_name,
                "duration_seconds": duration_seconds,
                "cost_estimate_usd": cost_estimate,
            },
            "metrics": {
                "final": metrics_summary,
                "history": metrics_history,
            },
            "artifact_uri": run.artifact_uri,
            "exit_code": run.exit_code,
            "snapshots": snapshots,
            "alerts": alerts,
        }

        already_recorded = run.metadata_json is not None
        self._runs.update(run, metadata_json=metadata)
        if not already_recorded:
            self._audits.record(
                event_type="training.experiment.recorded",
                user_id=None,
                ip_address=None,
                user_agent=None,
                payload={
                    "workspace_id": job.workspace_id,
                    "job_id": job.id,
                    "run_id": run.id,
                    "dataset_version_id": job.dataset_version_id,
                    "training_template_id": job.training_template_id,
                    "status": run.status.value,
                },
            )
        return metadata

    def _serialize_dataset(
        self,
        dataset: Dataset | None,
        version: DatasetVersion | None,
    ) -> dict[str, Any]:
        if dataset is None or version is None:
            return {}
        return {
            "dataset_id": dataset.id,
            "dataset_name": dataset.name,
            "dataset_version_id": version.id,
            "version": version.version,
            "source_type": dataset.source_type.value,
            "stats": dict(version.stats_json or {}),
            "created_at": _isoformat(version.created_at),
        }

    def _serialize_template(self, template: TrainingTemplate | None) -> dict[str, Any] | None:
        if template is None:
            return None
        return {
            "template_id": template.id,
            "name": template.name,
            "description": template.description,
            "is_builtin": template.is_builtin,
        }

    def _serialize_metric_history(self, samples: Iterable) -> dict[str, list[dict[str, Any]]]:
        history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for sample in samples:
            history[sample.metric.value].append(
                {
                    "value": sample.value,
                    "recorded_at": _isoformat(sample.recorded_at),
                }
            )
        # limit to latest 20 samples per metric to avoid oversized payloads
        for metric, points in history.items():
            history[metric] = points[-20:]
        return dict(history)

    def _serialize_snapshot(self, snapshot: TrainingSnapshot) -> dict[str, Any]:
        return {
            "snapshot_id": snapshot.id,
            "trigger_type": snapshot.trigger_type.value,
            "path": snapshot.path,
            "metrics": dict(snapshot.metrics_json or {}),
            "created_at": _isoformat(snapshot.created_at),
            "step": snapshot.step,
            "epoch": snapshot.epoch,
        }

    def _serialize_alert(self, alert: TrainingAlert) -> dict[str, Any]:
        rule: TrainingAlertRule | None = self._alert_rules.get(alert.rule_id)
        return {
            "alert_id": alert.id,
            "rule_id": alert.rule_id,
            "rule_name": rule.name if rule else None,
            "metric": rule.metric.value if rule else None,
            "value": alert.value,
            "status": alert.status.value,
            "triggered_at": _isoformat(alert.triggered_at),
            "acknowledged_at": _isoformat(alert.acknowledged_at),
            "resolved_at": _isoformat(alert.resolved_at),
            "notes": alert.notes,
        }

    def _serialize_run_summary(
        self,
        run: TrainingRun,
        job: TrainingJob,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "run_id": run.id,
            "job_id": job.id,
            "workspace_id": job.workspace_id,
            "status": run.status.value,
            "started_at": _isoformat(run.started_at),
            "finished_at": _isoformat(run.finished_at),
            "base_model": job.base_model,
            "adapter_type": job.adapter_type.value,
            "dataset": metadata.get("dataset", {}),
            "metrics": metadata.get("metrics", {}).get("final", {}),
            "resource": metadata.get("resource", {}),
        }

    def _serialize_run_detail(
        self,
        run: TrainingRun,
        job: TrainingJob,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        detail = self._serialize_run_summary(run, job, metadata)
        detail["metadata"] = metadata
        detail["artifact_uri"] = run.artifact_uri
        detail["exit_code"] = run.exit_code
        return detail

    @staticmethod
    def _diff_dicts(
        left: dict[str, Any],
        right: dict[str, Any],
        *,
        numeric_delta: bool = False,
    ) -> list[dict[str, Any]]:
        diff: list[dict[str, Any]] = []
        keys = sorted({*left.keys(), *right.keys()})
        for key in keys:
            left_value = left.get(key)
            right_value = right.get(key)
            if left_value == right_value:
                continue
            entry: dict[str, Any] = {
                "key": key,
                "left": left_value,
                "right": right_value,
            }
            if numeric_delta:
                try:
                    entry["delta"] = (
                        float(right_value) - float(left_value) if left_value is not None and right_value is not None else None
                    )
                except (TypeError, ValueError):
                    entry["delta"] = None
            diff.append(entry)
        return diff

    @staticmethod
    def _write_csv_export(path: Path, runs: list[dict[str, Any]]) -> None:
        fieldnames = [
            "run_id",
            "job_id",
            "workspace_id",
            "status",
            "started_at",
            "finished_at",
            "base_model",
            "adapter_type",
            "dataset_version_id",
            "dataset_name",
            "duration_seconds",
            "cost_estimate_usd",
        ]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for run in runs:
                metadata = run.get("metadata", {})
                dataset = metadata.get("dataset", {})
                resource = metadata.get("resource", {})
                writer.writerow(
                    {
                        "run_id": run["run_id"],
                        "job_id": run["job_id"],
                        "workspace_id": run["workspace_id"],
                        "status": run["status"],
                        "started_at": run["started_at"],
                        "finished_at": run["finished_at"],
                        "base_model": run["base_model"],
                        "adapter_type": run["adapter_type"],
                        "dataset_version_id": dataset.get("dataset_version_id"),
                        "dataset_name": dataset.get("dataset_name"),
                        "duration_seconds": resource.get("duration_seconds"),
                        "cost_estimate_usd": resource.get("cost_estimate_usd"),
                    }
                )

    @staticmethod
    def _write_markdown_export(
        path: Path,
        workspace: Workspace,
        runs: list[dict[str, Any]],
        comparison: dict[str, Any] | None,
    ) -> None:
        lines = [
            f"# 训练实验导出（工作空间 {workspace.name}）",
            "",
            f"- 导出时间：{_isoformat(datetime.utcnow())}",
            f"- 工作空间 ID：{workspace.id}",
            "",
        ]
        for run in runs:
            metadata = run.get("metadata", {})
            dataset = metadata.get("dataset", {})
            resource = metadata.get("resource", {})
            lines.extend(
                [
                    f"## 运行 {run['run_id']}（作业 {run['job_id']}）",
                    f"- 模型：{run['base_model']}（{run['adapter_type']}）",
                    f"- 数据集：{dataset.get('dataset_name')} v{dataset.get('version')} (ID {dataset.get('dataset_version_id')})",
                    f"- 时长/成本：{resource.get('duration_seconds')} 秒 / 估算 ${resource.get('cost_estimate_usd')}",
                    f"- 状态：{run['status']}，起止 {run['started_at'] or '-'} → {run['finished_at'] or '-'}",
                    "",
                    "### 关键指标",
                ]
            )
            metrics = metadata.get("metrics", {}).get("final", {})
            if metrics:
                for key, value in metrics.items():
                    lines.append(f"- {key}: {value}")
            else:
                lines.append("- 无可用指标")
            lines.append("")
        if comparison:
            lines.append("## 对比差异")
            for section, entries in comparison["diff"].items():
                lines.append(f"### {section}")
                if not entries:
                    lines.append("- 无差异")
                else:
                    for entry in entries:
                        delta = entry.get("delta")
                        delta_text = f"（Δ {delta:+.4f}）" if delta is not None else ""
                        lines.append(f"- {entry['key']}: {entry['left']} → {entry['right']}{delta_text}")
                lines.append("")
        path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
