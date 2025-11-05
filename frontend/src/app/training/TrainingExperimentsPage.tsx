import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  TrainingExperimentComparison,
  TrainingExperimentDetail,
  TrainingExperimentExportResult,
  TrainingExperimentSummary,
  trainingExperimentsApi,
  workspaceApi,
  WorkspaceDetail
} from "../../lib/api";
import { TrainingNav } from "./TrainingNav";
import { AppShell } from "../layout/AppShell";

function formatMetricSummary(metrics: Record<string, unknown> | undefined) {
  if (!metrics) return "—";
  const entries = Object.entries(metrics);
  if (entries.length === 0) {
    return "—";
  }
  return entries
    .map(([key, value]) => `${key}: ${typeof value === "number" ? value.toFixed(3) : String(value)}`)
    .join("，");
}

function formatResource(resource: Record<string, unknown> | undefined) {
  if (!resource) return "—";
  const duration = resource.duration_seconds ?? resource.duration;
  const cost = resource.cost_estimate_usd;
  const parts: string[] = [];
  if (duration !== undefined && duration !== null) {
    parts.push(`时长 ${duration} 秒`);
  }
  if (cost !== undefined && cost !== null) {
    parts.push(`估算成本 $${cost}`);
  }
  if (!parts.length) {
    return "—";
  }
  return parts.join(" / ");
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return undefined;
}

