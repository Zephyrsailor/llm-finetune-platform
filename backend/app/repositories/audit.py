"""Audit log repository."""

from typing import Sequence

from sqlmodel import Session, select

from app.models import AuditLog


class AuditLogRepository:
    """Provide persistence helpers for audit trail entries."""

    def __init__(self, session: Session):
        self._session = session

    def list_recent(self, *, limit: int | None = None) -> Sequence[AuditLog]:
        """Return recent audit events ordered by recency."""
        statement = select(AuditLog).order_by(AuditLog.created_at.desc())
        if limit is not None:
            statement = statement.limit(limit)
        result = self._session.exec(statement)
        return tuple(result.all())

    def list_for_workspace(self, workspace_id: int, *, limit: int | None = None) -> Sequence[AuditLog]:
        """Return recent audit events tagged with the given workspace id."""
        events = self.list_recent(limit=limit)
        return tuple(event for event in events if self._matches_workspace(event, workspace_id))

    def record(
        self,
        *,
        event_type: str,
        user_id: int | None,
        ip_address: str | None,
        user_agent: str | None,
        payload: dict | None = None,
    ) -> AuditLog:
        """Create an audit log entry."""
        entry = AuditLog(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload=payload or {},
        )
        self._session.add(entry)
        self._session.commit()
        self._session.refresh(entry)
        return entry

    @staticmethod
    def _matches_workspace(event: AuditLog, workspace_id: int) -> bool:
        payload = event.payload or {}
        if isinstance(payload, dict):
            value = payload.get("workspace_id")
            try:
                return int(value) == workspace_id
            except (TypeError, ValueError):
                return False
        return False
