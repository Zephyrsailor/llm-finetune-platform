import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";

import {
  ProjectCreateResponse,
  RoleMatrix,
  RoleOperationValue,
  RoleSummary,
  WorkspaceDetail,
  workspaceApi
} from "../../lib/api";

type Feedback = { type: "success" | "error"; text: string };

interface CreateWorkspaceForm {
  name: string;
  description?: string;
  plan?: string;
}

interface ProjectForm {
  name: string;
  description?: string;
}

function StatusBadge({ status }: { status: string }) {
  const label = status === "archived" ? "已归档" : "启用中";
  const color = status === "archived" ? "bg-red-500/20 text-red-300" : "bg-emerald-500/20 text-emerald-300";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>{label}</span>;
}

export function WorkspacesPage() {
  const [workspaces, setWorkspaces] = useState<WorkspaceDetail[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<Feedback | null>(null);
  const [projectFeedback, setProjectFeedback] = useState<Feedback | null>(null);
  const [roleMatrix, setRoleMatrix] = useState<RoleMatrix | null>(null);
  const [roleLoading, setRoleLoading] = useState(false);
  const [roleError, setRoleError] = useState<string | null>(null);
  const [roleActionFeedback, setRoleActionFeedback] = useState<Feedback | null>(null);
  const [assigningMemberId, setAssigningMemberId] = useState<number | null>(null);
  const [newRoleName, setNewRoleName] = useState("");
  const [newRoleDescription, setNewRoleDescription] = useState("");
  const [newRoleOperations, setNewRoleOperations] = useState<RoleOperationValue[]>([]);
  const [creatingRole, setCreatingRole] = useState(false);
  const [editingRole, setEditingRole] = useState<RoleSummary | null>(null);
  const [editingRoleName, setEditingRoleName] = useState("");
  const [editingRoleDescription, setEditingRoleDescription] = useState("");
  const [editingRoleOperations, setEditingRoleOperations] = useState<RoleOperationValue[]>([]);
  const [updatingRoleId, setUpdatingRoleId] = useState<number | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { isSubmitting: creatingWorkspace }
  } = useForm<CreateWorkspaceForm>();

  const {
    register: registerProject,
    handleSubmit: handleProjectSubmit,
    reset: resetProjectForm,
    formState: { isSubmitting: creatingProject }
  } = useForm<ProjectForm>();

  const fetchRoleMatrix = useCallback(
    async (workspaceId: number) => {
      setRoleLoading(true);
      setRoleError(null);
      try {
        const data = await workspaceApi.getRoleMatrix(workspaceId);
        setRoleMatrix(data);
      } catch (error) {
        setRoleError((error as Error).message);
        setRoleMatrix(null);
      } finally {
        setRoleLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    async function loadWorkspaces() {
      try {
        const data = await workspaceApi.list();
        setWorkspaces(data);
        if (data.length > 0) {
          setSelectedId(data[0].id);
        }
      } catch (error) {
        setLoadError((error as Error).message);
      } finally {
        setLoading(false);
      }
    }
    loadWorkspaces();
  }, []);

  const selectedWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === selectedId) ?? null,
    [workspaces, selectedId]
  );

  useEffect(() => {
    if (!selectedWorkspace) {
      setRoleMatrix(null);
      setRoleError(null);
      setRoleActionFeedback(null);
      return;
    }
    setRoleActionFeedback(null);
    setEditingRole(null);
    setEditingRoleName("");
    setEditingRoleDescription("");
    setEditingRoleOperations([]);
    setNewRoleName("");
    setNewRoleDescription("");
    setNewRoleOperations([]);
    fetchRoleMatrix(selectedWorkspace.id);
  }, [fetchRoleMatrix, selectedWorkspace?.id]);

  const operationLabelMap = useMemo(() => {
    if (!roleMatrix) {
      return new Map<RoleOperationValue, string>();
    }
    return new Map(roleMatrix.operations.map((operation) => [operation.value, operation.label]));
  }, [roleMatrix]);

  const memberAssignments = useMemo(() => {
    const map = new Map<number, number[]>();
    roleMatrix?.assignments.forEach((assignment) => map.set(assignment.user_id, assignment.role_ids));
    return map;
  }, [roleMatrix]);

  const roleLookup = useMemo(() => {
    const map = new Map<number, RoleSummary>();
    roleMatrix?.roles.forEach((role) => map.set(role.id, role));
    return map;
  }, [roleMatrix]);

  const formatOperations = useCallback(
    (operations: RoleOperationValue[]) =>
      operations.length === 0
        ? "无"
        : operations.map((operation) => operationLabelMap.get(operation) ?? operation).join("、"),
    [operationLabelMap]
  );

  const toggleNewRoleOperation = (operation: RoleOperationValue) => {
    setNewRoleOperations((prev) =>
      prev.includes(operation) ? prev.filter((value) => value !== operation) : [...prev, operation]
    );
  };

  const toggleEditingRoleOperation = (operation: RoleOperationValue) => {
    setEditingRoleOperations((prev) =>
      prev.includes(operation) ? prev.filter((value) => value !== operation) : [...prev, operation]
    );
  };

  const startEditingRole = (role: RoleSummary) => {
    setRoleActionFeedback(null);
    setEditingRole(role);
    setEditingRoleName(role.name);
    setEditingRoleDescription(role.description ?? "");
    setEditingRoleOperations([...role.operations]);
  };

  const cancelEditingRole = () => {
    setEditingRole(null);
    setEditingRoleName("");
    setEditingRoleDescription("");
    setEditingRoleOperations([]);
  };

  const handleCreateRole = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedWorkspace) {
      return;
    }
    const trimmedName = newRoleName.trim();
    if (!trimmedName) {
      setRoleActionFeedback({ type: "error", text: "请填写角色名称" });
      return;
    }
    if (newRoleOperations.length === 0) {
      setRoleActionFeedback({ type: "error", text: "请选择至少一个权限操作" });
      return;
    }
    setCreatingRole(true);
    setRoleActionFeedback(null);
    try {
      await workspaceApi.createRole(selectedWorkspace.id, {
        name: trimmedName,
        description: newRoleDescription.trim() ? newRoleDescription.trim() : null,
        operations: newRoleOperations
      });
      setRoleActionFeedback({ type: "success", text: "角色创建成功" });
      setNewRoleName("");
      setNewRoleDescription("");
      setNewRoleOperations([]);
      await fetchRoleMatrix(selectedWorkspace.id);
    } catch (error) {
      setRoleActionFeedback({ type: "error", text: (error as Error).message });
    } finally {
      setCreatingRole(false);
    }
  };

  const handleUpdateRole = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedWorkspace || !editingRole) {
      return;
    }
    const trimmedName = editingRoleName.trim();
    if (!trimmedName) {
      setRoleActionFeedback({ type: "error", text: "角色名称不能为空" });
      return;
    }
    if (editingRoleOperations.length === 0) {
      setRoleActionFeedback({ type: "error", text: "请选择至少一个权限操作" });
      return;
    }
    setUpdatingRoleId(editingRole.id);
    setRoleActionFeedback(null);
    try {
      await workspaceApi.updateRole(selectedWorkspace.id, editingRole.id, {
        name: trimmedName,
        description: editingRoleDescription.trim() ? editingRoleDescription.trim() : null,
        operations: editingRoleOperations
      });
      setRoleActionFeedback({ type: "success", text: "角色已更新" });
      cancelEditingRole();
      await fetchRoleMatrix(selectedWorkspace.id);
    } catch (error) {
      setRoleActionFeedback({ type: "error", text: (error as Error).message });
    } finally {
      setUpdatingRoleId(null);
    }
  };

  const handleToggleMemberRole = async (userId: number, roleId: number) => {
    if (!selectedWorkspace || !roleMatrix) {
      return;
    }
    const current = memberAssignments.get(userId) ?? [];
    const next = new Set(current);
    if (next.has(roleId)) {
      next.delete(roleId);
    } else {
      next.add(roleId);
    }
    setAssigningMemberId(userId);
    setRoleActionFeedback(null);
    try {
      await workspaceApi.setMemberRoles(selectedWorkspace.id, userId, Array.from(next));
      setRoleActionFeedback({ type: "success", text: "成员角色已更新" });
      await fetchRoleMatrix(selectedWorkspace.id);
    } catch (error) {
      setRoleActionFeedback({ type: "error", text: (error as Error).message });
    } finally {
      setAssigningMemberId(null);
    }
  };

  const onCreateWorkspace = handleSubmit(async (values) => {
    setActionFeedback(null);
    try {
      const created = await workspaceApi.create({
        name: values.name,
        description: values.description ?? null,
        plan: values.plan ?? null
      });
      setWorkspaces((prev) => [created, ...prev.filter((w) => w.id !== created.id)]);
      setSelectedId(created.id);
      setActionFeedback({ type: "success", text: "工作空间创建成功" });
      reset();
    } catch (error) {
      setActionFeedback({ type: "error", text: (error as Error).message });
    }
  });

  const onToggleStatus = async (workspace: WorkspaceDetail) => {
    setActionFeedback(null);
    const nextStatus = workspace.status === "archived" ? "active" : "archived";
    try {
      const updated = await workspaceApi.update(workspace.id, { status: nextStatus });
      setWorkspaces((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setSelectedId(updated.id);
      setActionFeedback({
        type: "success",
        text: nextStatus === "archived" ? "工作空间已归档" : "工作空间已恢复"
      });
    } catch (error) {
      setActionFeedback({ type: "error", text: (error as Error).message });
    }
  };

  const onCreateProject = handleProjectSubmit(async (values) => {
    if (!selectedWorkspace) {
      return;
    }
    setProjectFeedback(null);
    try {
      const response: ProjectCreateResponse = await workspaceApi.createProject(selectedWorkspace.id, {
        name: values.name,
        description: values.description ?? null
      });
      setWorkspaces((prev) =>
        prev.map((item) => (item.id === response.workspace.id ? response.workspace : item))
      );
      setSelectedId(response.workspace.id);
      setProjectFeedback({
        type: "success",
        text: `默认目录已生成：${response.created_paths.join(", ")}`
      });
      resetProjectForm();
    } catch (error) {
      setProjectFeedback({ type: "error", text: (error as Error).message });
    }
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/60">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="text-xl font-semibold text-sky-400">工作空间与项目管理</h1>
            <p className="text-sm text-slate-400">创建隔离的工作空间并初始化项目模板。</p>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        {loading ? (
          <p className="text-sm text-slate-400">正在加载工作空间...</p>
        ) : loadError ? (
          <div className="rounded border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
            {loadError}
          </div>
        ) : (
          <div className="grid gap-6 lg:grid-cols-[340px,1fr]">
            <section className="space-y-6">
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow">
                <h2 className="text-lg font-semibold">创建新的工作空间</h2>
                <p className="mt-1 text-sm text-slate-400">
                  填写基本信息以初始化隔离的工作空间，后续可继续添加成员与项目。
                </p>
                <form className="mt-4 space-y-4" onSubmit={onCreateWorkspace}>
                  <div>
                    <label className="block text-sm font-medium text-slate-300" htmlFor="workspace-name">
                      名称
                    </label>
                    <input
                      id="workspace-name"
                      type="text"
                      className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/40"
                      placeholder="例如：客户A-交付工作空间"
                      required
                      {...register("name")}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300" htmlFor="workspace-plan">
                      套餐/计划
                    </label>
                    <input
                      id="workspace-plan"
                      type="text"
                      className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/40"
                      placeholder="standard / enterprise"
                      {...register("plan")}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300" htmlFor="workspace-description">
                      描述
                    </label>
                    <textarea
                      id="workspace-description"
                      className="mt-1 h-20 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/40"
                      placeholder="简要说明该工作空间的用途。"
                      {...register("description")}
                    />
                  </div>
                  {actionFeedback && (
                    <p
                      className={`rounded-md px-3 py-2 text-sm ${
                        actionFeedback.type === "success"
                          ? "bg-emerald-500/10 text-emerald-200"
                          : "bg-red-500/10 text-red-200"
                      }`}
                    >
                      {actionFeedback.text}
                    </p>
                  )}
                  <button
                    className="w-full rounded-md bg-sky-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
                    type="submit"
                    disabled={creatingWorkspace}
                  >
                    {creatingWorkspace ? "创建中..." : "创建工作空间"}
                  </button>
                </form>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow">
                <h2 className="text-lg font-semibold">工作空间列表</h2>
                <div className="mt-3 space-y-3">
                  {workspaces.length === 0 ? (
                    <p className="text-sm text-slate-400">当前还没有工作空间，创建后将显示在此处。</p>
                  ) : (
                    workspaces.map((workspace) => (
                      <button
                        key={workspace.id}
                        type="button"
                        onClick={() => setSelectedId(workspace.id)}
                        className={`w-full rounded-lg border px-3 py-3 text-left transition ${
                          selectedId === workspace.id
                            ? "border-sky-500/60 bg-sky-500/10"
                            : "border-slate-800 bg-slate-900/40 hover:border-slate-700"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-slate-100">{workspace.name}</span>
                          <StatusBadge status={workspace.status} />
                        </div>
                        <p className="mt-1 text-xs text-slate-400">
                          项目数量：{workspace.projects.length}，计划：{workspace.plan ?? "未指定"}
                        </p>
                      </button>
                    ))
                  )}
                </div>
              </div>
            </section>

            <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow">
              {selectedWorkspace ? (
                <div className="space-y-6">
                  <header className="flex items-start justify-between gap-4 border-b border-slate-800 pb-4">
                  <div>
                      <h2 className="text-xl font-semibold text-slate-50">{selectedWorkspace.name}</h2>
                      <p className="mt-1 text-sm text-slate-400">
                        创建于 {new Date(selectedWorkspace.created_at).toLocaleString()}，当前计划：
                        {selectedWorkspace.plan ?? "未指定"}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => onToggleStatus(selectedWorkspace)}
                      className="rounded-md border border-slate-700 px-3 py-1 text-xs font-semibold text-slate-200 transition hover:border-slate-500"
                    >
                      {selectedWorkspace.status === "archived" ? "恢复启用" : "归档工作空间"}
                    </button>
                  </header>

                  <div>
                    <h3 className="text-sm font-semibold text-slate-200">成员</h3>
                    <ul className="mt-2 space-y-2">
                      {selectedWorkspace.members.map((member) => {
                        const assignedRoles = memberAssignments.get(member.user_id) ?? [];
                        const assignedRoleNames = assignedRoles
                          .map((roleId) => roleLookup.get(roleId)?.name)
                          .filter((name): name is string => Boolean(name))
                          .join("、");
                        return (
                          <li
                            key={member.user_id}
                            className="rounded-md border border-slate-800 bg-slate-900/60 px-3 py-2 text-xs text-slate-300"
                          >
                            <span className="font-medium text-slate-100">{member.email}</span>
                            <span className="ml-2 text-slate-400">
                              {assignedRoleNames ? `角色：${assignedRoleNames}` : `角色：${member.role ?? "未分配"}`}
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                  </div>

                  <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-sm font-semibold text-slate-200">角色矩阵与权限配置</h3>
                        <p className="mt-1 text-xs text-slate-400">
                          管理角色定义与成员权限映射，角色变更即时生效并写入审计日志。
                        </p>
                      </div>
                      {roleLoading && <span className="text-xs text-slate-400">加载中...</span>}
                    </div>

                    {roleError ? (
                      <p className="mt-3 rounded-md border border-red-500/40 bg-red-500/10 p-3 text-xs text-red-200">
                        {roleError}
                      </p>
                    ) : roleMatrix ? (
                      <>
                        <div className="mt-3 overflow-x-auto">
                          <table className="min-w-full border-collapse text-xs text-slate-200">
                            <thead>
                              <tr>
                                <th className="border-b border-slate-800 px-3 py-2 text-left font-semibold text-slate-300">
                                  成员
                                </th>
                                {roleMatrix.roles.map((role) => (
                                  <th
                                    key={role.id}
                                    className="border-b border-slate-800 px-3 py-2 text-left align-top font-semibold text-slate-300"
                                  >
                                    <div className="flex flex-col gap-1">
                                      <div className="flex items-center gap-2">
                                        <span className="text-slate-100">{role.name}</span>
                                        {role.is_system ? (
                                          <span className="rounded-full bg-slate-700 px-2 py-0.5 text-[10px] text-slate-200">
                                            系统
                                          </span>
                                        ) : (
                                          <button
                                            type="button"
                                            onClick={() => startEditingRole(role)}
                                            className="text-[10px] text-sky-400 hover:text-sky-300"
                                          >
                                            编辑
                                          </button>
                                        )}
                                      </div>
                                      <span className="text-[10px] text-slate-400">
                                        {formatOperations(role.operations)}
                                      </span>
                                    </div>
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {selectedWorkspace.members.map((member) => {
                                const assignedRoles = memberAssignments.get(member.user_id) ?? [];
                                return (
                                  <tr key={member.user_id} className="border-b border-slate-900/60">
                                    <td className="border-b border-slate-800 px-3 py-2 text-slate-300">
                                      {member.email}
                                    </td>
                                    {roleMatrix.roles.map((role) => {
                                      const checked = assignedRoles.includes(role.id);
                                      return (
                                        <td key={role.id} className="border-b border-slate-800 px-3 py-2 text-center">
                                          <input
                                            type="checkbox"
                                            className="h-4 w-4 accent-sky-500"
                                            checked={checked}
                                            disabled={assigningMemberId === member.user_id || roleLoading}
                                            onChange={() => handleToggleMemberRole(member.user_id, role.id)}
                                            aria-label={`切换 ${member.email} 的 ${role.name} 角色`}
                                          />
                                        </td>
                                      );
                                    })}
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>

                        {editingRole && (
                          <form
                            className="mt-4 space-y-3 rounded-md border border-slate-800 bg-slate-900/60 p-4"
                            onSubmit={handleUpdateRole}
                          >
                            <div className="flex items-center justify-between">
                              <h4 className="text-xs font-semibold text-slate-200">
                                编辑角色：{editingRole.name}
                              </h4>
                              <button
                                type="button"
                                onClick={cancelEditingRole}
                                className="text-[10px] text-slate-400 hover:text-slate-200"
                              >
                                取消
                              </button>
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-slate-300" htmlFor="edit-role-name">
                                角色名称
                              </label>
                              <input
                                id="edit-role-name"
                                type="text"
                                value={editingRoleName}
                                onChange={(event) => setEditingRoleName(event.target.value)}
                                className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/40"
                                placeholder="请输入角色名称"
                              />
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-slate-300" htmlFor="edit-role-description">
                                描述
                              </label>
                              <textarea
                                id="edit-role-description"
                                value={editingRoleDescription}
                                onChange={(event) => setEditingRoleDescription(event.target.value)}
                                className="mt-1 h-16 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/40"
                                placeholder="描述该角色的职责"
                              />
                            </div>
                            <fieldset>
                              <legend className="text-xs font-medium text-slate-300">权限操作</legend>
                              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                                {roleMatrix.operations.map((operation) => (
                                  <label
                                    key={`edit-${operation.value}`}
                                    className="flex items-center gap-2 rounded border border-slate-800 bg-slate-900/60 px-3 py-2"
                                  >
                                    <input
                                      type="checkbox"
                                      className="h-4 w-4 accent-sky-500"
                                      checked={editingRoleOperations.includes(operation.value)}
                                      onChange={() => toggleEditingRoleOperation(operation.value)}
                                    />
                                    <span className="text-xs text-slate-200">{operation.label}</span>
                                  </label>
                                ))}
                              </div>
                            </fieldset>
                            <div className="flex items-center gap-3">
                              <button
                                type="submit"
                                className="rounded-md bg-sky-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
                                disabled={updatingRoleId === editingRole.id}
                              >
                                {updatingRoleId === editingRole.id ? "保存中..." : "保存修改"}
                              </button>
                              <button
                                type="button"
                                onClick={cancelEditingRole}
                                className="rounded-md border border-slate-700 px-3 py-2 text-xs text-slate-200 hover:border-slate-500"
                              >
                                取消
                              </button>
                            </div>
                          </form>
                        )}

                        <form
                          className="mt-4 space-y-3 rounded-md border border-slate-800 bg-slate-900/60 p-4"
                          onSubmit={handleCreateRole}
                        >
                          <h4 className="text-xs font-semibold text-slate-200">新增自定义角色</h4>
                          <div>
                            <label className="block text-xs font-medium text-slate-300" htmlFor="new-role-name">
                              角色名称
                            </label>
                            <input
                              id="new-role-name"
                              type="text"
                              value={newRoleName}
                              onChange={(event) => setNewRoleName(event.target.value)}
                              className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/40"
                              placeholder="例如：数据审阅者"
                              required
                            />
                          </div>
                          <div>
                            <label
                              className="block text-xs font-medium text-slate-300"
                              htmlFor="new-role-description"
                            >
                              描述
                            </label>
                            <textarea
                              id="new-role-description"
                              value={newRoleDescription}
                              onChange={(event) => setNewRoleDescription(event.target.value)}
                              className="mt-1 h-16 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/40"
                              placeholder="可选：描述该角色的适用场景。"
                            />
                          </div>
                          <fieldset>
                            <legend className="text-xs font-medium text-slate-300">权限操作</legend>
                            <div className="mt-2 grid gap-2 sm:grid-cols-2">
                              {roleMatrix.operations.map((operation) => (
                                <label
                                  key={operation.value}
                                  className="flex items-center gap-2 rounded border border-slate-800 bg-slate-900/60 px-3 py-2"
                                >
                                  <input
                                    type="checkbox"
                                    className="h-4 w-4 accent-sky-500"
                                    checked={newRoleOperations.includes(operation.value)}
                                    onChange={() => toggleNewRoleOperation(operation.value)}
                                  />
                                  <span className="text-xs text-slate-200">{operation.label}</span>
                                </label>
                              ))}
                            </div>
                          </fieldset>
                          <button
                            type="submit"
                            className="rounded-md bg-slate-800 px-3 py-2 text-xs font-semibold text-slate-100 transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={creatingRole}
                          >
                            {creatingRole ? "创建中..." : "创建角色"}
                          </button>
                        </form>
                      </>
                    ) : (
                      <p className="mt-3 text-xs text-slate-400">暂无角色数据。</p>
                    )}

                    {roleActionFeedback && (
                      <p
                        className={`mt-3 rounded-md px-3 py-2 text-xs ${
                          roleActionFeedback.type === "success"
                            ? "bg-emerald-500/10 text-emerald-200"
                            : "bg-red-500/10 text-red-200"
                        }`}
                      >
                        {roleActionFeedback.text}
                      </p>
                    )}
                  </div>

                  <div>
                    <h3 className="text-sm font-semibold text-slate-200">项目</h3>
                    {selectedWorkspace.projects.length === 0 ? (
                      <p className="mt-2 text-sm text-slate-400">尚未创建任何项目。</p>
                    ) : (
                      <div className="mt-2 space-y-2">
                        {selectedWorkspace.projects.map((project) => (
                          <div
                            key={project.id}
                            className="rounded-md border border-slate-800 bg-slate-900/60 px-3 py-2 text-sm text-slate-200"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-medium">{project.name}</span>
                              <StatusBadge status={project.status} />
                            </div>
                            <p className="mt-1 text-xs text-slate-400">
                              创建时间：{new Date(project.created_at).toLocaleString()}
                            </p>
                            {project.description && (
                              <p className="mt-1 text-xs text-slate-300">{project.description}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
                    <h3 className="text-sm font-semibold text-slate-200">在该工作空间下创建项目</h3>
                    <p className="mt-1 text-xs text-slate-400">
                      项目会自动生成默认目录结构和占位文档，便于团队快速启动。
                    </p>
                    <form className="mt-3 space-y-3" onSubmit={onCreateProject}>
                      <div>
                        <label className="block text-xs font-medium text-slate-300" htmlFor="project-name">
                          项目名称
                        </label>
                        <input
                          id="project-name"
                          type="text"
                          className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/40"
                          placeholder="例如：nlp-finetune-demo"
                          required
                          {...registerProject("name")}
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-slate-300" htmlFor="project-description">
                          简要描述
                        </label>
                        <textarea
                          id="project-description"
                          className="mt-1 h-16 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/40"
                          placeholder="可选：补充本项目的目标或数据来源。"
                          {...registerProject("description")}
                        />
                      </div>
                      {projectFeedback && (
                        <p
                          className={`rounded-md px-3 py-2 text-sm ${
                            projectFeedback.type === "success"
                              ? "bg-emerald-500/10 text-emerald-200"
                              : "bg-red-500/10 text-red-200"
                          }`}
                        >
                          {projectFeedback.text}
                        </p>
                      )}
                      <button
                        className="w-full rounded-md bg-slate-800 px-3 py-2 text-sm font-semibold text-slate-100 transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                        type="submit"
                        disabled={creatingProject}
                      >
                        {creatingProject ? "创建中..." : "创建项目并生成目录"}
                      </button>
                    </form>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-slate-400">请选择一个工作空间查看详情。</div>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
