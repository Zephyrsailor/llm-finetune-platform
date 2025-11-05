"""Notification center API tests."""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta
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
from app.models import NotificationDeliveryStatus, WorkspaceMember
from app.repositories.role import RoleRepository

pytest_plugins = ["backend.tests.test_datasets"]


def test_notification_channels_and_events_flow(client: Tuple[TestClient, Session]) -> None:
    test_client, engine = client
    owner = _create_user(engine, "notify-owner@example.com")
    reviewer = _create_user(engine, "notify-reviewer@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Notify Lab")
    dataset_version_id, training_job_id = _bootstrap_comment_entities(engine, workspace.id, owner.id)

    with Session(engine) as session:
        session.add(WorkspaceMember(workspace_id=workspace.id, user_id=reviewer.id, role="member"))
        role_repo = RoleRepository(session)
        reviewer_role = role_repo.get_by_key(workspace.id, "business-reviewer")
        assert reviewer_role is not None
        role_repo.set_member_roles(
            workspace_id=workspace.id,
            user_id=reviewer.id,
            role_ids=[reviewer_role.id],
        )
        session.commit()

    email_spool = Path("tmp/test_notification_email")
    if email_spool.exists():
        shutil.rmtree(email_spool)

    channel_resp = test_client.post(
        "/api/v1/notifications/channels",
        json={
            "workspace_id": workspace.id,
            "name": "Email Mentions",
            "channel_type": "email",
            "event_types": ["governance.comment.created", "governance.comment.mention"],
            "config": {
                "recipients": ["reviewer@example.com"],
                "sender": "bot@example.com",
                "subject": "事件提醒",
                "spool_dir": str(email_spool),
            },
        },
        headers=_auth_header(owner),
    )
    assert channel_resp.status_code == 201, channel_resp.text
    email_channel_id = channel_resp.json()["id"]
    assert email_channel_id

    comment_resp = test_client.post(
        "/api/v1/governance/comments",
        json={
            "workspace_id": workspace.id,
            "entity_type": "dataset_version",
            "entity_id": dataset_version_id,
            "body": "请确认样本质量。",
            "mentions": [reviewer.id],
            "attachments": [],
            "context": "notify-test",
        },
        headers=_auth_header(owner),
    )
    assert comment_resp.status_code == 201, comment_resp.text

    events_resp = test_client.get(
        "/api/v1/notifications/events",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert events_resp.status_code == 200, events_resp.text
    events = events_resp.json()
    assert any(item["channel_id"] == email_channel_id for item in events)
    assert all(item["status"] == NotificationDeliveryStatus.SENT.value for item in events if item["channel_id"] == email_channel_id)

    spool_files = list(email_spool.glob("*.eml"))
    assert spool_files, "Email 渠道应生成本地邮件文件"

    webhook_resp = test_client.post(
        "/api/v1/notifications/channels",
        json={
            "workspace_id": workspace.id,
            "name": "Webhook Approvals",
            "channel_type": "webhook",
            "event_types": ["governance.approval.requested", "governance.approval.completed"],
            "config": {
                "url": "http://127.0.0.1:1/notify",
            },
        },
        headers=_auth_header(owner),
    )
    assert webhook_resp.status_code == 201, webhook_resp.text
    webhook_channel_id = webhook_resp.json()["id"]

    approval_resp = test_client.post(
        "/api/v1/governance/approvals",
        json={
            "workspace_id": workspace.id,
            "entity_type": "training_job",
            "entity_id": training_job_id,
            "title": "训练审批",
            "description": "请审阅训练结果",
            "approver_ids": [reviewer.id],
            "due_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        },
        headers=_auth_header(owner),
    )
    assert approval_resp.status_code == 201, approval_resp.text

    events_resp = test_client.get(
        "/api/v1/notifications/events",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert events_resp.status_code == 200, events_resp.text
    events = events_resp.json()
    failed_event = next(
        item
        for item in events
        if item["channel_id"] == webhook_channel_id and item["status"] == NotificationDeliveryStatus.FAILED.value
    )
    failed_event_id = failed_event["id"]

    webhook_log = (Path.cwd() / "tmp" / "notification_webhook.log").resolve()
    if webhook_log.exists():
        webhook_log.unlink()

    update_resp = test_client.patch(
        f"/api/v1/notifications/channels/{webhook_channel_id}",
        json={
            "config": {
                "url": f"file://{webhook_log}",
            }
        },
        headers=_auth_header(owner),
    )
    assert update_resp.status_code == 200, update_resp.text

    retry_resp = test_client.post(
        f"/api/v1/notifications/events/{failed_event_id}/retry",
        headers=_auth_header(owner),
    )
    assert retry_resp.status_code == 200, retry_resp.text
    retry_payload = retry_resp.json()
    assert retry_payload["status"] == NotificationDeliveryStatus.SENT.value

    assert webhook_log.exists()
    assert webhook_log.read_text(encoding="utf-8").strip() != ""
