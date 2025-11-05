import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  trainingMonitorApi,
  TrainingMonitorRun,
  TrainingMetricSample,
  TrainingAlertRule,
  TrainingAlertOperator,
  TrainingAlertStatus,
  TrainingAlert,
  workspaceApi,
  WorkspaceDetail,
  TrainingMetricName
} from "../../lib/api";
import { TrainingNav } from "./TrainingNav";
import { AppShell } from "../layout/AppShell";

const METRIC_LABELS: Record<TrainingMetricName, string> = {
  loss: "Loss",
  perplexity: "困惑度",
  throughput: "吞吐",
  gpu_memory: "显存使用 (GB)",
  evaluation_bleu: "BLEU",
  evaluation_rouge_l: "ROUGE-L",
  evaluation_exact_match: "Exact Match",
  evaluation_perplexity: "评估困惑度",
  evaluation_failure: "评估失败"
};

const operatorOptions: { value: TrainingAlertOperator; label: string }[] = [
  { value: "gt", label: ">" },
  { value: "gte", label: "≥" },
  { value: "lt", label: "<" },
  { value: "lte", label: "≤" }
];

function formatTimestamp(value?: string | null): string {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function formatMetricValue(value: unknown): string {
  if (value == null) {
    return "--";
  }
  if (typeof value === "number") {
    return value.toFixed(3);
  }
  if (typeof value === "string") {
    return value;
  }
  return String(value);
}

export function TrainingMonitorPage() {
  const queryClient = useQueryClient();
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [ruleForm, setRuleForm] = useState({
    name: "",
    metric: "loss" as TrainingMetricName,
    operator: "gt" as TrainingAlertOperator,
    threshold: 0.5,
    cooldown_seconds: 300
  });
  const [alertNotes, setAlertNotes] = useState<string>("");
  const [exporting, setExporting] = useState(false);

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

  const runsQuery = useQuery<TrainingMonitorRun[]>({
    queryKey: ["training-monitor", "runs", selectedWorkspaceId],
    enabled: selectedWorkspaceId != null,
    queryFn: () => trainingMonitorApi.listRuns(selectedWorkspaceId ?? 0),
    refetchInterval: 15_000
  });

  const metricsQuery = useQuery<TrainingMetricSample[]>({
    queryKey: ["training-monitor", "metrics", selectedRunId],
    enabled: selectedRunId != null,
    queryFn: () => trainingMonitorApi.listMetrics(selectedRunId ?? 0),
    refetchInterval: 10_000
  });

  const alertRulesQuery = useQuery<TrainingAlertRule[]>({
    queryKey: ["training-monitor", "rules", selectedWorkspaceId],
    enabled: selectedWorkspaceId != null,
    queryFn: () => trainingMonitorApi.listAlertRules(selectedWorkspaceId ?? 0)
  });

  const alertsQuery = useQuery<TrainingAlert[]>({
    queryKey: ["training-monitor", "alerts", selectedWorkspaceId],
    enabled: selectedWorkspaceId != null,
    queryFn: () => trainingMonitorApi.listAlerts(selectedWorkspaceId ?? 0),
    refetchInterval: 15_000
  });

  const createRuleMutation = useMutation({
    mutationFn: trainingMonitorApi.createAlertRule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["training-monitor", "rules"] });
      setRuleForm((previous) => ({ ...previous, name: "" }));
    }
  });

  const updateAlertStatusMutation = useMutation({
    mutationFn: ({ alertId, status }: { alertId: number; status: TrainingAlertStatus }) =>
      trainingMonitorApi.updateAlertStatus(alertId, { status, notes: alertNotes || undefined }),
    onSuccess: () => {
      setAlertNotes("");
      queryClient.invalidateQueries({ queryKey: ["training-monitor", "alerts"] });
      queryClient.invalidateQueries({ queryKey: ["training-monitor", "runs"] });
    }
  });

  const workspaceOptions = workspaceQuery.data ?? [];
  const selectedRun = useMemo(
    () => runsQuery.data?.find((run) => run.run_id === selectedRunId) ?? null,
    [runsQuery.data, selectedRunId]
  );

  const runStats = useMemo(() => {
    const runs = runsQuery.data ?? [];
    const running = runs.filter((run) => run.status === "running").length;
    const queued = runs.filter((run) => run.status === "queued").length;
    const completed = runs.filter((run) => run.status === "completed").length;
    return {
      total: runs.length,
      running,
      queued,
      completed
    };
  }, [runsQuery.data]);

  const handleCreateRule = () => {
    if (!selectedWorkspaceId || !ruleForm.name.trim()) {
      return;
    }
    createRuleMutation.mutate({
      workspace_id: selectedWorkspaceId,
      name: ruleForm.name.trim(),
      metric: ruleForm.metric,
      operator: ruleForm.operator,
      threshold: Number(ruleForm.threshold),
      cooldown_seconds: Number(ruleForm.cooldown_seconds) || 300
    });
  };

  const handleExportMetrics = async (runId: number) => {
    try {
      setExporting(true);
      const blob = await trainingMonitorApi.exportMetrics(runId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `training-metrics-${runId}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  const handleExportAlerts = async () => {
    if (!selectedWorkspaceId) return;
    try {
      setExporting(true);
      const blob = await trainingMonitorApi.exportAlerts(selectedWorkspaceId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `training-alerts-${selectedWorkspaceId}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  const toolbar = (
    <div className="mx-auto w-full max-w-7xl px-8 py-3">
      <TrainingNav />
    </div>
  );

  return (
    <AppShell
      title="训练编排与进度"
      subtitle="实时洞察训练运行、自动评估与资源健康状态"
      searchPlaceholder="搜索训练任务、运行或告警"
      primaryAction={{ label: "新建训练任务", to: "/training/wizard" }}
      toolbar={toolbar}
    >
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-slate-500">训练任务总数</p>
          <p className="mt-2 text-2xl font-semibold text-slate-900">{runStats.total}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-slate-500">运行中</p>
          <p className="mt-2 text-2xl font-semibold text-blue-600">{runStats.running}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-slate-500">排队中</p>
          <p className="mt-2 text-2xl font-semibold text-amber-600">{runStats.queued}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-slate-500">已完成</p>
          <p className="mt-2 text-2xl font-semibold text-emerald-600">{runStats.completed}</p>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor="workspace-select">
              工作空间
            </label>
            <select
              id="workspace-select"
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
              value={selectedWorkspaceId ?? ""}
              onChange={(event) => {
                const workspaceId = Number(event.target.value);
                setSelectedWorkspaceId(Number.isNaN(workspaceId) ? null : workspaceId);
                setSelectedRunId(null);
              }}
            >
              {workspaceOptions.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={handleExportAlerts}
              disabled={exporting || !selectedWorkspaceId}
              className="inline-flex items-center rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-600 shadow-sm transition hover:border-slate-400 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              导出告警
            </button>
            {selectedRunId && (
              <button
                type="button"
                onClick={() => handleExportMetrics(selectedRunId)}
                disabled={exporting}
                className="inline-flex items-center rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-600 shadow-sm transition hover:border-slate-400 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                导出指标
              </button>
            )}
          </div>
        </div>
        {workspaceOptions.length === 0 && (
          <p className="mt-4 text-sm text-slate-500">暂无可用工作空间，请先在工作空间模块完成配置。</p>
        )}
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.25fr_1fr]">
        <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">训练运行列表</h2>
            <button
              type="button"
              onClick={() => runsQuery.refetch()}
              className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 hover:border-slate-300 hover:text-slate-800"
            >
              刷新
            </button>
          </div>
          {runsQuery.isLoading ? (
            <p className="text-sm text-slate-500">加载训练运行中...</p>
          ) : runsQuery.data && runsQuery.data.length > 0 ? (
            <ul className="space-y-4">
              {runsQuery.data.map((run) => {
                const evaluation = run.latest_evaluation;
                const evaluationMetrics = (evaluation?.metrics ?? {}) as Record<string, unknown>;
                const thresholds = (evaluationMetrics["thresholds"] ?? {}) as Record<
                  string,
                  { threshold?: number; triggered?: boolean }
                >;
                const baselines = (evaluationMetrics["baseline"] ?? {}) as Record<string, number>;
                const deltas = (evaluationMetrics["delta"] ?? {}) as Record<string, number>;
                const displayedEvaluationKeys: string[] = ["bleu", "rouge_l", "exact_match", "perplexity"];
                return (
                  <li
                    key={run.run_id}
                    className={`cursor-pointer rounded-xl border px-4 py-4 transition ${
                      run.run_id === selectedRunId
                        ? "border-purple-400 bg-purple-50"
                        : "border-slate-200 bg-slate-50 hover:border-slate-300"
                    }`}
                    onClick={() => setSelectedRunId(run.run_id)}
                  >
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-semibold text-slate-800">运行 #{run.run_id}</span>
                      <span className="text-xs uppercase text-slate-500">{run.status}</span>
                    </div>
                    <div className="mt-3 grid gap-3 text-xs text-slate-500 md:grid-cols-2">
                      <div>
                        <span className="text-slate-500">开始：</span>
                        {formatTimestamp(run.started_at)}
                      </div>
                      {run.finished_at && (
                        <div>
                          <span className="text-slate-500">结束：</span>
                          {formatTimestamp(run.finished_at)}
                        </div>
                      )}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-600">
                      {run.latest_metrics.map((metric, index) => (
                        <span
                          key={`${run.run_id}-${metric.metric}-${metric.recorded_at ?? index}`}
                          className="rounded-full bg-white px-2 py-1 shadow-sm"
                        >
                          {(METRIC_LABELS[metric.metric as TrainingMetricName] ?? metric.metric)}:{" "}
                          {metric.value.toFixed(3)}
                        </span>
                      ))}
                    </div>
                    {run.job_error_message ? (
                      <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-600">
                        失败原因：{run.job_error_message}
                      </div>
                    ) : null}
                    {evaluation && evaluationMetrics && (
                      <div className="mt-4 space-y-2 rounded-xl border border-purple-200 bg-purple-50 p-4 text-xs text-slate-600">
                        <div className="font-medium text-purple-700">
                          自动评估完成{evaluation.job_id ? `（任务 #${evaluation.job_id}）` : ""}：
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {displayedEvaluationKeys
                            .filter((key) => key in evaluationMetrics)
                            .map((key) => (
                              <span key={String(key)} className="rounded-full bg-white px-3 py-1 shadow-sm">
                                {String(key).toUpperCase()}: {formatMetricValue(evaluationMetrics[key])}
                                {typeof deltas[String(key)] === "number"
                                  ? ` (Δ ${Number(deltas[String(key)]).toFixed(4)})`
                                  : ""}
                                {typeof baselines[String(key)] === "number"
                                  ? ` · 基线 ${baselines[String(key)].toFixed(4)}`
                                  : ""}
                              </span>
                            ))}
                        </div>
                        {evaluation.job_id && (
                          <Link
                            to={`/evaluation/reports/${evaluation.job_id}`}
                            className="inline-flex items-center rounded-md border border-purple-200 bg-white px-3 py-1 text-[11px] font-medium text-purple-600 hover:border-purple-300"
                          >
                            查看评估报告
                          </Link>
                        )}
                        {Object.values(thresholds).some((item) => item?.triggered) && (
                          <p className="text-xs text-amber-600">
                            检测到以下指标触发阈值：
                            {Object.entries(thresholds)
                              .filter(([, info]) => info?.triggered)
                              .map(([metricName]) => metricName.toUpperCase())
                              .join("、")}
                            ，请及时复核模型质量。
                          </p>
                        )}
                      </div>
                    )}
                    {run.alerts.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2 text-xs">
                        {run.alerts.map((alert) => (
                          <span
                            key={alert.id}
                            className="rounded-full bg-amber-100 px-3 py-1 text-amber-700"
                          >{`告警#${alert.id} · ${alert.status}`}</span>
                        ))}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">当前工作空间暂无训练运行，完成编排后可在此查看。</p>
          )}
        </div>

        <aside className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">运行详情</h3>
            <p className="mt-1 text-sm text-slate-500">选择左侧运行以查看实时指标与告警处理状态。</p>
          </div>

          {selectedRun ? (
            <div className="space-y-4">
              <dl className="grid gap-4 text-sm text-slate-600">
                <div className="flex justify-between">
                  <dt>运行 ID</dt>
                  <dd className="font-medium text-slate-800">{selectedRun.run_id}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>任务 ID</dt>
                  <dd className="font-medium text-slate-800">{selectedRun.job_id}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>状态</dt>
                  <dd className="font-medium text-blue-600">{selectedRun.status}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>开始时间</dt>
                  <dd className="font-medium text-slate-800">{formatTimestamp(selectedRun.started_at)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>结束时间</dt>
                  <dd className="font-medium text-slate-800">{formatTimestamp(selectedRun.finished_at)}</dd>
                </div>
                {selectedRun.job_error_message ? (
                  <div className="col-span-full rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-600">
                    失败原因：{selectedRun.job_error_message}
                  </div>
                ) : null}
              </dl>

              <div>
                <h4 className="text-sm font-semibold text-slate-900">指标采样</h4>
                {metricsQuery.isLoading ? (
                  <p className="mt-2 text-xs text-slate-500">正在拉取指标...</p>
                ) : metricsQuery.data && metricsQuery.data.length > 0 ? (
                  <ul className="mt-2 space-y-2 text-xs text-slate-600">
                    {metricsQuery.data.slice(0, 8).map((metric, index) => (
                      <li
                        key={`${metric.metric}-${metric.recorded_at ?? index}`}
                        className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
                      >
                        <span>{METRIC_LABELS[metric.metric] ?? metric.metric}</span>
                        <span className="font-medium text-slate-800">{metric.value.toFixed(4)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-xs text-slate-500">暂无指标采样记录。</p>
                )}
              </div>

              {selectedRun.alerts.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-slate-900">关联告警</h4>
                  <ul className="mt-2 space-y-2 text-xs text-slate-600">
                    {selectedRun.alerts.map((alert) => (
                      <li key={alert.id} className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
                        <div className="flex items-center justify-between">
                          <span>告警 #{alert.id}</span>
                          <span className="font-medium text-amber-700">{alert.status}</span>
                        </div>
                        <div className="mt-1 flex justify-between text-[11px] text-amber-700/80">
                          <span>触发：{formatTimestamp(alert.triggered_at)}</span>
                          {alert.resolved_at && <span>恢复：{formatTimestamp(alert.resolved_at)}</span>}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-500">请选择左侧运行查看详细信息。</p>
          )}
        </aside>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-slate-900">告警规则</h3>
            <button
              type="button"
              onClick={() => alertRulesQuery.refetch()}
              className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 hover:border-slate-300"
            >
              刷新
            </button>
          </div>
          {alertRulesQuery.isLoading ? (
            <p className="mt-3 text-sm text-slate-500">正在加载告警规则...</p>
          ) : alertRulesQuery.data && alertRulesQuery.data.length > 0 ? (
            <ul className="mt-4 space-y-3 text-sm text-slate-600">
              {alertRulesQuery.data.map((rule) => (
                <li key={rule.id} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                    <span className="font-medium text-slate-800">{rule.name}</span>
                    <span className="text-xs text-slate-500">
                      {METRIC_LABELS[rule.metric] ?? rule.metric} {rule.operator} {rule.threshold.toFixed(3)}
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                    <span>冷却：{rule.cooldown_seconds}s</span>
                    <span>状态：{rule.is_active ? "启用" : "停用"}</span>
                    <span>更新：{formatTimestamp(rule.updated_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-slate-500">尚未配置告警规则，添加后可对关键指标做阈值预警。</p>
          )}
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">新增告警规则</h3>
          <div className="mt-4 space-y-4 text-sm text-slate-600">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="rule-name">
                规则名称
              </label>
              <input
                id="rule-name"
                value={ruleForm.name}
                onChange={(event) => setRuleForm((previous) => ({ ...previous, name: event.target.value }))}
                placeholder="如：Loss 降不下去"
                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="rule-metric">
                  指标
                </label>
                <select
                  id="rule-metric"
                  value={ruleForm.metric}
                  onChange={(event) =>
                    setRuleForm((previous) => ({ ...previous, metric: event.target.value as TrainingMetricName }))
                  }
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
                >
                  {Object.entries(METRIC_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="rule-operator">
                  条件
                </label>
                <select
                  id="rule-operator"
                  value={ruleForm.operator}
                  onChange={(event) =>
                    setRuleForm((previous) => ({
                      ...previous,
                      operator: event.target.value as TrainingAlertOperator
                    }))
                  }
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
                >
                  {operatorOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="rule-threshold">
                  阈值
                </label>
                <input
                  id="rule-threshold"
                  type="number"
                  value={ruleForm.threshold}
                  onChange={(event) =>
                    setRuleForm((previous) => ({ ...previous, threshold: Number(event.target.value) }))
                  }
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="rule-cooldown">
                  冷却时间（秒）
                </label>
                <input
                  id="rule-cooldown"
                  type="number"
                  value={ruleForm.cooldown_seconds}
                  onChange={(event) =>
                    setRuleForm((previous) => ({ ...previous, cooldown_seconds: Number(event.target.value) }))
                  }
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
                />
              </div>
            </div>
            <button
              type="button"
              onClick={handleCreateRule}
              disabled={createRuleMutation.isPending || !selectedWorkspaceId}
              className="inline-flex w-full justify-center rounded-md bg-purple-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-purple-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {createRuleMutation.isPending ? "创建中..." : "新增规则"}
            </button>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">告警处理</h3>
          {alertsQuery.isLoading ? (
            <p className="mt-3 text-sm text-slate-500">正在加载告警记录...</p>
          ) : alertsQuery.data && alertsQuery.data.length > 0 ? (
            <ul className="mt-4 space-y-3 text-sm text-slate-600">
              {alertsQuery.data.map((alert) => (
                <li key={alert.id} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                    <div>
                      <div className="text-sm font-semibold text-slate-800">{`告警 #${alert.id}`}</div>
                      <div className="text-xs text-slate-500">触发时间：{formatTimestamp(alert.triggered_at)}</div>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <button
                        type="button"
                        onClick={() => updateAlertStatusMutation.mutate({ alertId: alert.id, status: "acknowledged" })}
                        className="rounded-md border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 hover:border-slate-300"
                      >
                        标记处理中
                      </button>
                      <button
                        type="button"
                        onClick={() => updateAlertStatusMutation.mutate({ alertId: alert.id, status: "resolved" })}
                        className="rounded-md border border-emerald-200 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-700 hover:border-emerald-300"
                      >
                        已解决
                      </button>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-col gap-2">
                    <textarea
                      value={alertNotes}
                      onChange={(event) => setAlertNotes(event.target.value)}
                      placeholder="记录分析、回滚或补救措施"
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
                    />
                    <div className="flex flex-wrap gap-3 text-xs text-slate-500">
                      <span>状态：{alert.status}</span>
                      {alert.acknowledged_at && <span>处理中：{formatTimestamp(alert.acknowledged_at)}</span>}
                      {alert.resolved_at && <span>恢复：{formatTimestamp(alert.resolved_at)}</span>}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-slate-500">暂未产生告警，持续监控训练运行即可及时获知异常。</p>
          )}
        </div>
      </section>
    </AppShell>
  );
}
