"""Celery application configuration."""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery("llmft")

celery_app.conf.broker_url = settings.redis_url
celery_app.conf.result_backend = settings.redis_url
celery_app.conf.task_always_eager = settings.celery_task_always_eager
celery_app.conf.task_eager_propagates = True
celery_app.conf.imports = (
    "app.tasks.training",
    "app.tasks.data_cleaning",
    "app.tasks.evaluation",
    "app.tasks.deployment",
)

__all__ = ["celery_app"]
