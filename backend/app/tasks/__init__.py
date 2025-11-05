"""Celery task package."""

from app.core.celery_app import celery_app
from app.tasks import data_cleaning, evaluation, deployment, training  # noqa: F401

__all__ = ["celery_app"]