export function TrainingExperimentsPage() {
  const queryClient = useQueryClient();
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [selectedRuns, setSelectedRuns] = useState<number[]>([]);
  const [detailRunId, setDetailRunId] = useState<number | null>(null);
  const [exportFormat, setExportFormat] = useState<"json" | "csv" | "markdown">("json");
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const workspaceQuery = useQuery<WorkspaceDetail[]>({
    queryKey: ["workspaces"],
    queryFn: () => workspaceApi.list(),
    staleTime: 60_000,
    retry: false
  });

  useEffect(() => {
    if (workspaceQuery.data && workspaceQuery.data.length > 0 && selectedWorkspaceId == null) {
      setSelectedWorkspaceId(workspaceQuery.data[0].id);
    }
  }, [workspaceQuery.data, selectedWorkspaceId]);

  const experimentsQuery = useQuery<TrainingExperimentSummary[]>({
    queryKey: ["training-experiments", "list", selectedWorkspaceId],
    enabled: selectedWorkspaceId != null,
    queryFn: () => trainingExperimentsApi.list(selectedWorkspaceId ?? 0, { limit: 20 }),
    refetchInterval: 30_000,
    retry: false
  });

  const detailQuery = useQuery<TrainingExperimentDetail>({
    queryKey: ["training-experiments", "detail", detailRunId],
    enabled: detailRunId != null,
    queryFn: () => trainingExperimentsApi.detail(detailRunId ?? 0),
    retry: false
  });

  const compareQuery = useQuery<TrainingExperimentComparison>({
    queryKey: ["training-experiments", "compare", ...selectedRuns],
    enabled: selectedRuns.length === 2,
    queryFn: () => trainingExperimentsApi.compare(selectedRuns[0], selectedRuns[1]),
    staleTime: 15_000,
    retry: false
  });

  const exportMutation = useMutation<
    TrainingExperimentExportResult,
    Error,
    { format: "json" | "csv" | "markdown" }
  >({
    mutationFn: ({ format }) =>
      trainingExperimentsApi.export({
        workspace_id: selectedWorkspaceId as number,
        run_ids: selectedRuns,
        format
      }),
    onSuccess: (result) => {
      setExportMessage(`导出成功，文件已保存至 ${result.path}`);
      setExportError(null);
      queryClient.invalidateQueries({ queryKey: ["training-experiments", "detail"] });
    },
    onError: (error) => {
      setExportError(error.message);
      setExportMessage(null);
    }
  });

  const runs = experimentsQuery.data ?? [];
  const workspaceOptions = workspaceQuery.data ?? [];

  const comparison = compareQuery.data;
  const detail = detailQuery.data;

  const toggleRunSelection = (runId: number) => {
    setSelectedRuns((previous) => {
      if (previous.includes(runId)) {
        return previous.filter((id) => id !== runId);
      }
      if (previous.length >= 2) {
        return [previous[1], runId];
      }
      return [...previous, runId];
    });
  };

  const clearSelection = () => {
    setSelectedRuns([]);
    setExportMessage(null);
    setExportError(null);
  };

  const isLoading = workspaceQuery.isLoading || (selectedWorkspaceId != null && experimentsQuery.isLoading);

  const toolbar = (
    <div className="mx-auto w-full max-w-7xl px-8 py-3">
      <TrainingNav />
    </div>
  );

  return (
    <AppShell
      title="训练实验管理与对比"
      subtitle="统一记录训练元数据，对比多次实验差异，并导出报告帮助知识沉淀。"
      searchPlaceholder="搜索训练运行或指标"
      toolbar={toolbar}
    >
      {exportMessage ? (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {exportMessage}
        </div>
      ) : null}
      {exportError ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{exportError}</div>
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
            setSelectedRuns([]);
            setDetailRunId(null);
            setExportMessage(null);
            setExportError(null);
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

      <section className="grid gap-6 lg:grid-cols-[1.7fr_1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">实验运行列表</h2>
              <p className="text-sm text-slate-500">选择两次运行即可查看差异，亦可导出报告或展开详情。</p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor="export-format">
                  导出格式
                </label>
                <select
                  id="export-format"
                  value={exportFormat}
                  onChange={(event) => setExportFormat(event.target.value as "json" | "csv" | "markdown")}
                  className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm text-slate-700 shadow-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-200"
                >
                  <option value="json">JSON</option>
                  <option value="csv">CSV</option>
                  <option value="markdown">Markdown</option>
                </select>
              </div>
              <button
                type="button"
                disabled={selectedWorkspaceId == null || selectedRuns.length === 0 || exportMutation.isPending}
                onClick={() => exportMutation.mutate({ format: exportFormat })}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500"
              >
                {exportMutation.isPending ? "导出中..." : "导出报告"}
              </button>
              {selectedRuns.length > 0 ? (
                <button
                  type="button"
                  onClick={clearSelection}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-400 hover:text-slate-700"
                >
                  清空比较选择
                </button>
              ) : null}
            </div>
          </div>

          <div className="mt-6 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm text-slate-600">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">选择</th>
                  <th className="px-4 py-3">运行信息</th>
                  <th className="px-4 py-3">数据集</th>
                  <th className="px-4 py-3">关键指标</th>
                  <th className="px-4 py-3">资源</th>
                  <th className="px-4 py-3">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading ? (
                  <tr>
                    <td className="px-4 py-5 text-center text-sm text-slate-500" colSpan={6}>
                      正在加载实验记录...
                    </td>
                  </tr>
                ) : runs.length === 0 ? (
                  <tr>
                    <td className="px-4 py-5 text-center text-sm text-slate-500" colSpan={6}>
                      当前工作空间尚无训练运行。
                    </td>
                  </tr>
                ) : (
                  runs.map((run) => {
                    const isSelected = selectedRuns.includes(run.run_id);
                    const datasetRecord = asRecord(run.dataset);
                    const datasetName = datasetRecord?.dataset_name ? String(datasetRecord.dataset_name) : "未记录";
                    const datasetVersion = datasetRecord?.version != null ? String(datasetRecord.version) : "—";
                    return (
                      <tr
                        key={run.run_id}
                        className={isSelected ? "bg-blue-50" : "hover:bg-slate-50"}
                        onClick={() => setDetailRunId(run.run_id)}
                      >
                        <td className="px-4 py-3 align-top">
                          <input
                            type="checkbox"
                            aria-label={`选择运行 ${run.run_id}`}
                            checked={isSelected}
                            onChange={() => toggleRunSelection(run.run_id)}
                            className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                            onClick={(event) => event.stopPropagation()}
                          />
                        </td>
                        <td className="px-4 py-3 align-top">
                          <div className="font-semibold text-slate-900">运行 #{run.run_id}</div>
                          <div className="text-xs text-slate-500">
                            作业 {run.job_id} · {run.status}
                          </div>
                          <div className="text-xs text-slate-400">
                            模型 {run.base_model} · {run.adapter_type}
                          </div>
                        </td>
                        <td className="px-4 py-3 align-top">
                          <div className="text-sm text-slate-700">{datasetName}</div>
                          <div className="text-xs text-slate-400">版本 {datasetVersion}</div>
                        </td>
                        <td className="px-4 py-3 align-top text-sm text-slate-600">
                          {formatMetricSummary(asRecord(run.metrics))}
                        </td>
                        <td className="px-4 py-3 align-top text-sm text-slate-600">
                          {formatResource(asRecord(run.resource))}
                        </td>
                        <td className="px-4 py-3 align-top">
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              setDetailRunId(run.run_id);
                            }}
                            className="rounded-lg border border-slate-300 px-3 py-1 text-xs font-medium text-slate-600 transition hover:border-slate-400 hover:text-slate-700"
                          >
                            查看详情
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-900">运行详情</h3>
            {detail ? (
              <div className="mt-4 space-y-4 text-sm text-slate-600">
                {(() => {
                  const metadata = asRecord(detail.metadata);
                  const dataset = asRecord(detail.dataset);
                  let metrics = asRecord(detail.metrics);
                  const metricsSection = metadata?.metrics;
                  if (metricsSection && typeof metricsSection === "object" && !Array.isArray(metricsSection)) {
                    const maybeFinal = (metricsSection as Record<string, unknown>).final;
                    const parsedFinal = asRecord(maybeFinal);
                    if (parsedFinal) {
                      metrics = parsedFinal;
                    }
                  }
                  const snapshots = Array.isArray(metadata?.snapshots) ? metadata.snapshots : [];
                  const alerts = Array.isArray(metadata?.alerts) ? metadata.alerts : [];
                  const resource = asRecord(metadata?.resource);
                  return (
                    <>
                      <div>
                        <strong className="text-slate-900">运行 #{detail.run_id}</strong> · 状态 {detail.status}
                      </div>
                      <div className="text-slate-500">
                        数据集：{String(dataset?.dataset_name ?? "未记录")} · 版本 {String(dataset?.version ?? "—")}
                      </div>
                      {resource ? (
                        <div className="text-slate-500">
                          资源：{formatResource(resource)} · GPU {String(resource.requested_gpus ?? "未知")}
                        </div>
                      ) : null}
                      <div className="text-slate-500">Artefact：{detail.artifact_uri ?? "尚未生成"}</div>
                      <div>
                        <h4 className="text-sm font-semibold text-slate-900">最终指标</h4>
                        <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-slate-100 p-3 text-xs text-slate-700">
                          {JSON.stringify(metrics ?? {}, null, 2)}
                        </pre>
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-slate-900">快照</h4>
                        <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-slate-100 p-3 text-xs text-slate-700">
                          {JSON.stringify(snapshots ?? [], null, 2)}
                        </pre>
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-slate-900">关联告警</h4>
                        <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-slate-100 p-3 text-xs text-slate-700">
                          {JSON.stringify(alerts ?? [], null, 2)}
                        </pre>
                      </div>
                    </>
                  );
                })()}
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-500">请选择左侧运行查看详情。</p>
            )}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-900">差异对比</h3>
            <p className="text-sm text-slate-500">选择两次运行后即可查看配置与指标差异。</p>
            {selectedRuns.length < 2 ? (
              <p className="mt-4 text-sm text-slate-500">请选择两次运行。</p>
            ) : compareQuery.isLoading ? (
              <p className="mt-4 text-sm text-slate-500">正在生成对比报告...</p>
            ) : comparison ? (
              <div className="mt-4 space-y-4 text-sm text-slate-600">
                {Object.entries(comparison.diff).map(([section, entries]) => {
                  const typedEntries = entries as Array<{
                    key?: string;
                    left?: unknown;
                    right?: unknown;
                    delta?: number | null;
                  }>;
                  return (
                    <div key={section}>
                      <h4 className="text-sm font-semibold text-slate-900">{section}</h4>
                      {typedEntries.length === 0 ? (
                        <p className="text-xs text-slate-400">无差异</p>
                      ) : (
                        <ul className="mt-2 space-y-1 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
                          {typedEntries.map((entry, index) => (
                            <li key={index}>
                              {entry.key ?? "未知"}: {String(entry.left)} → {String(entry.right)}
                              {entry.delta !== undefined && entry.delta !== null
                                ? ` （Δ ${Number(entry.delta).toFixed(3)}）`
                                : ""}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  );
                })}
                <div>
                  <h4 className="text-sm font-semibold text-slate-900">快照</h4>
                  {comparison.snapshots.run_a.length === 0 && comparison.snapshots.run_b.length === 0 ? (
                    <p className="text-xs text-slate-400">无关联快照。</p>
                  ) : (
                    <div className="mt-2 space-y-2 text-xs text-slate-600">
                      <div>
                        <span className="font-semibold text-slate-700">运行 #{selectedRuns[0]}：</span>
                        {comparison.snapshots.run_a.length === 0 ? (
                          <span className="text-slate-400"> 无</span>
                        ) : (
                          <ul className="mt-1 space-y-1">
                            {comparison.snapshots.run_a.map((snapshot, index) => (
                              <li key={`snap-a-${index}`} className="rounded bg-slate-100 px-2 py-1 font-mono">
                                {JSON.stringify(snapshot)}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                      <div>
                        <span className="font-semibold text-slate-700">运行 #{selectedRuns[1]}：</span>
                        {comparison.snapshots.run_b.length === 0 ? (
                          <span className="text-slate-400"> 无</span>
                        ) : (
                          <ul className="mt-1 space-y-1">
                            {comparison.snapshots.run_b.map((snapshot, index) => (
                              <li key={`snap-b-${index}`} className="rounded bg-slate-100 px-2 py-1 font-mono">
                                {JSON.stringify(snapshot)}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  )}
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-slate-900">告警</h4>
                  {comparison.alerts.run_a.length === 0 && comparison.alerts.run_b.length === 0 ? (
                    <p className="text-xs text-slate-400">无关联告警。</p>
                  ) : (
                    <div className="mt-2 space-y-2 text-xs text-slate-600">
                      <div>
                        <span className="font-semibold text-slate-700">运行 #{selectedRuns[0]}：</span>
                        {comparison.alerts.run_a.length === 0 ? (
                          <span className="text-slate-400"> 无</span>
                        ) : (
                          <ul className="mt-1 space-y-1">
                            {comparison.alerts.run_a.map((alert, index) => (
                              <li key={`alert-a-${index}`} className="rounded bg-slate-100 px-2 py-1 font-mono">
                                {JSON.stringify(alert)}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                      <div>
                        <span className="font-semibold text-slate-700">运行 #{selectedRuns[1]}：</span>
                        {comparison.alerts.run_b.length === 0 ? (
                          <span className="text-slate-400"> 无</span>
                        ) : (
                          <ul className="mt-1 space-y-1">
                            {comparison.alerts.run_b.map((alert, index) => (
                              <li key={`alert-b-${index}`} className="rounded bg-slate-100 px-2 py-1 font-mono">
                                {JSON.stringify(alert)}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <p className="mt-4 text-sm text-rose-500">加载对比结果失败。</p>
            )}
          </div>
        </div>
      </section>
    </AppShell>
  );
}
