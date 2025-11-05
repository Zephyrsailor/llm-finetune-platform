import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  dataHubApi,
  Dataset,
  DatasetVersion,
  qualityApi,
  QualitySummary,
  workspaceApi,
  WorkspaceDetail
} from "../../lib/api";
import { DataHubNav } from "./DataHubNav";
import { AppShell } from "../layout/AppShell";

type Feedback = { type: "success" | "error"; text: string } | null;

type MetricValue = string | number | undefined;

type QualityStats = Record<string, unknown>;

function HeroStat({ title, value, description }: { title: string; value: string; description?: string }) {
  return (
    <div className="rounded-3xl bg-gradient-to-br from-emerald-50 via-white to-white px-6 py-6 shadow-sm">
      <div className="text-sm font-semibold text-slate-500">{title}</div>
      <div className="mt-4 text-3xl font-semibold text-slate-900">{value}</div>
      {description ? <div className="mt-2 text-xs text-slate-500">{description}</div> : null}
    </div>
  );
}

function MetricCard({ title, value, description }: { title: string; value: MetricValue; description?: string }) {
  return (
    <div className="rounded-3xl border border-slate-200 bg-white px-6 py-6 shadow-sm">
      <div className="text-sm font-semibold text-slate-600">{title}</div>
      <div className="mt-3 text-xl font-semibold text-slate-900">{value ?? "—"}</div>
      {description ? <div className="mt-1 text-xs text-slate-500">{description}</div> : null}
    </div>
  );
}

