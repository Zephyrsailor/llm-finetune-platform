"""Repository helpers for dataset format conversions."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlmodel import Session, select

from app.models import DatasetFormatStatus, DatasetFormatType, DatasetFormatVersion


class DatasetFormatVersionRepository:
    """Persist and query standardised dataset formats."""

    def __init__(self, session: Session):
        self._session = session

    def create(
        self,
        *,
        dataset_version_id: int,
        format: DatasetFormatType,
        logs_path: str | None = None,
    ) -> DatasetFormatVersion:
        now = datetime.utcnow()
        record = DatasetFormatVersion(
            dataset_version_id=dataset_version_id,
            format=format,
            status=DatasetFormatStatus.PENDING,
            created_at=now,
            updated_at=now,
            logs_path=logs_path,
        )
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)
        return record

    def get(self, format_id: int) -> DatasetFormatVersion | None:
        return self._session.get(DatasetFormatVersion, format_id)

    def list_for_version(self, dataset_version_id: int) -> Sequence[DatasetFormatVersion]:
        statement = (
            select(DatasetFormatVersion)
            .where(DatasetFormatVersion.dataset_version_id == dataset_version_id)
            .order_by(DatasetFormatVersion.created_at.desc())
        )
        return tuple(self._session.exec(statement).all())

    def get_latest(self, dataset_version_id: int, format: DatasetFormatType) -> DatasetFormatVersion | None:
        statement = (
            select(DatasetFormatVersion)
            .where(
                DatasetFormatVersion.dataset_version_id == dataset_version_id,
                DatasetFormatVersion.format == format,
            )
            .order_by(DatasetFormatVersion.created_at.desc())
        )
        return self._session.exec(statement).first()

    def set_active(self, format_id: int) -> DatasetFormatVersion:
        record = self.get(format_id)
        if record is None:
            raise ValueError("format not found")
        all_records = self.list_for_version(record.dataset_version_id)
        now = datetime.utcnow()
        for candidate in all_records:
            candidate.is_active = candidate.id == record.id
            candidate.updated_at = now
            self._session.add(candidate)
        self._session.flush()
        self._session.refresh(record)
        return record

    def update_status(
        self,
        record: DatasetFormatVersion,
        *,
        status: DatasetFormatStatus,
        path: str | None = None,
        checksum: str | None = None,
        file_size: int | None = None,
        error_message: str | None = None,
        mark_started: bool = False,
        mark_finished: bool = False,
        logs_path: str | None = None,
    ) -> DatasetFormatVersion:
        now = datetime.utcnow()
        record.status = status
        if path is not None:
            record.path = path
        if checksum is not None:
            record.checksum_sha256 = checksum
        if file_size is not None:
            record.file_size_bytes = file_size
        if error_message is not None:
            record.error_message = error_message
        if logs_path is not None:
            record.logs_path = logs_path
        if mark_started:
            record.started_at = now
        if mark_finished:
            record.finished_at = now
        record.updated_at = now
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)
        return record
