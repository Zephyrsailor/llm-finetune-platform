"""Transformer + PEFT training runner used by Celery tasks."""

from __future__ import annotations

import json
import logging
import math
import os
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

from app.models import TrainingMetricName

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

@dataclass
class TrainingHistoryItem:
    step: int
    loss: float
    perplexity: float
    throughput: float
    vocab_size: int
    timestamp: str


@dataclass
class TrainingSummary:
    final_loss: float
    final_perplexity: float
    vocab_size: int
    total_tokens: int
    total_examples: int
    history: list[TrainingHistoryItem]
    artifact_uri: str


def _import_training_dependencies():
    import logging
    import sys

    logger = logging.getLogger(__name__)
    try:
        import torch
        from torch.utils.data import Dataset
        from transformers import (
            AutoModelForCausalLM,
            DataCollatorForLanguageModeling,
            GPT2Config,
            PreTrainedTokenizerFast,
            Trainer,
            TrainerCallback,
            TrainerControl,
            TrainerState,
            TrainingArguments,
        )
        from transformers.tokenization_utils_base import PaddingStrategy
        from tokenizers import Tokenizer, normalizers
        from tokenizers.models import BPE
        from tokenizers.pre_tokenizers import Whitespace
        from tokenizers.processors import TemplateProcessing
        from tokenizers.trainers import BpeTrainer
        from peft import LoraConfig, PeftModel, TaskType, get_peft_model
    except ModuleNotFoundError as exc:
        logger.exception("Import training dependencies failed on python=%s", sys.executable)
        raise RuntimeError(
            "缺少 transformers/peft/torch 依赖，请先在后端虚拟环境中安装："
            "'pip install torch transformers peft accelerate tokenizers'."
        ) from exc

    logger.info(
        "Loaded training deps: python=%s torch=%s transformers=%s peft=%s",
        sys.executable,
        getattr(torch, "__version__", "unknown"),
        __import__("transformers").__version__,
        __import__("peft").__version__,
    )
    return {
        "torch": torch,
        "Dataset": Dataset,
        "AutoModelForCausalLM": AutoModelForCausalLM,
        "DataCollatorForLanguageModeling": DataCollatorForLanguageModeling,
        "GPT2Config": GPT2Config,
        "PreTrainedTokenizerFast": PreTrainedTokenizerFast,
        "Trainer": Trainer,
        "TrainerCallback": TrainerCallback,
        "TrainerControl": TrainerControl,
        "TrainerState": TrainerState,
        "TrainingArguments": TrainingArguments,
        "PaddingStrategy": PaddingStrategy,
        "Tokenizer": Tokenizer,
        "normalizers": normalizers,
        "BPE": BPE,
        "Whitespace": Whitespace,
        "TemplateProcessing": TemplateProcessing,
        "BpeTrainer": BpeTrainer,
        "LoraConfig": LoraConfig,
        "PeftModel": PeftModel,
        "TaskType": TaskType,
        "get_peft_model": get_peft_model,
    }


