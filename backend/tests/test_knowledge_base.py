"""Knowledge base API integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.tests.test_datasets import (
    _auth_header,
    _create_user,
    _create_workspace_via_api,
)
from backend.tests.test_governance_collaboration import _bootstrap_comment_entities
from app.core.config import settings
from app.models import WorkspaceMember
from app.repositories.role import RoleRepository

pytest_plugins = ["backend.tests.test_datasets"]


def test_knowledge_entry_document_and_version(client: Tuple[TestClient, Session]) -> None:
    test_client, engine = client
    owner = _create_user(engine, "kb-owner@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Knowledge Lab")

    create_resp = test_client.post(
        "/api/v1/knowledge/entries",
        json={
            "workspace_id": workspace.id,
            "entry_type": "document",
            "title": "上线检查清单",
            "description": "部署前需要确认的事项",
            "tags": ["deployment", "checklist"],
            "content": "# 部署检查\n- 验证模型版本\n- 通知运维",
        },
        headers=_auth_header(owner),
    )
    assert create_resp.status_code == 201, create_resp.text
    detail = create_resp.json()
    entry_id = detail["entry"]["id"]
    assert detail["entry"]["latest_version"] == 1
    assert detail["versions"][0]["version"] == 1

    version_resp = test_client.post(
        f"/api/v1/knowledge/entries/{entry_id}/versions",
        json={
            "summary": "增加灰度发布步骤",
            "content": "# 部署检查\n- 验证模型版本\n- 通知运维\n- 启动灰度",
        },
        headers=_auth_header(owner),
    )
    assert version_resp.status_code == 200, version_resp.text
    version_payload = version_resp.json()
    assert version_payload["entry"]["latest_version"] == 2
    assert len(version_payload["versions"]) == 2

    list_resp = test_client.get(
        "/api/v1/knowledge/entries",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert list_resp.status_code == 200
    entries = list_resp.json()
    assert any(item["id"] == entry_id for item in entries)

    storage_root = Path(settings.workspace_storage_root).expanduser()
    stored_files = list(storage_root.rglob("entry-*/v*.md"))
    assert stored_files, "文档版本应写入存储目录"


def test_knowledge_template_clone_flow(client: Tuple[TestClient, Session]) -> None:
    test_client, engine = client
    owner = _create_user(engine, "kb-template-owner@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Template Lab")
    dataset_version_id, training_job_id = _bootstrap_comment_entities(engine, workspace.id, owner.id)

    with Session(engine) as session:
        reviewer = _create_user(engine, "kb-reviewer@example.com")
        session.add(WorkspaceMember(workspace_id=workspace.id, user_id=reviewer.id, role="member"))
        role_repo = RoleRepository(session)
        reviewer_role = role_repo.get_by_key(workspace.id, "business-reviewer")
        if reviewer_role is not None:
            role_repo.set_member_roles(workspace_id=workspace.id, user_id=reviewer.id, role_ids=[reviewer_role.id])
        session.commit()

    template_payload = {
        "base_model": "llama-3-8b",
        "epochs": 3,
        "learning_rate": 2e-5,
    }
    template_resp = test_client.post(
        "/api/v1/knowledge/entries",
        json={
            "workspace_id": workspace.id,
            "entry_type": "training_template",
            "title": "中文客服微调模板",
            "description": "适用于客服场景的微调超参",
            "tags": ["training", "customer-service"],
            "config_snapshot": template_payload,
        },
        headers=_auth_header(owner),
    )
    assert template_resp.status_code == 201, template_resp.text
    template_entry_id = template_resp.json()["entry"]["id"]

    project_resp = test_client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        json={"name": "Retail Pilot", "description": "零售行业试点"},
        headers=_auth_header(owner),
    )
    assert project_resp.status_code == 201, project_resp.text
    created_paths = project_resp.json()["created_paths"]
    assert created_paths
    target_project_id = next(
        project["id"]
        for project in project_resp.json()["workspace"]["projects"]
        if project["name"] == "Retail Pilot"
    )

    clone_resp = test_client.post(
        f"/api/v1/knowledge/entries/{template_entry_id}/clone",
        json={"target_project_id": target_project_id, "title": "零售客服模板"},
        headers=_auth_header(owner),
    )
    assert clone_resp.status_code == 200, clone_resp.text
    clone_payload = clone_resp.json()
    assert clone_payload["entry"]["project_id"] == target_project_id
    assert clone_payload["entry"]["title"] == "零售客服模板"
    assert clone_payload["versions"][0]["config_snapshot"] == template_payload

    storage_root = Path(settings.workspace_storage_root).expanduser()
    clone_files = list(storage_root.rglob("knowledge/library/entry-*/v1.json"))
    assert clone_files, "模板克隆后应生成 JSON 存档"
    data = json.loads(clone_files[0].read_text(encoding="utf-8"))
    assert data == template_payload