function AnomalyTable({ anomalies }: { anomalies: unknown[] }) {
  if (!Array.isArray(anomalies) || anomalies.length === 0) {
    return <p className="rounded-3xl border border-slate-200 bg-white px-6 py-6 text-sm text-slate-500">暂无异常样本。</p>;
  }

  return (
    <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200 text-left text-sm text-slate-600">
        <thead className="bg-slate-50 text-xs font-semibold text-slate-500">
          <tr>
            <th className="px-5 py-3">#</th>
            <th className="px-5 py-3">原因</th>
            <th className="px-5 py-3">样本</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200">
          {anomalies.slice(0, 20).map((item, index) => {
            const anomaly = item as { index?: number; reasons?: string[]; record?: unknown };
            return (
              <tr key={index} className="hover:bg-slate-50">
                <td className="px-5 py-3 text-slate-400">{anomaly.index ?? index}</td>
                <td className="px-5 py-3 text-slate-600">{(anomaly.reasons ?? []).join("，") || "—"}</td>
                <td className="px-5 py-3 font-mono text-[11px] text-slate-500">
                  {JSON.stringify(anomaly.record ?? {}, null, 0)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function extractMetric(stats: QualityStats, key: string, fallback: string = "—"): string {
  const value = stats[key];
  if (typeof value === "number") {
    return value.toFixed(3);
  }
  if (typeof value === "string") {
    return value;
  }
  return fallback;
}

export function QualityDashboardPage() {
  const queryClient = useQueryClient();
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [selectedDatasetId, setSelectedDatasetId] = useState<number | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [lastTriggeredAt, setLastTriggeredAt] = useState<string | null>(null);
  const [pendingStatus, setPendingStatus] = useState<string | null>(null);

  const workspaceQuery = useQuery<WorkspaceDetail[]>({
    queryKey: ["workspaces"],
    queryFn: () => workspaceApi.list()
  });

  const datasetsQuery = useQuery<Dataset[]>({
    queryKey: ["datasets", selectedWorkspaceId],
    enabled: selectedWorkspaceId != null,
    queryFn: () => dataHubApi.listDatasets(selectedWorkspaceId ?? 0)
  });

  const versionsQuery = useQuery<DatasetVersion[]>({
    queryKey: ["dataset-versions", selectedDatasetId],
    enabled: selectedDatasetId != null,
    queryFn: () => dataHubApi.listVersions(selectedDatasetId ?? 0)
  });

  const summaryQuery = useQuery<QualitySummary>({
    queryKey: ["quality-summary", selectedDatasetId, selectedVersionId],
    enabled: selectedDatasetId != null && selectedVersionId != null,
    queryFn: () => qualityApi.summary(selectedDatasetId ?? 0, selectedVersionId ?? 0)
  });

  useEffect(() => {
    if (workspaceQuery.data?.length && selectedWorkspaceId == null) {
      setSelectedWorkspaceId(workspaceQuery.data[0].id);
    }
  }, [workspaceQuery.data, selectedWorkspaceId]);

  useEffect(() => {
    const datasets = datasetsQuery.data ?? [];
    if (!datasets.length) {
      setSelectedDatasetId(null);
      return;
    }
    if (!datasets.some((item) => item.id === selectedDatasetId)) {
      setSelectedDatasetId(datasets[0].id);
    }
  }, [datasetsQuery.data, selectedDatasetId]);

  useEffect(() => {
    const versions = versionsQuery.data ?? [];
    if (!versions.length) {
      setSelectedVersionId(null);
      return;
    }
    if (!versions.some((item) => item.id === selectedVersionId)) {
      setSelectedVersionId(versions[0].id);
    }
  }, [versionsQuery.data, selectedVersionId]);

  const runMutation = useMutation({
    mutationFn: () => qualityApi.run(selectedDatasetId ?? 0, selectedVersionId ?? 0),
    onMutate: () => {
      setPendingStatus("running");
      setFeedback(null);
    },
    onSuccess: () => {
      setLastTriggeredAt(new Date().toLocaleString());
      setFeedback({ type: "success", text: "已重新触发质量评估。" });
      queryClient.invalidateQueries({ queryKey: ["quality-summary", selectedDatasetId, selectedVersionId] });
      setTimeout(() => {
        void summaryQuery.refetch().finally(() => {
          setPendingStatus(null);
        });
      }, 1500);
    },
    onError: (error: Error) => {
      setFeedback({ type: "error", text: error.message });
      setPendingStatus(null);
    }
  });

  const handleDownload = async (format: "json" | "csv") => {
    if (!selectedDatasetId || !selectedVersionId) {
      setFeedback({ type: "error", text: "请先选择数据集版本。" });
      return;
    }
    try {
      const blob = await qualityApi.downloadExport(selectedDatasetId, selectedVersionId, format);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `quality-${selectedDatasetId}-v${selectedVersionId}.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setFeedback({ type: "success", text: `已开始下载 ${format.toUpperCase()} 报告。` });
    } catch (error) {
      setFeedback({ type: "error", text: (error as Error).message });
    }
  };

  const datasetOptions = datasetsQuery.data ?? [];
  const versionOptions = versionsQuery.data ?? [];
  const stats = (summaryQuery.data?.stats ?? {}) as QualityStats;
  const isRefreshing = Boolean(pendingStatus) || runMutation.isPending || summaryQuery.isFetching;
  const anomalies = isRefreshing ? [] : ((stats["top_anomalies"] as unknown[]) ?? []);
  const currentStatus = pendingStatus ?? summaryQuery.data?.status ?? "待执行";

  const toolbar = (
    <div className="mx-auto w-full max-w-7xl px-10 py-4">
      <DataHubNav />
    </div>
  );

  return (
    <AppShell
      title="数据质量评估"
      subtitle="查看清洗后的质量指标、异常样本与评估报告"
      searchPlaceholder="搜索数据集或质量报告"
      primaryAction={{ label: "新建清洗任务", to: "/data-hub/upload" }}
      toolbar={toolbar}
    >
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <HeroStat
          title="覆盖样本"
          value={isRefreshing ? "—" : extractMetric(stats, "total_records", "0 条")}
          description="评估覆盖的样本总量"
        />
        <HeroStat
          title="通过率"
          value={isRefreshing ? "—" : `${extractMetric(stats, "pass_rate", "0")} %`}
          description="通过规则校验的占比"
        />
        <HeroStat
          title="异常样本"
          value={isRefreshing ? "—" : String(anomalies.length)}
          description="已识别的潜在问题样本"
        />
        <HeroStat
          title="最新评估状态"
          value={currentStatus}
          description={lastTriggeredAt ? `最近触发：${lastTriggeredAt}` : "最近一次质量评估结果状态"}
        />
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white px-6 py-6 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">数据集</span>
            <select
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-200"
              value={selectedDatasetId ?? ""}
              onChange={(event) => {
                const datasetId = Number(event.target.value);
                setSelectedDatasetId(Number.isNaN(datasetId) ? null : datasetId);
                setSelectedVersionId(null);
              }}
            >
              <option value="">请选择数据集</option>
              {datasetOptions.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>
                  {dataset.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">数据集版本</span>
            <select
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-200"
              value={selectedVersionId ?? ""}
              onChange={(event) => {
                const versionId = Number(event.target.value);
                setSelectedVersionId(Number.isNaN(versionId) ? null : versionId);
              }}
              disabled={versionOptions.length === 0}
            >
              <option value="">请选择版本</option>
              {versionOptions.map((version) => (
                <option key={version.id} value={version.id}>
                  v{version.version}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={() => runMutation.mutate()}
            className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-500"
            disabled={!selectedDatasetId || !selectedVersionId || runMutation.isPending}
          >
            {runMutation.isPending ? "触发中..." : "重新评估"}
          </button>
          <div className="flex flex-wrap gap-2 text-xs text-slate-500">
            <button
              type="button"
              onClick={() => handleDownload("json")}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 font-medium text-slate-600 hover:border-slate-300"
            >
              导出 JSON
            </button>
            <button
              type="button"
              onClick={() => handleDownload("csv")}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 font-medium text-slate-600 hover:border-slate-300"
            >
              导出 CSV
            </button>
          </div>
        </div>
        {!datasetOptions.length && (
          <p className="mt-3 text-xs text-amber-600">尚未接入数据集，请先完成数据导入。</p>
        )}
        {feedback && (
          <div
            className={`mt-4 rounded-2xl border px-4 py-3 text-sm ${
              feedback.type === "success"
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-rose-200 bg-rose-50 text-rose-700"
            }`}
          >
            {feedback.text}
          </div>
        )}
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <MetricCard
          title="均匀度"
          value={isRefreshing ? "—" : extractMetric(stats, "evenness")}
          description="样本分布是否均衡"
        />
        <MetricCard
          title="重复率"
          value={isRefreshing ? "—" : `${extractMetric(stats, "duplication_rate", "0")} %`}
          description="重复样本占比"
        />
        <MetricCard
          title="噪声率"
          value={isRefreshing ? "—" : `${extractMetric(stats, "noise_rate", "0")} %`}
          description="噪声样本占比"
        />
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-900">异常样本列表</h2>
        {isRefreshing ? (
          <p className="rounded-3xl border border-slate-200 bg-slate-50 px-6 py-6 text-sm text-slate-500">评估进行中，结果刷新后自动展示。</p>
        ) : (
          <AnomalyTable anomalies={anomalies} />
        )}
      </section>
    </AppShell>
  );
}
