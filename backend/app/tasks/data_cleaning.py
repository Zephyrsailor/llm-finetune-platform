"""Celery tasks for data cleaning workflow."""

from __future__ import annotations

import csv
import json
import statistics
import hashlib
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

from sqlmodel import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import engine
from app.models import (
    DataCleaningJob,
    DataCleaningJobStatus,
    Dataset,
    DatasetFormatStatus,
    DatasetFormatType,
    DatasetVersion,
    DatasetVersionStatus,
    QualityEvaluationJob,
    QualityEvaluationStatus,
)
from app.repositories.dataset import (
    DataCleaningJobRepository,
    DatasetRepository,
    DatasetVersionRepository,
)
from app.repositories.quality import QualityEvaluationJobRepository
from app.repositories.format import DatasetFormatVersionRepository


def _append_log(log_path: str | None, message: str) -> None:
    if not log_path:
        return
    root = Path(settings.workspace_storage_root).expanduser()
    log_file = root / log_path
    log_file.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().isoformat()
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def _load_raw_records(version: DatasetVersion) -> tuple[list[dict], list[str]]:
    root = Path(settings.workspace_storage_root).expanduser()
    version_root = root / (version.location_uri or "")
    raw_dir = version_root / "raw"
    records: list[dict] = []
    errors: list[str] = []
    if not raw_dir.exists():
        return records, errors

    for raw_file in sorted(raw_dir.glob("*")):
        if not raw_file.is_file():
            continue
        suffix = raw_file.suffix.lower()
        try:
            if suffix == ".jsonl":
                with raw_file.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        records.append(json.loads(line))
            elif suffix == ".json":
                with raw_file.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                    if isinstance(data, list):
                        records.extend(data)
                    elif isinstance(data, dict):
                        records.append(data)
            elif suffix in {".csv", ".tsv"}:
                delimiter = "," if suffix == ".csv" else "\t"
                with raw_file.open("r", encoding="utf-8", newline="") as handle:
                    reader = csv.DictReader(handle, delimiter=delimiter)
                    for row in reader:
                        records.append({key: value for key, value in row.items() if value is not None})
            else:
                errors.append(f"忽略不支持的文件类型: {raw_file.name}")
        except Exception as exc:  # pragma: no cover - defensive logging
            errors.append(f"解析文件 {raw_file.name} 失败: {exc}")
    return records, errors


def _load_clean_records(version: DatasetVersion) -> list[dict]:
    root = Path(settings.workspace_storage_root).expanduser()
    version_root = root / (version.location_uri or "")
    clean_dir = version_root / "clean"
    cleaned: list[dict] = []
    jsonl_path = clean_dir / "cleaned.jsonl"
    if jsonl_path.exists():
        try:
            with jsonl_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    cleaned.append(json.loads(line))
        except Exception:  # pragma: no cover - defensive
            cleaned = []
    elif clean_dir.exists():
        for file in sorted(clean_dir.glob("*.json")):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    cleaned.extend(data)
            except Exception:  # pragma: no cover
                continue
    return cleaned


