import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  trainingSnapshotApi,
  TrainingSnapshot,
  TrainingRun,
  workspaceApi,
  WorkspaceDetail
} from "../../lib/api";
import { TrainingNav } from "./TrainingNav";
import { AppShell } from "../layout/AppShell";

const triggerLabels: Record<string, string> = {
  scheduled: "周期快照",
  metric: "指标触发",
  manual: "手动保存"
};

function formatDate(value: string | undefined | null): string {
  if (!value) {
    return "—";
  }
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function TrainingSnapshotsPage() {
  const queryClient = useQueryClient();
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<number | null>(null);
  const [operationNotes, setOperationNotes] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);

  const workspaceQuery = useQuery<WorkspaceDetail[]>({
    queryKey: ["workspaces"],
    queryFn: () => workspaceApi.list(),
    staleTime: 60_000
  });

  useEffect(() => {
    if (workspaceQuery.data && workspaceQuery.data.length > 0 && selectedWorkspaceId == null) {
      setSelectedWorkspaceId(workspaceQuery.data[0].id);
    }
  }, [workspaceQuery.data, selectedWorkspaceId]);

  const snapshotsQuery = useQuery<TrainingSnapshot[]>({
    queryKey: ["training-snapshots", selectedWorkspaceId],
    enabled: selectedWorkspaceId != null,
    queryFn: () => trainingSnapshotApi.list({ workspaceId: selectedWorkspaceId ?? undefined }),
    refetchInterval: 20_000
  });

  useEffect(() => {
    const snapshots = snapshotsQuery.data;
    if (!snapshots || snapshots.length === 0) {
      setSelectedSnapshotId(null);
      return;
    }
    if (selectedSnapshotId == null || !snapshots.some((snapshot) => snapshot.id === selectedSnapshotId)) {
      setSelectedSnapshotId(snapshots[0].id);
    }
  }, [snapshotsQuery.data, selectedSnapshotId]);

  const selectedSnapshot = useMemo(
    () => snapshotsQuery.data?.find((snapshot) => snapshot.id === selectedSnapshotId) ?? null,
    [snapshotsQuery.data, selectedSnapshotId]
  );

  const resumeMutation = useMutation({
    mutationFn: ({ snapshotId, notes }: { snapshotId: number; notes?: string }) =>
      trainingSnapshotApi.resume(snapshotId, notes ? { notes } : undefined),
    onSuccess: (run: TrainingRun) => {
      setFeedback(`已触发断点续训，运行 #${run.id} 已排队执行。`);
      queryClient.invalidateQueries({ queryKey: ["training-snapshots", selectedWorkspaceId] });
    },
    onError: (error: Error) => {
      setFeedback(`续训失败：${error.message}`);
    }
  });

  const rollbackMutation = useMutation({
    mutationFn: ({ snapshotId, reason }: { snapshotId: number; reason?: string }) =>
      trainingSnapshotApi.rollback(snapshotId, reason ? { reason } : undefined),
    onSuccess: (snapshot: TrainingSnapshot) => {
      setFeedback(`已回滚到快照 #${snapshot.id}，建议重新评估模型表现。`);
      queryClient.invalidateQueries({ queryKey: ["training-snapshots", selectedWorkspaceId] });
    },
    onError: (error: Error) => {
      setFeedback(`回滚失败：${error.message}`);
    }
  });

  const workspaceOptions = workspaceQuery.data ?? [];
  const snapshots = snapshotsQuery.data ?? [];

  const handleResume = () => {
    if (!selectedSnapshot || resumeMutation.isPending) {
      return;
    }
    resumeMutation.mutate({
      snapshotId: selectedSnapshot.id,
      notes: operationNotes.trim() || undefined
    });
  };

  const handleRollback = () => {
    if (!selectedSnapshot || rollbackMutation.isPending) {
      return;
    }
    rollbackMutation.mutate({
      snapshotId: selectedSnapshot.id,
      reason: operationNotes.trim() || undefined
    });
  };

  const toolbar = (
    <div className="mx-auto w-full max-w-7xl px-8 py-3">
      <TrainingNav />
    </div>
  );

  return (
    <AppShell
      title="训练快照管理"
      subtitle="查看训练快照、发起断点续训或一键回滚。"
      searchPlaceholder="搜索快照或运行"
      toolbar={toolbar}
    >
      {feedback ? (
        <div
          className={`rounded-md border px-4 py-3 text-sm ${
            feedback.includes("失败")
              ? "border-rose-200 bg-rose-50 text-rose-700"
              : "border-emerald-200 bg-emerald-50 text-emerald-700"
          }`}
        >
          {feedback}
        </div>
      ) : null}

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor="workspace-select">
          工作空间
        </label>
        <select
          id="workspace-select"
          className="mt-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
          value={selectedWorkspaceId ?? ""}
          onChange={(event) => {
            const workspaceId = Number(event.target.value);
            setSelectedWorkspaceId(Number.isNaN(workspaceId) ? null : workspaceId);
            setSelectedSnapshotId(null);
          }}
        >
          {workspaceOptions.map((workspace) => (
            <option key={workspace.id} value={workspace.id}>
              {workspace.name}
            </option>
          ))}
        </select>
        {workspaceQuery.isLoading ? <p className="mt-3 text-sm text-slate-500">正在加载工作空间...</p> : null}
        {workspaceOptions.length === 0 && !workspaceQuery.isLoading ? (
          <p className="mt-3 text-sm text-slate-500">尚未创建任何工作空间，请先在工作空间模块完成配置。</p>
        ) : null}
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">快照列表</h2>
            {snapshotsQuery.isFetching ? <span className="text-xs text-slate-400">刷新中...</span> : null}
          </div>
          {snapshots.length === 0 ? (
            <p className="text-sm text-slate-500">尚未生成快照。训练完成时会自动保存快照，或在训练监控中手动触发。</p>
          ) : (
            <ul className="space-y-3">
              {snapshots.map((snapshot) => {
                const isSelected = snapshot.id === selectedSnapshotId;
                return (
                  <li key={snapshot.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedSnapshotId(snapshot.id)}
                      className={`w-full rounded-xl border px-4 py-3 text-left transition-colors ${
                        isSelected
                          ? "border-purple-400 bg-purple-50"
                          : "border-slate-200 bg-slate-50 hover:border-slate-300"
                      }`}
                    >
                      <div className="flex items-center justify-between text-sm text-slate-700">
                        <span className="font-semibold">快照 #{snapshot.id} · 运行 #{snapshot.run_id}</span>
                        <span className="text-xs text-slate-400">{formatDate(snapshot.created_at)}</span>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                        <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5">
                          {triggerLabels[snapshot.trigger_type] ?? snapshot.trigger_type}
                        </span>
                        {snapshot.restored_at ? (
                          <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-emerald-600">
                            已回滚
                          </span>
                        ) : null}
                        {snapshot.notes ? <span>备注：{snapshot.notes}</span> : null}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <aside className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">快照详情</h2>
          {selectedSnapshot ? (
            <div className="mt-4 space-y-4 text-sm text-slate-600">
              <div className="grid gap-2">
                <p>
                  <span className="text-slate-500">所属工作空间：</span>
                  #{selectedSnapshot.workspace_id}
                </p>
                <p>
                  <span className="text-slate-500">训练任务：</span>#{selectedSnapshot.job_id}
                </p>
                <p>
                  <span className="text-slate-500">创建时间：</span>
                  {formatDate(selectedSnapshot.created_at)}
                </p>
                <p>
                  <span className="text-slate-500">触发方式：</span>
                  {triggerLabels[selectedSnapshot.trigger_type] ?? selectedSnapshot.trigger_type}
                </p>
                <p>
                  <span className="text-slate-500">当前状态：</span>
                  {selectedSnapshot.restored_at ? `已回滚（${formatDate(selectedSnapshot.restored_at)}）` : "可用"}
                </p>
              </div>

              <div>
                <p className="mb-1 text-xs font-semibold text-slate-500">指标快照</p>
                {selectedSnapshot.metrics && Object.keys(selectedSnapshot.metrics).length > 0 ? (
                  <ul className="space-y-1 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
                    {Object.entries(selectedSnapshot.metrics).map(([key, value]) => (
                      <li key={key} className="flex justify-between">
                        <span>{key}</span>
                        <span>{String(value)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-slate-400">暂无指标记录。</p>
                )}
              </div>

              <label className="block text-xs font-semibold text-slate-500" htmlFor="snapshot-notes">
                操作备注（可选）
              </label>
              <textarea
                id="snapshot-notes"
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
                rows={3}
                value={operationNotes}
                onChange={(event) => setOperationNotes(event.target.value)}
                placeholder="记录续训或回滚原因，方便后续审计。"
              />

              <div className="flex flex-wrap gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleResume}
                  disabled={resumeMutation.isPending}
                  className="rounded-md border border-purple-400 bg-purple-50 px-4 py-2 text-xs font-medium text-purple-600 transition hover:border-purple-500 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
                >
                  {resumeMutation.isPending ? "续训中..." : "从快照断点续训"}
                </button>
                <button
                  type="button"
                  onClick={handleRollback}
                  disabled={rollbackMutation.isPending}
                  className="rounded-md border border-rose-300 bg-rose-50 px-4 py-2 text-xs font-medium text-rose-600 transition hover:border-rose-400 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
                >
                  {rollbackMutation.isPending ? "回滚中..." : "回滚至该快照"}
                </button>
              </div>
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-500">请选择左侧快照以查看详情与操作。</p>
          )}
        </aside>
      </section>
    </AppShell>
  );
}
