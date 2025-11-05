"""Training snapshot management service."""

from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from sqlmodel import Session, select

from app.core.celery_app import celery_app
from app.core.config import settings
from app.models import (
    TrainingJob,
    TrainingJobStatus,
    TrainingRun,
    TrainingSnapshot,
    TrainingSnapshotTriggerType,
    TrainingAlertStatus,
    User,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.training import (
    TrainingAlertRepository,
    TrainingEventRepository,
    TrainingJobRepository,
    TrainingRunRepository,
    TrainingSnapshotRepository,
)
from app.services.errors import TrainingSnapshotError
from app.services.permissions import PermissionService
from app.services.roles import RoleOperation


class TrainingSnapshotService:
    """Coordinates snapshot creation, listing, resume, and rollback."""

    def __init__(self, session: Session):
        self._session = session
        self._snapshots = TrainingSnapshotRepository(session)
        self._runs = TrainingRunRepository(session)
        self._jobs = TrainingJobRepository(session)
        self._events = TrainingEventRepository(session)
        self._alerts = TrainingAlertRepository(session)
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
    # Snapshot creation and listing
    # ------------------------------------------------------------------ #

    def create_snapshot(
        self,
        *,
        job: TrainingJob,
        run: TrainingRun,
        trigger_type: TrainingSnapshotTriggerType,
        metrics: dict[str, Any] | None,
        created_by: User | None,
        notes: str | None = None,
        step: int | None = None,
        epoch: int | None = None,
    ) -> TrainingSnapshot:
        """Persist snapshot metadata and placeholder artefacts."""
        path = self._build_snapshot_path(job.workspace_id, job.id, run.id)
        path.mkdir(parents=True, exist_ok=True)

        metadata = {
            "workspace_id": job.workspace_id,
            "job_id": job.id,
            "run_id": run.id,
            "trigger_type": trigger_type.value,
            "created_at": datetime.utcnow().isoformat(),
            "metrics": metrics or {},
            "notes": notes or "",
            "step": step,
            "epoch": epoch,
        }
        self._write_metadata(path, metadata)
        self._write_placeholder_artifacts(path)

        snapshot = self._snapshots.create(
            workspace_id=job.workspace_id,
            job_id=job.id,
            run_id=run.id,
            path=str(path),
            trigger_type=trigger_type,
            step=step,
            epoch=epoch,
            metrics_json=metrics,
            created_by=created_by.id if created_by else None,
            notes=notes,
        )
        self._audits.record(
            event_type="training.snapshot.created",
            user_id=created_by.id if created_by else None,
            ip_address=None,
            user_agent=None,
            payload={
                "snapshot_id": snapshot.id,
                "workspace_id": job.workspace_id,
                "job_id": job.id,
                "run_id": run.id,
                "path": snapshot.path,
                "trigger_type": trigger_type.value,
            },
        )
        return snapshot

    def list_snapshots(
        self,
        *,
        workspace_id: int | None,
        run_id: int | None,
        current_user: User,
    ) -> Sequence[TrainingSnapshot]:
        """List snapshots by workspace or run with permission checks."""
        if workspace_id is None and run_id is None:
            raise TrainingSnapshotError("必须提供 workspace_id 或 run_id")

        if run_id is not None:
            run = self._runs.get(run_id)
            if run is None:
                raise TrainingSnapshotError("训练运行不存在")
            job = self._jobs.get(run.job_id)
            if job is None:
                raise TrainingSnapshotError("训练任务不存在")
            self._require_launch_permission(job.workspace_id, current_user)
            return self._snapshots.list_for_run(run_id)

        assert workspace_id is not None  # for type checker
        self._require_launch_permission(workspace_id, current_user)
        return self._snapshots.list_for_workspace(workspace_id)

    def get_snapshot(self, snapshot_id: int, current_user: User) -> TrainingSnapshot:
        """Return a snapshot ensuring the caller has access."""
        snapshot = self._load_snapshot(snapshot_id)
        if snapshot is None:
            raise TrainingSnapshotError("训练快照不存在")
        self._require_launch_permission(snapshot.workspace_id, current_user)
        return snapshot

    # ------------------------------------------------------------------ #
    # Resume and rollback
    # ------------------------------------------------------------------ #

    def resume_from_snapshot(
        self,
        snapshot_id: int,
        *,
        current_user: User,
        notes: str | None = None,
    ) -> TrainingRun:
        """Create a new run from an existing snapshot and queue execution."""
        snapshot = self.get_snapshot(snapshot_id, current_user)
        job = self._jobs.get(snapshot.job_id)
        if job is None:
            raise TrainingSnapshotError("训练任务不存在")

        self._require_launch_permission(job.workspace_id, current_user)

        try:
            from app.tasks.training import run_training_job_from_snapshot
        except ImportError as exc:  # pragma: no cover - defensive branch
            raise TrainingSnapshotError("无法导入续训任务执行器") from exc

        with self._transaction():
            run = self._runs.create(
                TrainingRun(
                    job_id=job.id,
                    status=TrainingJobStatus.PENDING,
                    resumed_from_snapshot_id=snapshot.id,
                )
            )
            self._events.create(
                run_id=run.id,
                level="INFO",
                message=f"从快照 {snapshot.id} 启动断点续训。",
            )

            self._jobs.update_status(job, status=TrainingJobStatus.QUEUED, started_at=None, finished_at=None)
            self._acknowledge_alerts(snapshot.run_id, actor_id=current_user.id, status=TrainingAlertStatus.ACKNOWLEDGED)

        self._audits.record(
            event_type="training.snapshot.resume",
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "snapshot_id": snapshot.id,
                "workspace_id": snapshot.workspace_id,
                "job_id": snapshot.job_id,
                "previous_run_id": snapshot.run_id,
                "resumed_run_id": run.id,
                "notes": notes or "",
            },
        )

        run_training_job_from_snapshot.delay(run.id, snapshot.id)
        self._session.refresh(run)
        return run

    def rollback_snapshot(
        self,
        snapshot_id: int,
        *,
        current_user: User,
        reason: str | None = None,
    ) -> TrainingSnapshot:
        """Restore artefacts from the snapshot for manual deployment."""
        snapshot = self.get_snapshot(snapshot_id, current_user)
        self._permissions.require_operation(
            workspace_id=snapshot.workspace_id,
            user=current_user,
            operation=RoleOperation.DEPLOYMENT_MANAGE,
            ip_address=None,
            user_agent=None,
        )

        source = Path(snapshot.path)
        if not source.exists():
            raise TrainingSnapshotError("快照目录不存在")

        destination = self._active_artifact_path(snapshot.workspace_id, snapshot.job_id)
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True, exist_ok=True)
        for item in source.iterdir():
            target = destination / item.name
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)

        evaluation = {
            "snapshot_id": snapshot.id,
            "restored_at": datetime.utcnow().isoformat(),
            "reason": reason or "",
            "next_steps": ["重新运行轻量评估", "通知相关干系人"],
        }
        (destination / "evaluation.json").write_text(
            json.dumps(evaluation, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        with self._transaction():
            snapshot = self._snapshots.mark_restored(snapshot, restored_by=current_user.id)
            self._acknowledge_alerts(snapshot.run_id, actor_id=current_user.id, status=TrainingAlertStatus.RESOLVED)

        self._audits.record(
            event_type="training.snapshot.rollback",
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "snapshot_id": snapshot.id,
                "workspace_id": snapshot.workspace_id,
                "job_id": snapshot.job_id,
                "run_id": snapshot.run_id,
                "reason": reason or "",
                "restored_path": str(destination),
            },
        )

        self._session.refresh(snapshot)
        return snapshot

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _build_snapshot_path(self, workspace_id: int, job_id: int, run_id: int) -> Path:
        root = Path(settings.workspace_storage_root).expanduser()
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        return (
            root
            / "workspaces"
            / str(workspace_id)
            / "training"
            / str(job_id)
            / "runs"
            / str(run_id)
            / "snapshots"
            / timestamp
        )

    def _active_artifact_path(self, workspace_id: int, job_id: int) -> Path:
        root = Path(settings.workspace_storage_root).expanduser()
        return root / "workspaces" / str(workspace_id) / "training" / str(job_id) / "active"

    def _write_metadata(self, path: Path, metadata: dict[str, Any]) -> None:
        metadata_file = path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_placeholder_artifacts(self, path: Path) -> None:
        weights = path / "model.safetensors"
        optimizer = path / "optimizer.pt"
        notes = path / "README.txt"
        if not weights.exists():
            weights.write_text("placeholder weights", encoding="utf-8")
        if not optimizer.exists():
            optimizer.write_text("placeholder optimizer state", encoding="utf-8")
        if not notes.exists():
            notes.write_text(
                "该目录存放训练快照占位文件，后续需替换为真实模型权重与优化器状态。",
                encoding="utf-8",
            )

    def _require_launch_permission(self, workspace_id: int, current_user: User) -> None:
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=current_user,
            operation=RoleOperation.TRAINING_LAUNCH,
            ip_address=None,
            user_agent=None,
        )

    def _acknowledge_alerts(
        self,
        run_id: int,
        *,
        actor_id: int | None,
        status: TrainingAlertStatus,
    ) -> None:
        if run_id is None:
            return
        alerts = self._alerts.list_for_run(run_id)
        for alert in alerts:
            if alert.status == status:
                continue
            if status == TrainingAlertStatus.ACKNOWLEDGED and alert.status != TrainingAlertStatus.TRIGGERED:
                continue
            self._alerts.update_status(alert, status=status, actor_id=actor_id, notes=None)

    def _load_snapshot(self, snapshot_id: int) -> TrainingSnapshot | None:
        statement = select(TrainingSnapshot).where(TrainingSnapshot.id == snapshot_id)
        return self._session.exec(statement).first()
