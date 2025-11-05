#!/usr/bin/env python
"""Seed or preview workspace role matrix from a JSON manifest.

Manifest format example:
{
  "roles": [
    {
      "key": "custom-review",
      "name": "自定义审阅",
      "description": "可查看评估并参与审批",
      "operations": ["evaluation_view", "approval_manage"],
      "members": ["reviewer@example.com", "auditor@example.com"]
    }
  ]
}
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from sqlmodel import Session, select

if __name__ == "__main__" and __package__ is None:
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.database import engine
from app.models import User
from app.repositories.role import RoleRepository
from app.repositories.workspace import WorkspaceRepository
from app.services.role_management import RoleManagementService
from app.services.roles import RoleOperation
from app.services.errors import RoleConflictError, RoleNotFoundError


@dataclass(slots=True)
class ManifestRole:
    key: str | None
    name: str
    description: str | None
    operations: list[str]
    members: list[str]
    generated_key: str | None = field(default=None, init=False)


def load_manifest(path: Path) -> list[ManifestRole]:
    content = json.loads(path.read_text(encoding="utf-8"))
    roles = []
    for entry in content.get("roles", []):
        roles.append(
            ManifestRole(
                key=entry.get("key"),
                name=entry["name"],
                description=entry.get("description"),
                operations=list(entry.get("operations", [])),
                members=list(entry.get("members", [])),
            )
        )
    return roles


def ensure_operations_valid(operations: Iterable[str]) -> None:
    allowed = {operation.value for operation in RoleOperation}
    unknown = sorted(set(operations) - allowed)
    if unknown:
        raise ValueError(f"未知权限操作: {', '.join(unknown)}")


def resolve_user_ids(session: Session, emails: list[str]) -> dict[str, int]:
    if not emails:
        return {}
    statement = select(User).where(User.email.in_(emails))
    mapping: dict[str, int] = {}
    for user in session.exec(statement).all():
        mapping[user.email] = user.id
    missing = sorted(set(emails) - set(mapping))
    if missing:
        raise ValueError(f"以下成员邮箱不存在: {', '.join(missing)}")
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed workspace roles from manifest.")
    parser.add_argument("--workspace", type=int, required=True, help="Workspace ID to apply.")
    parser.add_argument("--file", type=Path, required=True, help="JSON manifest path.")
    parser.add_argument("--dry-run", action="store_true", help="Only print actions without persisting.")
    parser.add_argument(
        "--actor-email",
        type=str,
        default=None,
        help="Email of the user performing the operation (must have approval_manage). "
        "If omitted, script will attempt to auto-select a workspace-admin member.",
    )
    args = parser.parse_args()

    manifest_roles = load_manifest(args.file)
    if not manifest_roles:
        print("Manifest 未包含任何角色定义，跳过。")
        return 0

    with Session(engine) as session:
        workspace_repo = WorkspaceRepository(session)
        workspace = workspace_repo.get(args.workspace)
        if workspace is None:
            print(f"工作空间 {args.workspace} 不存在。", file=sys.stderr)
            return 1

        role_repo = RoleRepository(session)
        service = RoleManagementService(session)

        existing_roles = {role.key: role for role in role_repo.list_roles(args.workspace)}
        roles_by_name = {role.name.lower(): role for role in role_repo.list_roles(args.workspace)}
        members_snapshot = workspace_repo.list_members(args.workspace)
        if not members_snapshot:
            raise RuntimeError("工作空间尚无成员，无法确定执行操作的用户。")

        acting_user = None
        if args.actor_email:
            for _, user in members_snapshot:
                if user.email == args.actor_email:
                    acting_user = user
                    break
            if acting_user is None:
                available = ", ".join(sorted({user.email for _, user in members_snapshot}))
                raise RuntimeError(
                    f"指定的执行账号 {args.actor_email} 不在工作空间成员列表中。可用成员：{available}"
                )
        else:
            # Auto-select member who already has approval_manage via existing roles; fallback to workspace-admin owner.
            for member, user in members_snapshot:
                operations = role_repo.list_operations_for_member(workspace_id=args.workspace, user_id=user.id)
                if RoleOperation.APPROVAL_MANAGE.value in operations:
                    acting_user = user
                    break
            if acting_user is None:
                for member, user in members_snapshot:
                    if member.role == "owner":
                        acting_user = user
                        break
        if acting_user is None:
            raise RuntimeError(
                "无法找到具备 approval_manage 权限的执行账号，请使用 --actor-email 指定具体成员。"
            )
        user_map_cache: dict[str, int] = {}
        member_role_targets: dict[int, set[int]] = {}

        changes: list[str] = []

        for entry in manifest_roles:
            ensure_operations_valid(entry.operations)

            role = None
            matched_new = False
            if entry.key:
                role = existing_roles.get(entry.key)
            if role is None:
                role = roles_by_name.get(entry.name.lower())

            if role is not None:
                changes.append(f"[更新角色] {role.name} (key={role.key}) -> operations={entry.operations}")
                if not args.dry_run:
                    try:
                        service.update_role(
                            workspace_id=args.workspace,
                            role_id=role.id,
                            current_user=acting_user,
                            name=entry.name,
                            description=entry.description,
                            operations=entry.operations,
                            ip_address=None,
                            user_agent="roles_seed",
                        )
                    except (RoleConflictError, RoleNotFoundError) as exc:
                        raise RuntimeError(f"更新角色 {entry.name} 失败: {exc}") from exc
                role_id = role.id
            else:
                changes.append(f"[新增角色] {entry.name} (operations={entry.operations})")
                if args.dry_run:
                    role_id = -1
                    entry.generated_key = "<dry-run>"
                else:
                    result = service.create_role(
                        workspace_id=args.workspace,
                        current_user=acting_user,
                        name=entry.name,
                        description=entry.description,
                        operations=entry.operations,
                        ip_address=None,
                        user_agent="roles_seed",
                    )
                    role_id = result["id"]
                    entry.generated_key = result["key"]
                    persisted = role_repo.get(result["id"])
                    if persisted is not None:
                        existing_roles[persisted.key] = persisted
                        roles_by_name[persisted.name.lower()] = persisted
                matched_new = True

            if entry.members:
                missing_emails = [email for email in entry.members if email not in user_map_cache]
                if missing_emails:
                    user_map_cache.update(resolve_user_ids(session, missing_emails))

                member_ids = [user_map_cache[email] for email in entry.members]
                for member_id in member_ids:
                    target = member_role_targets.setdefault(member_id, set())
                    target.add(role_id)
                    changes.append(f"  - 将成员 {member_id} 追加角色 {entry.name}")

            if matched_new and entry.generated_key not in (None, "<dry-run>"):
                changes.append(f"    新角色 key: {entry.generated_key}（请更新 manifest）")

        if not args.dry_run and member_role_targets:
            matrix_snapshot = service.get_matrix(workspace_id=args.workspace, current_user=acting_user)
            current_roles_map = {
                assignment["user_id"]: set(assignment["role_ids"])
                for assignment in matrix_snapshot["assignments"]
            }
            for member_id, additional_roles in member_role_targets.items():
                existing_role_ids = current_roles_map.get(member_id, set())
                combined = sorted(existing_role_ids | {role_id for role_id in additional_roles if role_id != -1})
                if combined == sorted(existing_role_ids):
                    continue
                service.set_member_roles(
                    workspace_id=args.workspace,
                    target_user_id=member_id,
                    role_ids=combined,
                    current_user=acting_user,
                    ip_address=None,
                    user_agent="roles_seed",
                )

        print("变更计划：")
        for line in changes:
            print(line)
        if args.dry_run:
            print("\nDRY RUN 完成，未写入数据库。")
        else:
            session.commit()
            print("\n角色矩阵已更新。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
