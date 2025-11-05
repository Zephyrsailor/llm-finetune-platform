"""Celery tasks for evaluation execution."""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from sqlmodel import Session

from app.core.celery_app import celery_app
from app.core.database import engine
from app.core.config import settings
from app.models import EvaluationJob, EvaluationJobStatus, TrainingRun
from app.repositories.audit import AuditLogRepository
from app.repositories.evaluation import EvaluationJobRepository, EvaluationTemplateRepository
from app.repositories.training import TrainingRunRepository
from app.services.training_monitoring import TrainingMonitoringService

try:  # pragma: no cover - optional dependency
    from sacrebleu.metrics import BLEU as SacreBLEU
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    SacreBLEU = None

try:  # pragma: no cover - optional dependency
    from rouge_score import rouge_scorer
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    rouge_scorer = None


EVALUATION_METRIC_THRESHOLDS: dict[str, float] = {
    "bleu": 0.3,
    "rouge_l": 0.3,
    "exact_match": 0.3,
    "perplexity": 5.0,
}

REFERENCE_KEYS: tuple[str, ...] = (
    "reference",
    "references",
    "answer",
    "label",
    "expected",
    "target",
    "ground_truth",
)
PREDICTION_KEYS: tuple[str, ...] = (
    "prediction",
    "predictions",
    "predicted",
    "output",
    "response",
    "generated",
    "hypothesis",
)


