"""Repositories for dataset cleaning templates and assignments."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlalchemy import delete, select
from sqlmodel import Session

from app.models import DatasetCleaningAssignment, DatasetCleaningTemplate


class DatasetCleaningTemplateRepository:
    """Manage persistence for cleaning templates."""

    def __init__(self, session: Session):
        self._session = session

    def create(
        self,
        *,
        workspace_id: int,
        name: str,
        description: str | None,
        steps: list[dict],
        is_active: bool = True,
    ) -> DatasetCleaningTemplate:
        now = datetime.utcnow()
        template = DatasetCleaningTemplate(
            workspace_id=workspace_id,
            name=name,
            description=description,
            steps=steps,
            is_active=is_active,
            created_at=now,
            updated_at=now,
        )
        self._session.add(template)
        self._session.flush()
        self._session.refresh(template)
        return template

    def list_by_workspace(self, workspace_id: int, *, active_only: bool = False) -> Sequence[DatasetCleaningTemplate]:
        statement = select(DatasetCleaningTemplate).where(DatasetCleaningTemplate.workspace_id == workspace_id)
        if active_only:
            statement = statement.where(DatasetCleaningTemplate.is_active.is_(True))
        statement = statement.order_by(DatasetCleaningTemplate.created_at.desc())
        return tuple(self._session.exec(statement).scalars().all())

    def get(self, template_id: int) -> DatasetCleaningTemplate | None:
        return self._session.get(DatasetCleaningTemplate, template_id)

    def update(
        self,
        template: DatasetCleaningTemplate,
        *,
        name: str | None = None,
        description: str | None = None,
        steps: list[dict] | None = None,
        is_active: bool | None = None,
    ) -> DatasetCleaningTemplate:
        if name is not None:
            template.name = name
        if description is not None:
            template.description = description
        if steps is not None:
            template.steps = steps
            template.version += 1
        if is_active is not None:
            template.is_active = is_active
        template.updated_at = datetime.utcnow()
        self._session.add(template)
        self._session.flush()
        self._session.refresh(template)
        return template

    def delete(self, template_id: int) -> None:
        statement = delete(DatasetCleaningTemplate).where(DatasetCleaningTemplate.id == template_id)
        self._session.exec(statement)
        self._session.flush()


class DatasetCleaningAssignmentRepository:
    """Manage dataset to template assignments."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, dataset_id: int) -> DatasetCleaningAssignment | None:
        return self._session.get(DatasetCleaningAssignment, dataset_id)

    def upsert(self, *, dataset_id: int, template_id: int, enabled: bool) -> DatasetCleaningAssignment:
        assignment = self.get(dataset_id)
        if assignment is None:
            assignment = DatasetCleaningAssignment(dataset_id=dataset_id, template_id=template_id, enabled=enabled)
        else:
            assignment.template_id = template_id
            assignment.enabled = enabled
            assignment.assigned_at = datetime.utcnow()
        self._session.add(assignment)
        self._session.flush()
        self._session.refresh(assignment)
        return assignment

    def disable(self, dataset_id: int) -> None:
        assignment = self.get(dataset_id)
        if assignment is None:
            return
        assignment.enabled = False
        assignment.assigned_at = datetime.utcnow()
        self._session.add(assignment)
        self._session.flush()