def run_transformer_training(
    *,
    texts: Sequence[str],
    output_dir: Path,
    monitor,
    run,
    event_repo,
    resume_dir: Path | None = None,
) -> TrainingSummary:
    if not texts:
        raise RuntimeError("训练数据为空。")

    deps = _import_training_dependencies()
    torch = deps["torch"]
    Dataset = deps["Dataset"]
    AutoModelForCausalLM = deps["AutoModelForCausalLM"]
    DataCollatorForLanguageModeling = deps["DataCollatorForLanguageModeling"]
    GPT2Config = deps["GPT2Config"]
    PreTrainedTokenizerFast = deps["PreTrainedTokenizerFast"]
    Trainer = deps["Trainer"]
    TrainerCallback = deps["TrainerCallback"]
    TrainerControl = deps["TrainerControl"]
    TrainerState = deps["TrainerState"]
    TrainingArguments = deps["TrainingArguments"]
    PaddingStrategy = deps["PaddingStrategy"]
    Tokenizer = deps["Tokenizer"]
    normalizers = deps["normalizers"]
    BPE = deps["BPE"]
    Whitespace = deps["Whitespace"]
    TemplateProcessing = deps["TemplateProcessing"]
    BpeTrainer = deps["BpeTrainer"]
    LoraConfig = deps["LoraConfig"]
    PeftModel = deps["PeftModel"]
    TaskType = deps["TaskType"]
    get_peft_model = deps["get_peft_model"]

    class PackedCausalDataset(Dataset):
        def __init__(self, tokenizer: PreTrainedTokenizerFast, input_texts: Sequence[str], block_size: int = 128):
            ids: list[int] = []
            pad_value = tokenizer.eos_token_id or tokenizer.pad_token_id or 0
            if tokenizer.pad_token_id is None:
                tokenizer.pad_token = tokenizer.eos_token or "<pad>"
            encoded = tokenizer(
                input_texts,
                add_special_tokens=True,
                padding=PaddingStrategy.DO_NOT_PAD,
                truncation=False,
            )
            for sequence in encoded["input_ids"]:
                ids.extend(sequence + [pad_value])
            examples: list[torch.Tensor] = []
            for start in range(0, max(len(ids) - block_size, 0), block_size):
                chunk = ids[start : start + block_size]
                if len(chunk) < block_size:
                    chunk = chunk + [pad_value] * (block_size - len(chunk))
                examples.append(torch.tensor(chunk, dtype=torch.long))
            if not examples and ids:
                padded = ids[:block_size]
                if len(padded) < block_size:
                    padded = padded + [pad_value] * (block_size - len(padded))
                examples.append(torch.tensor(padded, dtype=torch.long))
            self.examples = examples

        def __len__(self) -> int:
            return len(self.examples)

        def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
            tensor = self.examples[index]
            return {"input_ids": tensor, "attention_mask": torch.ones_like(tensor), "labels": tensor.clone()}

    class MonitoringCallback(TrainerCallback):
        def __init__(self, history: list[TrainingHistoryItem]):
            self.history = history
            self._logged_gpu = False

        def on_log(
            self,
            args: TrainingArguments,
            state: TrainerState,
            control: TrainerControl,
            logs: dict[str, float],
            **kwargs,
        ) -> None:
            if "loss" not in logs:
                return
            loss = float(logs["loss"])
            perplexity = math.exp(loss) if loss < 20 else float("inf")
            throughput = float(logs.get("tokens_per_second") or logs.get("samples_per_second") or 0.0)
            vocab_size = int(logs.get("vocab_size") or 0)
            timestamp = datetime.utcnow().isoformat()
            monitor.record_metric(run=run, metric=TrainingMetricName.LOSS, value=loss)
            if math.isfinite(perplexity):
                monitor.record_metric(run=run, metric=TrainingMetricName.PERPLEXITY, value=perplexity)
            if throughput:
                monitor.record_metric(run=run, metric=TrainingMetricName.THROUGHPUT, value=throughput)
            if not self._logged_gpu:
                monitor.record_metric(run=run, metric=TrainingMetricName.GPU_MEMORY, value=2.0)
                self._logged_gpu = True
            history_item = TrainingHistoryItem(
                step=int(state.global_step),
                loss=loss,
                perplexity=perplexity,
                throughput=throughput,
                vocab_size=vocab_size,
                timestamp=timestamp,
            )
            self.history.append(history_item)
            event_repo.create(
                run_id=run.id,
                level="INFO",
                message=f"Step {history_item.step}: loss={loss:.4f}, ppl={perplexity:.2f}",
            )

    def build_tokenizer(input_texts: Sequence[str]) -> PreTrainedTokenizerFast:
        tokenizer = Tokenizer(BPE(unk_token="<unk>"))
        tokenizer.normalizer = normalizers.Sequence(
            [normalizers.NFD(), normalizers.Lowercase(), normalizers.StripAccents()]
        )
        tokenizer.pre_tokenizer = Whitespace()
        specials = ["<s>", "</s>", "<unk>", "<pad>"]
        trainer = BpeTrainer(vocab_size=2048, min_frequency=1, special_tokens=specials)
        tokenizer.train_from_iterator(iter(input_texts), trainer=trainer)
        tokenizer.post_processor = TemplateProcessing(
            single="<s> $A </s>",
            pair="<s> $A </s> $B </s>",
            special_tokens=[("<s>", tokenizer.token_to_id("<s>")), ("</s>", tokenizer.token_to_id("</s>"))],
        )
        fast_tokenizer = PreTrainedTokenizerFast(tokenizer_object=tokenizer)
        fast_tokenizer.bos_token = "<s>"
        fast_tokenizer.eos_token = "</s>"
        fast_tokenizer.unk_token = "<unk>"
        fast_tokenizer.pad_token = "<pad>"
        return fast_tokenizer

    def create_model(tokenizer: PreTrainedTokenizerFast) -> AutoModelForCausalLM:
        config = GPT2Config(
            vocab_size=len(tokenizer),
            n_layer=2,
            n_head=2,
            n_positions=256,
            n_ctx=256,
            n_embd=128,
            bos_token_id=tokenizer.bos_token_id,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.pad_token_id,
        )
        base_model = AutoModelForCausalLM.from_config(config)
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=8,
            lora_alpha=16,
            lora_dropout=0.05,
            bias="none",
            target_modules=["c_attn", "c_proj"],
        )
        if resume_dir and (resume_dir / "adapter_config.json").exists():
            return PeftModel.from_pretrained(get_peft_model(base_model, lora_config), resume_dir)
        return get_peft_model(base_model, lora_config)

    def prepare_training_args(dataset_size: int) -> TrainingArguments:
        per_device_batch = 1 if dataset_size < 2 else 2
        return TrainingArguments(
            output_dir=str(output_dir),
            overwrite_output_dir=True,
            per_device_train_batch_size=per_device_batch,
            num_train_epochs=1.0,
            gradient_accumulation_steps=1,
            learning_rate=2e-4,
            warmup_steps=0,
            weight_decay=0.0,
            logging_steps=1,
            save_strategy="no",
            report_to=[],
            dataloader_num_workers=0,
            logging_dir=str(output_dir / "logs"),
            include_num_input_tokens_seen=True,
            no_cuda=True,
            use_mps_device=False,
        )

    random.shuffle(texts)
    tokenizer = build_tokenizer(texts)
    dataset = PackedCausalDataset(tokenizer, texts)
    if len(dataset) == 0:
        raise RuntimeError("训练数据量不足，无法构造样本。")

    output_dir.mkdir(parents=True, exist_ok=True)
    tokenizer.save_pretrained(output_dir / "tokenizer")

    model = create_model(tokenizer)
    model.to("cpu")
    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    history: list[TrainingHistoryItem] = []
    callback = MonitoringCallback(history=history)
    training_args = prepare_training_args(len(dataset))

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=data_collator,
        callbacks=[callback],
    )

    train_result = trainer.train()

    final_loss = float(
        (train_result.training_loss if train_result.training_loss is not None else None)
        or (history[-1].loss if history else 0.0)
    )
    final_perplexity = math.exp(final_loss) if final_loss < 20 else float("inf")
    vocab_size = len(tokenizer)
    total_tokens = int(sum(item.vocab_size for item in history)) if history else 0

    model_dir = output_dir / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(model_dir)
    if hasattr(model, "base_model"):
        base_config = model.base_model.model.config.to_json_string()
        (model_dir / "base_config.json").write_text(base_config, encoding="utf-8")

    summary_payload = {
        "final_loss": final_loss,
        "final_perplexity": final_perplexity,
        "history": [item.__dict__ for item in history],
        "train_steps": int(train_result.global_step),
        "total_examples": len(dataset),
        "vocab_size": vocab_size,
        "total_tokens": total_tokens,
        "created_at": datetime.utcnow().isoformat(),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return TrainingSummary(
        final_loss=final_loss,
        final_perplexity=final_perplexity,
        vocab_size=vocab_size,
        total_tokens=total_tokens,
        total_examples=len(dataset),
        history=history,
        artifact_uri=str(output_dir),
    )
