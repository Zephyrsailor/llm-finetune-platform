"""Evaluation feedback API integration tests."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.tests.test_datasets import (
    _auth_header,
    _create_user,
    _create_workspace_via_api,
)
from backend.tests.test_evaluations import _create_dataset_and_version
from app.core.config import settings

pytest_plugins = ["backend.tests.test_datasets"]


def _create_completed_evaluation(
    test_client: TestClient,
    engine: Session,
    owner,
    workspace,
) -> dict:
    dataset_version_id = _create_dataset_and_version(test_client, engine, owner, workspace)
    templates_resp = test_client.get(
        "/api/v1/evaluations/templates",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert templates_resp.status_code == 200, templates_resp.text
    template_id = templates_resp.json()[0]["id"]

    job_resp = test_client.post(
        "/api/v1/evaluations/jobs",
        data={
            "workspace_id": str(workspace.id),
            "evaluation_template_id": str(template_id),
            "dataset_version_id": str(dataset_version_id),
        },
        headers=_auth_header(owner),
    )
    assert job_resp.status_code == 201, job_resp.text

    jobs_resp = test_client.get(
        "/api/v1/evaluations/jobs",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert jobs_resp.status_code == 200, jobs_resp.text
    data = jobs_resp.json()
    assert data, "评估任务应已生成"
    return data[0]


def test_feedback_crud_and_export(client):
    test_client, engine = client
    owner = _create_user(engine, "feedback-owner@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Feedback Lab")

    evaluation_job = _create_completed_evaluation(test_client, engine, owner, workspace)
    job_id = evaluation_job["id"]

    # 初始列表为空
    list_resp = test_client.get(
        f"/api/v1/evaluations/jobs/{job_id}/feedback",
        headers=_auth_header(owner),
    )
    assert list_resp.status_code == 200, list_resp.text
    assert list_resp.json() == []

    # 创建评论
    comment_resp = test_client.post(
        f"/api/v1/evaluations/jobs/{job_id}/feedback",
        json={
            "workspace_id": workspace.id,
            "kind": "comment",
            "body": "报告整体表现良好。",
            "tags": ["summary"],
        },
        headers=_auth_header(owner),
    )
    assert comment_resp.status_code == 201, comment_resp.text
    comment_id = comment_resp.json()["id"]

    # 创建 TODO
    todo_resp = test_client.post(
        f"/api/v1/evaluations/jobs/{job_id}/feedback",
        json={
            "workspace_id": workspace.id,
            "kind": "todo",
            "body": "针对知识问答低准确率场景补充更多 FAQ 语料。",
            "tags": ["action", "faq"],
        },
        headers=_auth_header(owner),
    )
    assert todo_resp.status_code == 201, todo_resp.text
    todo_id = todo_resp.json()["id"]

    # 创建业务指标
    metric_resp = test_client.post(
        f"/api/v1/evaluations/jobs/{job_id}/feedback",
        json={
            "workspace_id": workspace.id,
            "kind": "business_metric",
            "body": "上线目标：客服首响满意度 ≥ 4.3。",
            "metric_name": "csat_target",
            "metric_value": 4.3,
            "tags": ["business"],
        },
        headers=_auth_header(owner),
    )
    assert metric_resp.status_code == 201, metric_resp.text

    # 列表应包含 3 条
    list_resp = test_client.get(
        f"/api/v1/evaluations/jobs/{job_id}/feedback",
        headers=_auth_header(owner),
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 3

    # 训练反馈摘要应包含 TODO
    summary_resp = test_client.get(
        "/api/v1/training/feedback-summaries",
        params={"workspace_id": workspace.id, "project_id": evaluation_job["project_id"]},
        headers=_auth_header(owner),
    )
    assert summary_resp.status_code == 200, summary_resp.text
    summary_payload = summary_resp.json()
    assert summary_payload["workspace_id"] == workspace.id
    assert len(summary_payload["items"]) == 1
    assert summary_payload["items"][0]["id"] == todo_id

    # 标记 TODO 为完成
    update_resp = test_client.patch(
        f"/api/v1/evaluations/jobs/{job_id}/feedback/{todo_id}",
        json={"status": "resolved"},
        headers=_auth_header(owner),
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["status"] == "resolved"
    assert update_resp.json()["resolved_at"] is not None

    # 训练摘要应为空
    summary_resp = test_client.get(
        "/api/v1/training/feedback-summaries",
        params={"workspace_id": workspace.id, "project_id": evaluation_job["project_id"]},
        headers=_auth_header(owner),
    )
    assert summary_resp.status_code == 200
    assert summary_resp.json()["items"] == []

    # 导出知识库（JSON）
    export_resp = test_client.post(
        f"/api/v1/evaluations/jobs/{job_id}/feedback:export",
        params={"format": "json"},
        headers=_auth_header(owner),
    )
    assert export_resp.status_code == 200, export_resp.text
    export_payload = export_resp.json()
    knowledge_path = Path(settings.workspace_storage_root).expanduser() / export_payload["path"]
    assert knowledge_path.exists()
    exported_data = json.loads(knowledge_path.read_text(encoding="utf-8"))
    assert len(exported_data) == 3

    # 删除评论
    delete_resp = test_client.delete(
        f"/api/v1/evaluations/jobs/{job_id}/feedback/{comment_id}",
        headers=_auth_header(owner),
    )
    assert delete_resp.status_code == 204, delete_resp.text

    remaining_resp = test_client.get(
        f"/api/v1/evaluations/jobs/{job_id}/feedback",
        headers=_auth_header(owner),
    )
    assert remaining_resp.status_code == 200
    remaining_ids = {item["id"] for item in remaining_resp.json()}
    assert comment_id not in remaining_ids