@celery_app.task(name="evaluation.run_job")
def run_evaluation_job(job_id: int) -> None:
    """Execute an evaluation job and persist metrics/results."""
    with Session(engine) as session:
        job_repo = EvaluationJobRepository(session)
        template_repo = EvaluationTemplateRepository(session)
        audit_repo = AuditLogRepository(session)
        run_repo = TrainingRunRepository(session)
        monitoring_service = TrainingMonitoringService(session)

        job = job_repo.get(job_id)
        if job is None:
            return
        template = template_repo.get(job.evaluation_template_id)
        if template is None:
            return

        storage_root = Path(settings.workspace_storage_root).expanduser()
        dataset_path = storage_root / job.dataset_path if job.dataset_path else None
        artifact_root = storage_root / job.artifact_path if job.artifact_path else None

        training_run: TrainingRun | None = None
        baseline_metrics: dict[str, float] = {}
        if job.training_run_id:
            training_run = run_repo.get(job.training_run_id)
            if training_run and training_run.metadata_json:
                evaluation_meta = training_run.metadata_json.get("evaluation") or {}
                baseline_candidate = evaluation_meta.get("baseline_metrics") or {}
                if isinstance(baseline_candidate, dict):
                    baseline_metrics = {
                        key: float(value)
                        for key, value in baseline_candidate.items()
                        if isinstance(value, (int, float))
                    }


        start_time = datetime.utcnow()
        job_repo.update(job, status=EvaluationJobStatus.RUNNING, started_at=start_time)
        session.commit()

        try:
            if dataset_path is None or not dataset_path.exists():
                raise FileNotFoundError("评估输入数据不存在")

            artifact_root = artifact_root or (storage_root / "tmp" / f"evaluation-{job.id}")
            artifact_root.mkdir(parents=True, exist_ok=True)

            files = _collect_dataset_files(dataset_path)
            examples = _load_examples(files)
            metrics = _compute_metrics(examples, baseline=baseline_metrics or None)
            metrics["generated_at"] = datetime.utcnow().isoformat()

            results_path = artifact_root / "results.json"
            results_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

            case_studies = _build_case_studies(examples)
            cases_path = artifact_root / "cases.json"
            cases_path.write_text(json.dumps(case_studies, ensure_ascii=False, indent=2), encoding="utf-8")

            report_path = artifact_root / "report.md"
            report_path.write_text(_build_report_markdown(job.id, template.name, metrics), encoding="utf-8")

            finished_at = datetime.utcnow()
            job_repo.update(
                job,
                status=EvaluationJobStatus.COMPLETED,
                finished_at=finished_at,
                metrics_json=metrics,
                report_path=str(report_path.relative_to(storage_root)),
            )
            if job.training_run_id:
                _update_training_run_metadata(
                    run_repo=run_repo,
                    training_run_id=job.training_run_id,
                    evaluation_job=job,
                    metrics=metrics,
                )
            session.commit()

            thresholds = metrics.get("thresholds", {})
            triggered_metrics = [
                metric for metric, info in thresholds.items() if info.get("triggered")
            ]
            if triggered_metrics:
                audit_repo.record(
                    event_type="evaluation.metric.threshold_triggered",
                    user_id=job.created_by,
                    ip_address=None,
                    user_agent=None,
                    payload={
                        "workspace_id": job.workspace_id,
                        "evaluation_job_id": job.id,
                        "training_run_id": job.training_run_id,
                        "metrics": metrics,
                        "triggered": triggered_metrics,
                    },
                )
                if job.training_run_id:
                    for metric_name in triggered_metrics:
                        info = thresholds.get(metric_name) or {}
                        monitoring_service.record_evaluation_alert(
                            workspace_id=job.workspace_id,
                            run_id=job.training_run_id,
                            metric=metric_name,
                            value=float(metrics.get(metric_name, 0.0)),
                            threshold=float(info.get("threshold", 0.0)),
                            triggered_at=finished_at,
                        )

            audit_repo.record(
                event_type="evaluation.job.completed",
                user_id=job.created_by,
                ip_address=None,
                user_agent=None,
                payload={
                    "workspace_id": job.workspace_id,
                    "evaluation_job_id": job.id,
                    "template_id": template.id,
                    "metrics": metrics,
                },
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            session.rollback()
            failure_time = datetime.utcnow()
            job_repo.update(
                job,
                status=EvaluationJobStatus.FAILED,
                finished_at=failure_time,
                error_message=str(exc),
            )
            session.commit()
            audit_repo.record(
                event_type="evaluation.job.failed",
                user_id=job.created_by,
                ip_address=None,
                user_agent=None,
                payload={
                    "workspace_id": job.workspace_id,
                    "evaluation_job_id": job.id,
                    "training_run_id": job.training_run_id,
                    "error": str(exc),
                },
            )
            if job.training_run_id:
                monitoring_service.record_evaluation_alert(
                    workspace_id=job.workspace_id,
                    run_id=job.training_run_id,
                    metric="evaluation_failure",
                    value=1.0,
                    threshold=0.0,
                    triggered_at=failure_time,
                    notes=str(exc),
                )


def _collect_dataset_files(dataset_path: Path) -> list[Path]:
    if dataset_path.is_file():
        return [dataset_path]
    return [candidate for candidate in dataset_path.rglob("*") if candidate.is_file()]


def _load_examples(files: Sequence[Path]) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    for file_path in files:
        try:
            with file_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    text = line.strip()
                    if not text:
                        continue
                    reference = text
                    prediction = text
                    record = None
                    if file_path.suffix.lower() in {".json", ".jsonl"}:
                        try:
                            record = json.loads(text)
                        except json.JSONDecodeError:
                            record = None
                    if isinstance(record, dict):
                        ref_value = _extract_text(record, REFERENCE_KEYS)
                        if ref_value:
                            reference = ref_value
                        pred_value = _extract_text(record, PREDICTION_KEYS)
                        if pred_value:
                            prediction = pred_value
                    examples.append(
                        {
                            "reference": reference,
                            "prediction": prediction,
                        }
                    )
        except UnicodeDecodeError:
            continue
    return examples


def _extract_text(record: dict, keys: Iterable[str]) -> str | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    return item
    return None


def _tokenize(text: str) -> list[str]:
    return text.strip().split()


def _normalize(text: str) -> str:
    return " ".join(_tokenize(text.lower()))


def _compute_metrics(
    examples: list[dict[str, str]],
    baseline: dict[str, float] | None = None,
) -> dict[str, float | dict]:
    count = len(examples)
    if count == 0:
        return {
            "example_count": 0,
            "avg_tokens_per_example": 0.0,
            "bleu": 0.0,
            "rouge_l": 0.0,
            "exact_match": 0.0,
            "perplexity": 0.0,
            "thresholds": {name: {"threshold": value, "triggered": False} for name, value in EVALUATION_METRIC_THRESHOLDS.items()},
        }

    reference_tokens = [_tokenize(item["reference"]) for item in examples]
    prediction_tokens = [_tokenize(item["prediction"]) for item in examples]

    total_tokens = sum(len(tokens) for tokens in reference_tokens)
    avg_tokens = total_tokens / count if count else 0.0

    exact_match = _compute_exact_match(reference_tokens, prediction_tokens)
    bleu = _compute_bleu_score(reference_tokens, prediction_tokens)
    rouge_l = _compute_rouge_l(reference_tokens, prediction_tokens)
    perplexity = _compute_perplexity(reference_tokens, prediction_tokens)

    metrics: dict[str, float | dict] = {
        "example_count": count,
        "avg_tokens_per_example": round(avg_tokens, 2),
        "bleu": round(bleu, 4),
        "rouge_l": round(rouge_l, 4),
        "exact_match": round(exact_match, 4),
        "perplexity": round(perplexity, 4),
    }

    thresholds: dict[str, dict[str, float | bool]] = {}
    for metric_name, threshold in EVALUATION_METRIC_THRESHOLDS.items():
        value = metrics.get(metric_name)
        if value is None:
            continue
        if metric_name == "perplexity":
            triggered = value > threshold
        else:
            triggered = value < threshold
        thresholds[metric_name] = {
            "threshold": threshold,
            "triggered": triggered,
        }
    metrics["thresholds"] = thresholds
    if baseline:
        deltas: dict[str, float] = {}
        for metric_name, baseline_value in baseline.items():
            current_value = metrics.get(metric_name)
            if not isinstance(baseline_value, (int, float)):
                continue
            if not isinstance(current_value, (int, float)):
                continue
            deltas[metric_name] = round(float(current_value) - float(baseline_value), 4)
        if deltas:
            metrics["baseline"] = baseline
            metrics["delta"] = deltas
    return metrics


def _build_case_studies(examples: list[dict[str, str]]) -> dict[str, list[dict[str, Any]]]:
    improved: list[dict[str, Any]] = []
    regressed: list[dict[str, Any]] = []

    for example in examples:
        reference = example.get("reference", "")
        prediction = example.get("prediction", "")
        score = 1.0 if _normalize(reference) == _normalize(prediction) else 0.0
        record = {
            "reference": reference,
            "prediction": prediction,
            "score": round(float(score), 4),
        }
        if score >= 0.99:
            improved.append(record)
        else:
            regressed.append(record)

    if not improved and examples:
        first = examples[0]
        improved.append(
            {
                "reference": first.get("reference", ""),
                "prediction": first.get("prediction", ""),
                "score": None,
            }
        )

    if not regressed and len(examples) > 1:
        last = examples[-1]
        regressed.append(
            {
                "reference": last.get("reference", ""),
                "prediction": last.get("prediction", ""),
                "score": None,
            }
        )

    return {
        "improved": improved[:10],
        "regressed": regressed[:10],
    }


def _compute_exact_match(references: Sequence[list[str]], predictions: Sequence[list[str]]) -> float:
    matches = 0
    total = len(references)
    for ref_tokens, pred_tokens in zip(references, predictions):
        if _normalize(" ".join(ref_tokens)) == _normalize(" ".join(pred_tokens)):
            matches += 1
    return matches / total if total else 0.0


def _compute_bleu_score(references: Sequence[list[str]], predictions: Sequence[list[str]]) -> float:
    if SacreBLEU is not None:
        prediction_sentences = [" ".join(tokens) for tokens in predictions]
        reference_sentences = [" ".join(tokens) for tokens in references]
        if prediction_sentences:
            bleu_metric = SacreBLEU()
            score = bleu_metric.corpus_score(prediction_sentences, [reference_sentences])
            return float(score.score) / 100.0

    weights = [0.25, 0.25, 0.25, 0.25]
    precisions = []
    total_ref_len = sum(len(tokens) for tokens in references)
    total_pred_len = sum(len(tokens) for tokens in predictions)
    if total_pred_len == 0:
        return 0.0

    for n in range(1, 5):
        matches = 0
        possible = 0
        for ref_tokens, pred_tokens in zip(references, predictions):
            if not pred_tokens:
                continue
            pred_ngrams = Counter(tuple(pred_tokens[i : i + n]) for i in range(len(pred_tokens) - n + 1))
            ref_ngrams = Counter(tuple(ref_tokens[i : i + n]) for i in range(len(ref_tokens) - n + 1))
            for ngram, count in pred_ngrams.items():
                matches += min(count, ref_ngrams.get(ngram, 0))
            possible += max(len(pred_tokens) - n + 1, 0)
        precisions.append((matches + 1) / (possible + 1))

    geo_mean = math.exp(sum(weight * math.log(p) for weight, p in zip(weights, precisions)))
    if total_pred_len > total_ref_len:
        bp = 1.0
    else:
        bp = math.exp(1 - total_ref_len / max(total_pred_len, 1))
    return bp * geo_mean


def _compute_rouge_l(references: Sequence[list[str]], predictions: Sequence[list[str]]) -> float:
    if rouge_scorer is not None:
        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        scores = []
        for ref_tokens, pred_tokens in zip(references, predictions):
            ref_text = " ".join(ref_tokens)
            pred_text = " ".join(pred_tokens)
            if not ref_text or not pred_text:
                continue
            score = scorer.score(ref_text, pred_text)["rougeL"].fmeasure
            scores.append(score)
        if scores:
            return sum(scores) / len(scores)

    scores = []
    for ref_tokens, pred_tokens in zip(references, predictions):
        if not ref_tokens or not pred_tokens:
            continue
        lcs = _lcs_length(ref_tokens, pred_tokens)
        if lcs == 0:
            scores.append(0.0)
            continue
        precision = lcs / len(pred_tokens)
        recall = lcs / len(ref_tokens)
        if precision + recall == 0:
            scores.append(0.0)
            continue
        f_score = (2 * precision * recall) / (precision + recall)
        scores.append(f_score)
    return sum(scores) / len(scores) if scores else 0.0


def _compute_perplexity(references: Sequence[list[str]], predictions: Sequence[list[str]]) -> float:
    total_tokens = 0
    mismatch_tokens = 0
    for ref_tokens, pred_tokens in zip(references, predictions):
        total_tokens += max(len(ref_tokens), 1)
        mismatch_tokens += _token_mismatch(ref_tokens, pred_tokens)
    return 1.0 + (mismatch_tokens / max(total_tokens, 1))


def _token_mismatch(ref_tokens: Sequence[str], pred_tokens: Sequence[str]) -> int:
    mismatches = abs(len(ref_tokens) - len(pred_tokens))
    for ref_token, pred_token in zip(ref_tokens, pred_tokens):
        if ref_token != pred_token:
            mismatches += 1
    return mismatches


def _lcs_length(ref_tokens: Sequence[str], pred_tokens: Sequence[str]) -> int:
    ref_len = len(ref_tokens)
    pred_len = len(pred_tokens)
    if ref_len == 0 or pred_len == 0:
        return 0
    dp = [[0] * (pred_len + 1) for _ in range(ref_len + 1)]
    for i in range(1, ref_len + 1):
        for j in range(1, pred_len + 1):
            if ref_tokens[i - 1] == pred_tokens[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[ref_len][pred_len]


def _update_training_run_metadata(
    *,
    run_repo: TrainingRunRepository,
    training_run_id: int | None,
    evaluation_job: EvaluationJob,
    metrics: dict[str, Any],
) -> None:
    if training_run_id is None:
        return
    training_run: TrainingRun | None = run_repo.get(training_run_id)
    if training_run is None:
        return
    metadata = training_run.metadata_json.copy() if training_run.metadata_json else {}
    evaluation_section = metadata.get("evaluation") or {}
    evaluation_section["latest_job_id"] = evaluation_job.id
    evaluation_section["latest_metrics"] = metrics
    evaluation_section["updated_at"] = datetime.utcnow().isoformat()
    if evaluation_job.report_path:
        evaluation_section["latest_report_path"] = evaluation_job.report_path
    if "baseline_metrics" not in evaluation_section and isinstance(metrics, dict):
        baseline = metrics.get("baseline")
        if isinstance(baseline, dict) and baseline:
            evaluation_section["baseline_metrics"] = baseline
    history = evaluation_section.get("history") or []
    history_entry = {
        "job_id": evaluation_job.id,
        "metrics": metrics,
        "finished_at": datetime.utcnow().isoformat(),
    }
    if evaluation_job.report_path:
        history_entry["report_path"] = evaluation_job.report_path
    history.insert(0, history_entry)
    evaluation_section["history"] = history[:10]
    metadata["evaluation"] = evaluation_section
    run_repo.update(training_run, metadata_json=metadata)


def _build_report_markdown(job_id: int, template_name: str, metrics: dict) -> str:
    """Generate a markdown report summarizing evaluation metrics."""
    lines = [
        f"# 评估报告 #{job_id}",
        "",
        f"- 模板：{template_name}",
        f"- 生成时间：{datetime.utcnow().isoformat()}",
        "",
        "## 指标概览",
    ]
    skip_keys = {"thresholds", "generated_at"}
    for key, value in metrics.items():
        if key in skip_keys:
            continue
        lines.append(f"- **{key}**: {value}")
    thresholds = metrics.get("thresholds", {})
    if thresholds:
        lines.append("")
        lines.append("## 阈值校验")
        for name, info in thresholds.items():
            status = "⚠️ 触发" if info.get("triggered") else "✅ 正常"
            lines.append(f"- {name}: {status}（阈值 {info.get('threshold')}）")
    lines.append("")
    lines.append("> 若阈值触发，请通过训练监控与评估页面检查告警并复核模型质量。")
    return "\n".join(lines)
