import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  inferenceApi,
  InferenceApiKeyItem,
  InferenceInvokeResult,
  InferenceLogSummary,
  workspaceApi,
  WorkspaceDetail
} from "../../lib/api";

type Feedback = { type: "success" | "error"; text: string } | null;

interface UsageSummary {
  total: number;
  success: number;
  rateLimited: number;
  averageLatency: number | null;
}

function formatDate(value?: string | null): string {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function buildUsage(logs: InferenceLogSummary[]): UsageSummary {
  if (logs.length === 0) {
    return { total: 0, success: 0, rateLimited: 0, averageLatency: null };
  }
  const success = logs.filter((log) => log.status === "success").length;
  const rateLimited = logs.filter((log) => log.status === "rate_limited").length;
  const latencySamples = logs.map((log) => log.latency_ms).filter((value): value is number => typeof value === "number");
  const averageLatency =
    latencySamples.length > 0 ? Math.round(latencySamples.reduce((sum, value) => sum + value, 0) / latencySamples.length) : null;
  return {
    total: logs.length,
    success,
    rateLimited,
    averageLatency
  };
}

export function InferenceConsolePage() {
  const queryClient = useQueryClient();
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [deploymentId, setDeploymentId] = useState("");
  const [modelVersionId, setModelVersionId] = useState("");
  const [prompt, setPrompt] = useState("你好，今天的工作安排是什么？");
  const [temperature, setTemperature] = useState("0.7");
  const [apiKeyName, setApiKeyName] = useState("");
  const [rateLimit, setRateLimit] = useState("");
  const [dailyQuota, setDailyQuota] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [latestSecret, setLatestSecret] = useState<string | null>(null);
  const [lastOutputs, setLastOutputs] = useState<string[]>([]);

  const workspacesQuery = useQuery<WorkspaceDetail[]>({
    queryKey: ["workspaces"],
    queryFn: () => workspaceApi.list(),
    staleTime: 60_000
  });

  useEffect(() => {
    if (workspacesQuery.data && workspacesQuery.data.length > 0 && selectedWorkspaceId === null) {
      setSelectedWorkspaceId(workspacesQuery.data[0].id);
    }
  }, [workspacesQuery.data, selectedWorkspaceId]);

  const apiKeysQuery = useQuery({
    queryKey: ["inference-api-keys", selectedWorkspaceId],
    queryFn: () => inferenceApi.listApiKeys(selectedWorkspaceId!),
    enabled: selectedWorkspaceId !== null
  });

  const logsQuery = useQuery({
    queryKey: ["inference-logs", selectedWorkspaceId],
    queryFn: () => inferenceApi.listLogs({ workspaceId: selectedWorkspaceId!, limit: 50 }),
    enabled: selectedWorkspaceId !== null,
    refetchInterval: 15_000
  });

  const usageSummary = useMemo(() => buildUsage(logsQuery.data?.logs ?? []), [logsQuery.data]);
  const workspaces = workspacesQuery.data ?? [];
  const apiKeys = apiKeysQuery.data?.items ?? [];
  const logs = logsQuery.data?.logs ?? [];

  const invokeMutation = useMutation({
    mutationFn: async (): Promise<InferenceInvokeResult> => {
      if (selectedWorkspaceId === null) {
        throw new Error("请选择工作空间");
      }
      const deploymentIdValue = deploymentId.trim() ? Number(deploymentId.trim()) : null;
      const modelVersionValue = modelVersionId.trim() ? Number(modelVersionId.trim()) : null;
      if (!deploymentIdValue && !modelVersionValue) {
        throw new Error("请输入部署 ID 或模型版本 ID");
      }
      if (!prompt.trim()) {
        throw new Error("请输入推理提示词");
      }
      const temperatureValue = Number(temperature);
      const parameters: Record<string, unknown> = Number.isFinite(temperatureValue)
        ? { temperature: Number(temperatureValue.toFixed(2)) }
        : {};
      return inferenceApi.invoke({
        workspace_id: selectedWorkspaceId,
        deployment_id: deploymentIdValue,
        model_version_id: modelVersionValue,
        inputs: [prompt],
        parameters
      });
    },
    onSuccess: (result) => {
      setLastOutputs(result.outputs.map((item) => item.output));
      setFeedback({ type: "success", text: `推理成功（延迟 ${result.latency_ms.toFixed(1)} ms）` });
      void queryClient.invalidateQueries({ queryKey: ["inference-logs", selectedWorkspaceId] });
    },
    onError: (error: Error) => {
      setFeedback({ type: "error", text: error.message });
    }
  });

  const createKeyMutation = useMutation({
    mutationFn: async () => {
      if (selectedWorkspaceId === null) {
        throw new Error("请选择工作空间");
      }
      if (!apiKeyName.trim()) {
        throw new Error("请填写密钥名称");
      }
      const rateLimitValue = rateLimit.trim() ? Number(rateLimit.trim()) : null;
      const quotaValue = dailyQuota.trim() ? Number(dailyQuota.trim()) : null;
      return inferenceApi.createApiKey({
        workspace_id: selectedWorkspaceId,
        name: apiKeyName.trim(),
        rate_limit_per_minute: rateLimitValue ?? undefined,
        daily_quota: quotaValue ?? undefined
      });
    },
    onSuccess: (result) => {
      setFeedback({ type: "success", text: "API Key 创建成功（请妥善保存明文）" });
      setLatestSecret(result.secret);
      setApiKeyName("");
      setRateLimit("");
      setDailyQuota("");
      void queryClient.invalidateQueries({ queryKey: ["inference-api-keys", selectedWorkspaceId] });
    },
    onError: (error: Error) => setFeedback({ type: "error", text: error.message })
  });

  const revokeKeyMutation = useMutation({
    mutationFn: (apiKeyId: number) => {
      if (selectedWorkspaceId === null) {
        throw new Error("请选择工作空间");
      }
      return inferenceApi.revokeApiKey(selectedWorkspaceId, apiKeyId);
    },
    onSuccess: () => {
      setFeedback({ type: "success", text: "已吊销 API Key" });
      void queryClient.invalidateQueries({ queryKey: ["inference-api-keys", selectedWorkspaceId] });
    },
    onError: (error: Error) => setFeedback({ type: "error", text: error.message })
  });

  const isWorkspaceLoading = workspacesQuery.isLoading;
  const workspaceError = workspacesQuery.error as Error | null;
  const apiKeyError = apiKeysQuery.error as Error | null;
  const logsError = logsQuery.error as Error | null;

  const handleRevoke = (item: InferenceApiKeyItem) => {
    if (!item.is_active || revokeKeyMutation.isPending) {
      return;
    }
    revokeKeyMutation.mutate(item.id);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/60">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-5">
          <div>
            <h1 className="text-xl font-semibold text-sky-300">推理 API 控制台</h1>
            <p className="text-sm text-slate-400">
              管理推理 API Key、查看调用日志，并快速验证部署的推理入口。
            </p>
          </div>
          {feedback && (
            <div
              className={`rounded-md border px-4 py-2 text-sm ${
                feedback.type === "success"
                  ? "border-emerald-500/40 bg-emerald-900/20 text-emerald-200"
                  : "border-rose-500/40 bg-rose-900/20 text-rose-200"
              }`}
            >
              {feedback.text}
            </div>
          )}
          {latestSecret && (
            <div className="rounded-md border border-amber-500/40 bg-amber-900/10 px-4 py-2 text-xs text-amber-200">
              一次性明文 API Key：<span className="font-mono text-sm">{latestSecret}</span>
            </div>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-8 px-6 py-10">
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold text-slate-400" htmlFor="workspace-select">
                工作空间
              </label>
              <select
                id="workspace-select"
                className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
                value={selectedWorkspaceId ?? ""}
                onChange={(event) => setSelectedWorkspaceId(Number(event.target.value))}
                disabled={isWorkspaceLoading || workspaces.length === 0}
              >
                {workspaces.map((workspace) => (
                  <option key={workspace.id} value={workspace.id}>
                    {workspace.name}
                  </option>
                ))}
              </select>
            </div>
            <span className="text-xs text-slate-400">
              {logsQuery.isFetching ? "日志自动刷新中..." : "日志每 15 秒自动刷新"}
            </span>
          </div>
          {isWorkspaceLoading && <p className="mt-4 text-sm text-slate-400">正在加载工作空间...</p>}
          {workspaceError && <p className="mt-4 text-sm text-rose-300">加载失败：{workspaceError.message}</p>}
          {!isWorkspaceLoading && !workspaceError && workspaces.length === 0 && (
            <p className="mt-4 text-sm text-slate-400">尚未加入任何工作空间，请先创建或加入一个工作空间。</p>
          )}
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg">
          <h2 className="text-lg font-semibold text-slate-100">调用统计</h2>
          {logsError && <p className="mt-3 text-sm text-rose-300">加载日志失败：{logsError.message}</p>}
          <div className="mt-4 grid gap-4 md:grid-cols-4">
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4 text-sm">
              <span className="text-xs text-slate-400">近 50 次总调用</span>
              <p className="mt-2 text-2xl font-semibold text-slate-100">{usageSummary.total}</p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4 text-sm">
              <span className="text-xs text-slate-400">成功次数</span>
              <p className="mt-2 text-2xl font-semibold text-emerald-300">{usageSummary.success}</p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4 text-sm">
              <span className="text-xs text-slate-400">限流次数</span>
              <p className="mt-2 text-2xl font-semibold text-amber-300">{usageSummary.rateLimited}</p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4 text-sm">
              <span className="text-xs text-slate-400">平均延迟 (ms)</span>
              <p className="mt-2 text-2xl font-semibold text-sky-300">
                {usageSummary.averageLatency != null ? usageSummary.averageLatency : "--"}
              </p>
            </div>
          </div>
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg">
          <header className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-100">推理调试</h2>
            <span className="text-xs text-slate-500">仅用于验证部署是否可用，实际业务仍通过 API/SDK 调用。</span>
          </header>
          <form
            className="grid gap-4 md:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault();
              invokeMutation.mutate();
            }}
          >
            <div className="space-y-2">
              <label htmlFor="deployment-id" className="text-xs font-semibold text-slate-400">
                部署 ID
              </label>
              <input
                id="deployment-id"
                type="number"
                placeholder="例如：201"
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
                value={deploymentId}
                onChange={(event) => setDeploymentId(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="model-version-id" className="text-xs font-semibold text-slate-400">
                模型版本 ID（可选）
              </label>
              <input
                id="model-version-id"
                type="number"
                placeholder="用于定位活动部署"
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
                value={modelVersionId}
                onChange={(event) => setModelVersionId(event.target.value)}
              />
            </div>
            <div className="md:col-span-2 space-y-2">
              <label htmlFor="prompt-input" className="text-xs font-semibold text-slate-400">
                推理提示词
              </label>
              <textarea
                id="prompt-input"
                rows={3}
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="temperature-input" className="text-xs font-semibold text-slate-400">
                温度（0 - 1）
              </label>
              <input
                id="temperature-input"
                type="number"
                step="0.1"
                min="0"
                max="1"
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
                value={temperature}
                onChange={(event) => setTemperature(event.target.value)}
              />
            </div>
            <div className="flex items-end">
              <button
                type="submit"
                className="rounded-md border border-sky-500/60 bg-sky-500/10 px-4 py-2 text-sm font-semibold text-sky-200 hover:border-sky-400"
                disabled={invokeMutation.isPending}
              >
                {invokeMutation.isPending ? "调用中..." : "发送推理请求"}
              </button>
            </div>
          </form>
          {lastOutputs.length > 0 && (
            <div className="mt-6 space-y-2 rounded-md border border-slate-800 bg-slate-950/50 p-4">
              <h3 className="text-sm font-semibold text-slate-200">最新返回</h3>
              <ul className="space-y-2 text-sm text-slate-200">
                {lastOutputs.map((output, index) => (
                  <li key={index} className="rounded border border-slate-800 bg-slate-900/60 p-3">
                    {output}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg">
          <header className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-100">API Key 管理</h2>
            <span className="text-xs text-slate-500">
              每个 API Key 绑定一个工作空间，可单独配置限流与每日配额。
            </span>
          </header>
          {apiKeyError && <p className="mt-3 text-sm text-rose-300">加载 API Key 失败：{apiKeyError.message}</p>}
          <form
            className="mt-4 grid gap-4 md:grid-cols-4"
            onSubmit={(event) => {
              event.preventDefault();
              createKeyMutation.mutate();
            }}
          >
            <div className="space-y-2">
              <label htmlFor="api-key-name" className="text-xs font-semibold text-slate-400">
                名称
              </label>
              <input
                id="api-key-name"
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
                value={apiKeyName}
                onChange={(event) => setApiKeyName(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="api-rate-limit" className="text-xs font-semibold text-slate-400">
                每分钟限流（可选）
              </label>
              <input
                id="api-rate-limit"
                type="number"
                min="1"
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
                value={rateLimit}
                onChange={(event) => setRateLimit(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="api-daily-quota" className="text-xs font-semibold text-slate-400">
                每日配额（可选）
              </label>
              <input
                id="api-daily-quota"
                type="number"
                min="1"
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
                value={dailyQuota}
                onChange={(event) => setDailyQuota(event.target.value)}
              />
            </div>
            <div className="flex items-end">
              <button
                type="submit"
                className="rounded-md border border-emerald-500/60 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-200 hover:border-emerald-400"
                disabled={createKeyMutation.isPending}
              >
                {createKeyMutation.isPending ? "创建中..." : "创建 API Key"}
              </button>
            </div>
          </form>
          <div className="mt-6 space-y-3">
            {apiKeys.length === 0 ? (
              <p className="text-sm text-slate-400">当前工作空间尚未创建 API Key。</p>
            ) : (
              <ul className="space-y-2">
                {apiKeys.map((item) => (
                  <li
                    key={item.id}
                    className="flex flex-col gap-2 rounded-md border border-slate-800 bg-slate-950/50 p-4 md:flex-row md:items-center md:justify-between"
                  >
                    <div>
                      <p className="text-sm font-semibold text-slate-100">
                        {item.name} {item.is_active ? "" : "(已吊销)"}
                      </p>
                      <p className="text-xs text-slate-400">
                        创建时间：{formatDate(item.created_at)} · 最近使用：{formatDate(item.last_used_at)}
                      </p>
                      <p className="text-xs text-slate-500">
                        每分钟限流：{item.rate_limit_per_minute ?? "默认"} · 每日配额：{item.daily_quota ?? "默认"}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRevoke(item)}
                      disabled={!item.is_active || revokeKeyMutation.isPending}
                      className="self-start rounded-md border border-rose-500/60 bg-rose-500/10 px-3 py-1 text-xs font-semibold text-rose-200 hover:border-rose-400 disabled:cursor-not-allowed disabled:border-slate-700 disabled:text-slate-500"
                    >
                      {item.is_active ? "吊销" : "已吊销"}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg">
          <header className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-100">调用日志（最近 50 条）</h2>
            <span className="text-xs text-slate-500">点击某条记录可在后端接口获取详细信息。</span>
          </header>
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-800 text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wide text-slate-400">
                  <th className="px-3 py-2 text-left">调用 ID</th>
                  <th className="px-3 py-2 text-left">部署 ID</th>
                  <th className="px-3 py-2 text-left">模型版本</th>
                  <th className="px-3 py-2 text-left">状态</th>
                  <th className="px-3 py-2 text-left">延迟 (ms)</th>
                  <th className="px-3 py-2 text-left">输入 Token</th>
                  <th className="px-3 py-2 text-left">输出 Token</th>
                  <th className="px-3 py-2 text-left">时间</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-900 text-slate-200">
                {logs.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-3 py-4 text-center text-sm text-slate-400">
                      尚无调用记录。
                    </td>
                  </tr>
                ) : (
                  logs.map((log) => (
                    <tr key={log.id}>
                      <td className="px-3 py-2 font-mono text-xs text-sky-300">#{log.id}</td>
                      <td className="px-3 py-2">{log.deployment_id ?? "--"}</td>
                      <td className="px-3 py-2">{log.model_version_id ?? "--"}</td>
                      <td className="px-3 py-2">
                        <span
                          className={`rounded-full px-2 py-1 text-xs font-semibold ${
                            log.status === "success"
                              ? "bg-emerald-500/20 text-emerald-200"
                              : log.status === "rate_limited"
                                ? "bg-amber-500/20 text-amber-200"
                                : "bg-rose-500/20 text-rose-200"
                          }`}
                        >
                          {log.status}
                        </span>
                      </td>
                      <td className="px-3 py-2">{log.latency_ms != null ? log.latency_ms.toFixed(1) : "--"}</td>
                      <td className="px-3 py-2">{log.input_tokens ?? "--"}</td>
                      <td className="px-3 py-2">{log.output_tokens ?? "--"}</td>
                      <td className="px-3 py-2 text-xs text-slate-400">{formatDate(log.created_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}

export default InferenceConsolePage;
