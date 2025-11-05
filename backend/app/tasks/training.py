"""Celery tasks orchestrating transformer + PEFT training runs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Sequence

from sqlmodel import Session

import logging
import sys

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import engine
from app.models import (
    DatasetFormatStatus,
    DatasetFormatVersion,
    DatasetVersion,
    TrainingJobStatus,
    TrainingRun,
    TrainingSnapshotTriggerType,
)
from app.repositories.dataset import DatasetVersionRepository
from app.repositories.format import DatasetFormatVersionRepository
from app.repositories.training import (
    TrainingEventRepository,
    TrainingJobRepository,
    TrainingRunRepository,
)
from app.services.training_monitoring import TrainingMonitoringService
from app.services.training_snapshots import TrainingSnapshotService
from app.services.training_experiments import TrainingExperimentService
from app.services.evaluation import EvaluationService
from app.services.training_runner import run_transformer_training


def _storage_root() -> Path:
    return Path(settings.workspace_storage_root).expanduser()


def _extract_text_from_record(record: dict) -> str | None:
    if not isinstance(record, dict):
        return None
    for key in ("completion", "text", "output", "content", "value"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    messages = record.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
    choices = record.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if isinstance(choice, dict):
                content = choice.get("text") or choice.get("content") or choice.get("message")
                if isinstance(content, str) and content.strip():
                    return content.strip()
    return None


def _load_jsonl(path: Path) -> list[str]:
    texts: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                parsed = line
            if isinstance(parsed, dict):
                text = _extract_text_from_record(parsed)
                if text:
                    texts.append(text)
            elif isinstance(parsed, list):
                for item in parsed:
                    text = _extract_text_from_record(item)
                    if text:
                        texts.append(text)
            elif isinstance(parsed, str) and parsed.strip():
                texts.append(parsed.strip())
    return texts


def _load_json(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    texts: list[str] = []
    if isinstance(data, list):
        for item in data:
            text = _extract_text_from_record(item) if isinstance(item, dict) else None
            if text:
                texts.append(text)
            elif isinstance(item, str) and item.strip():
                texts.append(item.strip())
    elif isinstance(data, dict):
        text = _extract_text_from_record(data)
        if text:
            texts.append(text)
    elif isinstance(data, str) and data.strip():
        texts.append(data.strip())
    return texts


def _gather_texts(version: DatasetVersion, dataset_format: DatasetFormatVersion | None) -> list[str]:
    root = _storage_root()
    if dataset_format and dataset_format.path:
        format_path = root / dataset_format.path
        if format_path.is_file():
            suffix = format_path.suffix.lower()
            if suffix in {".jsonl", ".ndjson"}:
                return _load_jsonl(format_path)
            if suffix in {".json", ".txt"}:
                return _load_json(format_path)
        elif format_path.is_dir():
            texts: list[str] = []
            for candidate in sorted(format_path.glob("*.jsonl")):
                texts.extend(_load_jsonl(candidate))
            if texts:
                return texts
    clean_path = root / (version.location_uri or "") / "clean" / "cleaned.jsonl"
    if clean_path.exists():
        return _load_jsonl(clean_path)
    return []


def _resolve_dataset_format(
    repo: DatasetFormatVersionRepository,
    version: DatasetVersion,
    requested_format_id: int | None,
) -> DatasetFormatVersion:
    if requested_format_id is not None:
        record = repo.get(requested_format_id)
        if (
            record is None
            or record.dataset_version_id != version.id
            or record.status != DatasetFormatStatus.COMPLETED
        ):
            raise RuntimeError("指定的标准化格式不存在或尚未完成。")
        return record
    candidates: Sequence[DatasetFormatVersion] = repo.list_for_version(version.id)
    for candidate in candidates:
        if candidate.is_active and candidate.status == DatasetFormatStatus.COMPLETED:
            return candidate
    for candidate in candidates:
        if candidate.status == DatasetFormatStatus.COMPLETED:
            return candidate
    raise RuntimeError("缺少已完成的标准化格式，无法训练。")


def _prepare_training_payload(session: Session, job) -> tuple[DatasetVersion, DatasetFormatVersion, list[str]]:
    version_repo = DatasetVersionRepository(session)
    format_repo = DatasetFormatVersionRepository(session)

    version = version_repo.get(job.dataset_version_id)
    if version is None:
        raise RuntimeError("数据集版本不存在。")

    dataset_format = _resolve_dataset_format(
        format_repo,
        version,
        job.dataset_format_version_id,
    )

    texts = _gather_texts(version, dataset_format)
    if not texts:
        raise RuntimeError("标准化数据为空，无法训练。")
    return version, dataset_format, texts


def _artifact_dir(job) -> Path:
    return _storage_root() / "training" / str(job.workspace_id) / str(job.id) / "artifacts"


def _relative_artifact_path(path: Path) -> str:
    try:
        return str(path.relative_to(_storage_root()))
    except ValueError:
        return str(path)


@celery_app.task(name="training.run_job")
def run_training_job(job_id: int) -> None:
    with Session(engine) as session:
        job_repo = TrainingJobRepository(session)
        run_repo = TrainingRunRepository(session)
        event_repo = TrainingEventRepository(session)

        job = job_repo.get(job_id)
        if job is None:
            return

        monitor = TrainingMonitoringService(session)
        snapshot_service = TrainingSnapshotService(session)
        experiment_service = TrainingExperimentService(session)

        start_time = datetime.utcnow()
        job_repo.update_status(job, status=TrainingJobStatus.RUNNING, started_at=start_time)
        run = run_repo.create(
            TrainingRun(
                job_id=job.id,
                status=TrainingJobStatus.RUNNING,
                started_at=start_time,
            )
        )
        event_repo.create(
            run_id=run.id,
            level="INFO",
            message=f"训练任务启动（队列：{job.queue_name}，GPU：{job.requested_gpus} 张），准备加载数据。",
        )
        session.commit()

        logger = logging.getLogger(__name__)
        logger.info("Executing training.run_job on python: %s", sys.executable)

        try:
            version, dataset_format, texts = _prepare_training_payload(session, job)
            event_repo.create(
                run_id=run.id,
                level="INFO",
                message=f"已加载标准化数据集版本 #{version.id}（格式：{dataset_format.format.value}），样本数：{len(texts)}。",
            )
            session.commit()

            artifact_dir = _artifact_dir(job)
            resume_dir = artifact_dir / "model"
            resume_path = resume_dir if resume_dir.exists() else None
            summary = run_transformer_training(
                texts=texts,
                output_dir=artifact_dir,
                monitor=monitor,
                run=run,
                event_repo=event_repo,
                resume_dir=resume_path,
            )

            finished_at = datetime.utcnow()
            artifact_uri = _relative_artifact_path(artifact_dir)
            run_repo.update(
                run,
                status=TrainingJobStatus.COMPLETED,
                finished_at=finished_at,
                metrics_json={
                    "final_loss": summary.final_loss,
                    "final_perplexity": summary.final_perplexity,
                    "vocab_size": summary.vocab_size,
                    "total_examples": summary.total_examples,
                    "total_tokens": summary.total_tokens,
                },
                metadata_json={
                    "trainer": {"type": "transformers_peft", "history_steps": len(summary.history)},
                    "dataset_version_id": version.id,
                    "dataset_format_version_id": dataset_format.id,
                },
                artifact_uri=artifact_uri,
                exit_code=0,
            )
            job_repo.update_status(job, status=TrainingJobStatus.COMPLETED, finished_at=finished_at)
            event_repo.create(
                run_id=run.id,
                level="INFO",
                message=(
                    f"训练完成，loss={summary.final_loss:.4f}，perplexity={summary.final_perplexity:.2f}，"
                    f"模型已保存到 {artifact_uri}。"
                ),
            )
            snapshot_service.create_snapshot(
                job=job,
                run=run,
                trigger_type=TrainingSnapshotTriggerType.SCHEDULED,
                metrics={
                    "final_loss": summary.final_loss,
                    "final_perplexity": summary.final_perplexity,
                },
                created_by=None,
                notes="自动保存快照",
            )
            experiment_service.refresh_run_metadata(run.id)
            session.commit()

            evaluation_service = EvaluationService(session)
            evaluation_service.schedule_automatic_evaluation(training_run=run, job=job)
            session.commit()
        except Exception as exc:  # pragma: no cover
            session.rollback()
            failure_time = datetime.utcnow()
            job_repo.update_status(
                job,
                status=TrainingJobStatus.FAILED,
                finished_at=failure_time,
                error_message=str(exc),
            )
            run_repo.update(
                run,
                status=TrainingJobStatus.FAILED,
                finished_at=failure_time,
                exit_code=1,
            )
            event_repo.create(run_id=run.id, level="ERROR", message=f"训练任务失败：{exc}")
            session.commit()


@celery_app.task(name="training.run_job_from_snapshot")
def run_training_job_from_snapshot(run_id: int, snapshot_id: int) -> None:
    with Session(engine) as session:
        job_repo = TrainingJobRepository(session)
        run_repo = TrainingRunRepository(session)
        event_repo = TrainingEventRepository(session)
        snapshot_service = TrainingSnapshotService(session)
        monitor = TrainingMonitoringService(session)
        experiment_service = TrainingExperimentService(session)

        run = run_repo.get(run_id)
        if run is None:
            return
        job = job_repo.get(run.job_id)
        if job is None:
            return

        start_time = datetime.utcnow()
        job_repo.update_status(job, status=TrainingJobStatus.RUNNING, started_at=start_time)
        run_repo.update(run, status=TrainingJobStatus.RUNNING, finished_at=None)
        event_repo.create(
            run_id=run.id,
            level="INFO",
            message=f"从快照 {snapshot_id} 恢复训练，加载历史模型参数。",
        )
        session.commit()

        try:
            version, dataset_format, texts = _prepare_training_payload(session, job)
            artifact_dir = _artifact_dir(job)
            resume_dir = artifact_dir / "model"
            summary = run_transformer_training(
                texts=texts,
                output_dir=artifact_dir,
                monitor=monitor,
                run=run,
                event_repo=event_repo,
                resume_dir=resume_dir if resume_dir.exists() else None,
            )

            finished_at = datetime.utcnow()
            artifact_uri = _relative_artifact_path(artifact_dir)
            run_repo.update(
                run,
                status=TrainingJobStatus.COMPLETED,
                finished_at=finished_at,
                metrics_json={
                    "final_loss": summary.final_loss,
                    "final_perplexity": summary.final_perplexity,
                    "vocab_size": summary.vocab_size,
                    "total_examples": summary.total_examples,
                    "total_tokens": summary.total_tokens,
                    "resumed_from_snapshot": snapshot_id,
                },
                metadata_json={
                    "trainer": {
                        "type": "transformers_peft",
                        "history_steps": len(summary.history),
                        "resumed": True,
                    },
                    "dataset_version_id": version.id,
                    "dataset_format_version_id": dataset_format.id,
                    "resume_snapshot_id": snapshot_id,
                },
                artifact_uri=artifact_uri,
                exit_code=0,
            )
            job_repo.update_status(job, status=TrainingJobStatus.COMPLETED, finished_at=finished_at)
            event_repo.create(
                run_id=run.id,
                level="INFO",
                message=(
                    f"续训完成，loss={summary.final_loss:.4f}，perplexity={summary.final_perplexity:.2f}，"
                    "模型已更新。"
                ),
            )
            snapshot_service.create_snapshot(
                job=job,
                run=run,
                trigger_type=TrainingSnapshotTriggerType.MANUAL,
                metrics={
                    "final_loss": summary.final_loss,
                    "final_perplexity": summary.final_perplexity,
                },
                created_by=None,
                notes=f"resume from snapshot {snapshot_id}",
            )
            experiment_service.refresh_run_metadata(run.id)
            session.commit()
        except Exception as exc:  # pragma: no cover
            session.rollback()
            failure_time = datetime.utcnow()
            job_repo.update_status(
                job,
                status=TrainingJobStatus.FAILED,
                finished_at=failure_time,
                error_message=str(exc),
            )
            run_repo.update(
                run,
                status=TrainingJobStatus.FAILED,
                finished_at=failure_time,
                exit_code=1,
            )
            event_repo.create(run_id=run.id, level="ERROR", message=f"续训失败：{exc}")
            session.commit()