def _compute_quality_metrics(records: list[dict]) -> tuple[dict, list[dict]]:
    total = len(records)
    lengths: list[int] = []
    normalized_rows: list[str] = []
    missing_counter: Counter[str] = Counter()
    text_field = "text"

    for row in records:
        serialized = json.dumps(row, sort_keys=True, ensure_ascii=False)
        normalized_rows.append(serialized)
        if isinstance(row.get(text_field), str):
            lengths.append(len(row[text_field]))
        elif row.get(text_field) is not None:
            lengths.append(len(str(row[text_field])))
        else:
            lengths.append(0)
        keys = set(row.keys())
        for key in keys:
            if row.get(key) in (None, "", [], {}):
                missing_counter[key] += 1

    duplicate_count = total - len(set(normalized_rows))
    length_avg = statistics.fmean(lengths) if lengths else 0
    length_median = statistics.median(lengths) if lengths else 0
    length_std = statistics.pstdev(lengths) if len(lengths) > 1 else 0

    anomalies: list[dict] = []
    seen = set()
    for idx, (serialized, length, row) in enumerate(zip(normalized_rows, lengths, records)):
        reasons: list[str] = []
        if serialized in seen:
            reasons.append("duplicate")
        else:
            seen.add(serialized)
        if length_std and length > length_avg + 3 * length_std:
            reasons.append("text_too_long")
        if length_std and length < max(length_avg - 3 * length_std, 0):
            reasons.append("text_too_short")
        if any(row.get(field) in (None, "", [], {}) for field in missing_counter):
            missing_fields = [field for field in missing_counter if row.get(field) in (None, "", [], {})]
            if missing_fields:
                reasons.append(f"missing_fields:{','.join(missing_fields[:3])}")
        if reasons:
            anomalies.append({
                "index": idx,
                "reasons": reasons,
                "record": row,
            })
        if len(anomalies) >= 50:
            break

    missing_stats = {
        field: count for field, count in missing_counter.items()
    }

    quality_score = 0.0
    if total:
        penalty = duplicate_count / total + (missing_stats.get(text_field, 0) / total)
        quality_score = max(0.0, round(1 - penalty, 4))

    stats = {
        "total_rows": total,
        "duplicate_rows": duplicate_count,
        "average_length": length_avg,
        "median_length": length_median,
        "length_stddev": length_std,
        "missing_counts": missing_stats,
        "quality_score": quality_score,
        "anomaly_count": len(anomalies),
        "generated_at": datetime.utcnow().isoformat(),
        "top_anomalies": anomalies[:20],
    }
    return stats, anomalies


def _write_quality_outputs(
    version: DatasetVersion,
    stats: dict,
    anomalies: list[dict],
) -> tuple[str, dict]:
    root = Path(settings.workspace_storage_root).expanduser()
    version_root = root / (version.location_uri or "")
    quality_dir = version_root / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)

    summary_path = quality_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(stats, handle, ensure_ascii=False, indent=2)

    anomalies_path = quality_dir / "anomalies.csv"
    with anomalies_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["index", "reasons", "record"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for anomaly in anomalies:
            writer.writerow(
                {
                    "index": anomaly.get("index"),
                    "reasons": ";".join(anomaly.get("reasons", [])),
                    "record": json.dumps(anomaly.get("record", {}), ensure_ascii=False),
                }
            )

    return (
        str(summary_path.relative_to(root)),
        {
            "json": str(summary_path.relative_to(root)),
            "csv": str(anomalies_path.relative_to(root)),
        },
    )


def _format_dir(version: DatasetVersion, fmt: DatasetFormatType) -> Path:
    root = Path(settings.workspace_storage_root).expanduser()
    version_root = root / (version.location_uri or "")
    directory = version_root / "standard" / fmt.value
    directory.mkdir(parents=True, exist_ok=True)
    return directory
def _apply_cleaning_steps(
    records: list[dict],
    steps: list[dict] | None,
) -> tuple[list[dict], dict]:
    metrics = {
        "duplicates_removed": 0,
        "noise_removed": 0,
        "masked_fields": 0,
        "normalized_fields": 0,
        "trimmed_fields": 0,
    }

    cleaned = [dict(record) for record in records]
    steps = steps or []
    for step in steps:
        step_type = step.get("type")
        if step_type == "deduplicate":
            key_fields = step.get("fields") or ([step.get("field")] if step.get("field") else None)
            seen: set[str] = set()
            unique_rows: list[dict] = []
            duplicates = 0
            for row in cleaned:
                if key_fields:
                    key = "::".join(str(row.get(field, "")) for field in key_fields)
                else:
                    key = json.dumps(row, sort_keys=True, ensure_ascii=False)
                if key in seen:
                    duplicates += 1
                    continue
                seen.add(key)
                unique_rows.append(row)
            metrics["duplicates_removed"] += duplicates
            cleaned = unique_rows
        elif step_type == "drop_noise":
            field = step.get("field")
            keywords = [keyword.lower() for keyword in step.get("keywords", [])]
            removed = 0
            keep_rows: list[dict] = []
            for row in cleaned:
                value = str(row.get(field, "")) if field else json.dumps(row, ensure_ascii=False)
                text = value.lower()
                if any(keyword in text for keyword in keywords):
                    removed += 1
                    continue
                keep_rows.append(row)
            metrics["noise_removed"] += removed
            cleaned = keep_rows
        elif step_type == "mask_field":
            fields = step.get("fields") or ([step.get("field")] if step.get("field") else [])
            replacement = step.get("replacement", "***")
            masked = 0
            for row in cleaned:
                for field in fields:
                    if field in row and isinstance(row[field], str) and row[field]:
                        row[field] = replacement
                        masked += 1
            metrics["masked_fields"] += masked
        elif step_type == "normalize_case":
            field = step.get("field")
            mode = step.get("mode", "lower")
            normalized = 0
            for row in cleaned:
                value = row.get(field)
                if isinstance(value, str) and value:
                    row[field] = value.lower() if mode == "lower" else value.upper()
                    normalized += 1
            metrics["normalized_fields"] += normalized
        elif step_type == "trim_whitespace":
            field = step.get("field")
            trimmed = 0
            for row in cleaned:
                value = row.get(field)
                if isinstance(value, str):
                    new_value = value.strip()
                    if new_value != value:
                        row[field] = new_value
                        trimmed += 1
            metrics["trimmed_fields"] += trimmed

    return cleaned, metrics


def _write_outputs(
    version: DatasetVersion,
    records: list[dict],
    stats: dict,
) -> tuple[str, dict]:
    root = Path(settings.workspace_storage_root).expanduser()
    version_root = root / (version.location_uri or "")
    clean_dir = version_root / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = clean_dir / "cleaned.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in records:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    csv_path = clean_dir / "cleaned.csv"
    field_names: set[str] = set()
    for row in records:
        field_names.update(row.keys())
    field_list = sorted(field_names)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        if field_list:
            writer = csv.DictWriter(handle, fieldnames=field_list)
            writer.writeheader()
            for row in records:
                writer.writerow({field: row.get(field, "") for field in field_list})
        else:
            handle.write("")

    summary_path = clean_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(stats, handle, ensure_ascii=False, indent=2)

    return (
        str(summary_path.relative_to(root)),
        {
            "jsonl": str(jsonl_path.relative_to(root)),
            "csv": str(csv_path.relative_to(root)),
        },
    )


@celery_app.task(name="data_cleaning.run_initial_cleaning")
def run_initial_cleaning(job_id: int, notes: str = "") -> None:
    """Execute the cleaning pipeline using the stored template snapshot."""
    with Session(engine) as session:
        job = session.get(DataCleaningJob, job_id)
        if job is None:
            return

        job_repo = DataCleaningJobRepository(session)
        version_repo = DatasetVersionRepository(session)
        dataset_repo = DatasetRepository(session)
        version = version_repo.get(job.dataset_version_id)
        if version is None:
            job_repo.update_status(
                job,
                status=DataCleaningJobStatus.FAILED,
                error_message="Dataset version not found for cleaning job",
                mark_finished=True,
            )
            session.commit()
            return

        dataset: Dataset | None = dataset_repo.get(version.dataset_id)
        if dataset is None:
            job_repo.update_status(
                job,
                status=DataCleaningJobStatus.FAILED,
                error_message="Dataset not found for cleaning job",
                mark_finished=True,
            )
            session.commit()
            return

        _append_log(job.logs_path, f"开始执行清洗任务。备注: {notes}".strip())
        version_repo.update_status(version, status=DatasetVersionStatus.PROCESSING)
        job_repo.update_status(job, status=DataCleaningJobStatus.RUNNING, mark_started=True)

        records, load_errors = _load_raw_records(version)
        if not records:
            message = "原始数据为空或不可读取"
            job_repo.update_status(
                job,
                status=DataCleaningJobStatus.FAILED,
                error_message=message,
                mark_finished=True,
            )
            version_repo.update_status(version, status=DatasetVersionStatus.FAILED)
            _append_log(job.logs_path, message)
            session.commit()
            return

        cleaned_records, metrics = _apply_cleaning_steps(records, (job.template_snapshot or {}).get("steps"))

        stats = {
            "total_rows": len(records),
            "rows_after_cleaning": len(cleaned_records),
            "duplicates_removed": metrics["duplicates_removed"],
            "noise_removed": metrics["noise_removed"],
            "masked_fields": metrics["masked_fields"],
            "normalized_fields": metrics["normalized_fields"],
            "trimmed_fields": metrics["trimmed_fields"],
            "load_errors": load_errors,
            "template": job.template_snapshot,
            "generated_at": datetime.utcnow().isoformat(),
        }

        summary_path, manifest = _write_outputs(version, cleaned_records, stats)

        version_repo.update_status(
            version,
            status=DatasetVersionStatus.COMPLETED,
            stats_json=stats,
        )
        job_repo.update_status(
            job,
            status=DataCleaningJobStatus.COMPLETED,
            summary_path=summary_path,
            export_manifest=manifest,
            mark_finished=True,
        )
        _append_log(job.logs_path, "清洗任务完成并生成导出文件。")

        quality_repo = QualityEvaluationJobRepository(session)
        quality_job = quality_repo.get_by_version(version.id)
        quality_job_id = quality_job.id if quality_job else None
        quality_logs_path = quality_job.logs_path if quality_job else None

        session.commit()

        if quality_job_id is not None:
            _append_log(quality_logs_path, "清洗完成，准备执行质量评估。")
            run_quality_evaluation.delay(quality_job_id)


@celery_app.task(name="data_cleaning.run_quality_evaluation")
def run_quality_evaluation(job_id: int) -> None:
    """Execute quality metrics computation for a dataset version."""
    with Session(engine) as session:
        job_repo = QualityEvaluationJobRepository(session)
        version_repo = DatasetVersionRepository(session)
        dataset_repo = DatasetRepository(session)

        job = job_repo.get(job_id)
        if job is None:
            return

        version = version_repo.get(job.dataset_version_id)
        if version is None:
            job_repo.update_status(
                job,
                status=QualityEvaluationStatus.FAILED,
                error_message="Dataset version not found for quality evaluation",
                mark_finished=True,
            )
            session.commit()
            return

        dataset = dataset_repo.get(version.dataset_id)
        if dataset is None:
            job_repo.update_status(
                job,
                status=QualityEvaluationStatus.FAILED,
                error_message="Dataset not found for quality evaluation",
                mark_finished=True,
            )
            session.commit()
            return

        job_repo.update_status(job, status=QualityEvaluationStatus.RUNNING, mark_started=True)
        _append_log(job.logs_path, "开始执行质量评估任务。")

        records = _load_clean_records(version)
        if not records:
            job_repo.update_status(
                job,
                status=QualityEvaluationStatus.FAILED,
                error_message="缺少清洗后的数据，无法计算质量指标",
                mark_finished=True,
            )
            _append_log(job.logs_path, "未找到 cleaned.jsonl，任务失败。")
            session.commit()
            return

        stats, anomalies = _compute_quality_metrics(records)
        summary_path, manifest = _write_quality_outputs(version, stats, anomalies)

        existing_status = version.status
        version_repo.update_status(
            version,
            status=existing_status,
            stats_json={"quality": stats},
        )
        version.quality_summary_path = summary_path
        version.quality_report_manifest = manifest
        session.add(version)

        job_repo.update_status(
            job,
            status=QualityEvaluationStatus.COMPLETED,
            summary_path=summary_path,
            export_manifest=manifest,
            mark_finished=True,
        )
        _append_log(job.logs_path, "质量评估任务完成。")
        session.commit()


@celery_app.task(name="data_cleaning.run_format_standardization")
def run_format_standardization(format_id: int) -> None:
    """Generate standardised artefacts for the given format record."""
    with Session(engine) as session:
        format_repo = DatasetFormatVersionRepository(session)
        version_repo = DatasetVersionRepository(session)
        dataset_repo = DatasetRepository(session)

        record = format_repo.get(format_id)
        if record is None:
            return

        version = version_repo.get(record.dataset_version_id)
        if version is None:
            format_repo.update_status(
                record,
                status=DatasetFormatStatus.FAILED,
                error_message="Dataset version not found",
                mark_finished=True,
            )
            session.commit()
            return

        dataset = dataset_repo.get(version.dataset_id)
        if dataset is None:
            format_repo.update_status(
                record,
                status=DatasetFormatStatus.FAILED,
                error_message="Dataset not found",
                mark_finished=True,
            )
            session.commit()
            return

        format_repo.update_status(record, status=DatasetFormatStatus.RUNNING, mark_started=True)
        _append_log(record.logs_path, "开始执行格式转换任务。")

        records = _load_clean_records(version)
        if not records:
            format_repo.update_status(
                record,
                status=DatasetFormatStatus.FAILED,
                error_message="未找到清洗后的数据，无法转换",
                mark_finished=True,
            )
            _append_log(record.logs_path, "缺少 cleaned.jsonl，任务失败。")
            session.commit()
            return

        root = Path(settings.workspace_storage_root).expanduser()
        format_dir = _format_dir(version, record.format)

        if record.format == DatasetFormatType.JSONL:
            source = root / (version.location_uri or "") / "clean" / "cleaned.jsonl"
            target = format_dir / "data.jsonl"
            if source.exists():
                shutil.copyfile(source, target)
            else:
                with target.open("w", encoding="utf-8") as handle:
                    for row in records:
                        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        elif record.format == DatasetFormatType.SFT:
            target = format_dir / "sft.jsonl"
            with target.open("w", encoding="utf-8") as handle:
                for row in records:
                    completion = row.get("text")
                    if completion is None:
                        completion = json.dumps(row, ensure_ascii=False)
                    handle.write(json.dumps({"prompt": "", "completion": completion}, ensure_ascii=False) + "\n")
        elif record.format == DatasetFormatType.PARQUET:
            target = format_dir / "data.parquet"
            # 占位实现：写入 JSON 数组以模拟结构，后续可替换为真实 Parquet 转换
            with target.open("w", encoding="utf-8") as handle:
                json.dump(records, handle, ensure_ascii=False)
        else:  # pragma: no cover - safeguard
            target = format_dir / "data.out"
            with target.open("w", encoding="utf-8") as handle:
                json.dump(records, handle, ensure_ascii=False)

        file_size = target.stat().st_size
        checksum = hashlib.sha256(target.read_bytes()).hexdigest()
        relative_path = str(target.relative_to(root))

        format_repo.update_status(
            record,
            status=DatasetFormatStatus.COMPLETED,
            path=relative_path,
            checksum=checksum,
            file_size=file_size,
            mark_finished=True,
        )
        format_repo.set_active(record.id)

        stats_json = (version.stats_json or {}).get("formats", {})
        stats_json = {**stats_json, record.format.value: {
            "path": relative_path,
            "checksum": checksum,
            "file_size": file_size,
            "updated_at": datetime.utcnow().isoformat(),
        }}
        version_repo.update_status(
            version,
            status=version.status,
            stats_json={"formats": stats_json},
        )

        _append_log(record.logs_path, f"格式转换完成，输出 {record.format.value}。")
        session.commit()
