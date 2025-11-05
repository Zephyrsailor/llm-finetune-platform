import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deploymentApi,
  DeploymentSummary,
  DeploymentStatusValue,
  DeploymentListPayload,
  modelRegistryApi,
  ModelVersionSummary,
  RegisteredModelSummary,
  workspaceApi,
  WorkspaceDetail
} from "../../lib/api";

type Feedback = { type: "success" | "error"; text: string } | null;

function formatDate(value?: string | null): string {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function DeploymentCard({
  deployment,
  onSetTraffic,
  onRollback
}: {
  deployment: DeploymentSummary;
  onSetTraffic: (percent: number) => void;
  onRollback: () => void;
}) {
  const metricsRecord = (deployment.metrics ?? {}) as Record<string, unknown>;
  const latencyP95 = typeof metricsRecord["latency_p95_ms"] === "number" ? (metricsRecord["latency_p95_ms"] as number) : undefined;
  const throughputRps = typeof metricsRecord["throughput_rps"] === "number" ? (metricsRecord["throughput_rps"] as number) : undefined;
  return (
    <article className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 shadow">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-emerald-200">部署 #{deployment.id}</h3>
          <p className="text-xs text-slate-400">环境：{deployment.environment} · 模型版本 #{deployment.model_version_id}</p>
        </div>
        <span className="rounded-full border border-slate-700 px-2 py-1 text-xs font-semibold text-slate-200">
          {deployment.status}
        </span>
      </header>

      <dl className="mt-3 grid gap-2 text-xs text-slate-300 md:grid-cols-2">
        <div>
          <dt className="font-semibold text-slate-200">Endpoint</dt>
          <dd className="font-mono text-slate-200">{deployment.endpoint_url ?? "部署中..."}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-200">访问令牌</dt>
          <dd className="truncate font-mono text-slate-200">{deployment.access_token ?? "部署中..."}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-200">流量占比</dt>
          <dd>{deployment.traffic_percent != null ? `${deployment.traffic_percent}%` : "未设置"}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-200">延迟 / 吞吐</dt>
          <dd>
            P95 {latencyP95 != null ? latencyP95 : "--"} ms · TPS {throughputRps != null ? throughputRps : "--"}
          </dd>
        </div>
      </dl>

      <footer className="mt-4 flex flex-wrap gap-2 text-xs">
        <button
          type="button"
          onClick={() => onSetTraffic(100)}
          className="rounded-md border border-slate-700 px-3 py-1 text-slate-200 hover:border-slate-500"
        >
          灰度完成（100% 流量）
        </button>
        <button
          type="button"
          onClick={() => onSetTraffic(10)}
          className="rounded-md border border-slate-700 px-3 py-1 text-slate-200 hover:border-slate-500"
        >
          灰度起步（10% 流量）
        </button>
        <button
          type="button"
          onClick={onRollback}
          className="rounded-md border border-rose-500/60 px-3 py-1 text-rose-300 hover:border-rose-400"
        >
          立即回滚
        </button>
      </footer>

      <section className="mt-4 space-y-2 rounded-md border border-slate-800 bg-slate-950/40 p-3">
        <h4 className="text-xs font-semibold text-slate-200">事件记录</h4>
        {deployment.events.length === 0 ? (
          <p className="text-xs text-slate-400">暂无事件。</p>
        ) : (
          <ul className="space-y-1 text-xs text-slate-400">
            {deployment.events.map((event) => (
              <li key={event.id} className="flex flex-col gap-0.5 border-b border-slate-800 pb-1 last:border-b-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-slate-300">{event.event_type}</span>
                  <span className="text-slate-500">{formatDate(event.created_at)}</span>
                </div>
                <p className="text-slate-200">{event.message}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </article>
  );
}

export function ModelDeploymentPage() {
  const queryClient = useQueryClient();
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [selectedModelVersionId, setSelectedModelVersionId] = useState<number | null>(null);
  const [environment, setEnvironment] = useState("production");
  const [replicas, setReplicas] = useState(1);
  const [maxBatchSize, setMaxBatchSize] = useState(16);
  const [maxConcurrency, setMaxConcurrency] = useState(32);
  const [notes, setNotes] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);

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

  const modelsQuery = useQuery<RegisteredModelSummary[]>({
    queryKey: ["model-registry", selectedWorkspaceId, "deploy"],
    queryFn: () =>
      modelRegistryApi.list({
        workspaceId: selectedWorkspaceId!,
        projectId: undefined,
        status: "production"
      }),
    enabled: selectedWorkspaceId !== null,
    staleTime: 30_000
  });

  useEffect(() => {
    if (modelsQuery.data) {
      const firstVersion = modelsQuery.data
        .flatMap((model) => model.versions)
        .find((version) => version.status === "production");
      if (firstVersion && selectedModelVersionId === null) {
        setSelectedModelVersionId(firstVersion.id);
      }
    }
  }, [modelsQuery.data, selectedModelVersionId]);

  const deploymentsQuery = useQuery<DeploymentListPayload>({
    queryKey: ["deployments", selectedWorkspaceId],
    queryFn: () => deploymentApi.list({ workspaceId: selectedWorkspaceId!, projectId: undefined, status: undefined }),
    enabled: selectedWorkspaceId !== null,
    staleTime: 10_000
  });

  const createMutation = useMutation({
    mutationFn: () => {
      if (selectedWorkspaceId === null || selectedModelVersionId === null) {
        throw new Error("请选择工作空间和模型版本");
      }
      return deploymentApi.create({
        workspace_id: selectedWorkspaceId,
        project_id: undefined,
        model_version_id: selectedModelVersionId,
        environment,
        replicas,
        max_batch_size: maxBatchSize,
        max_concurrency: maxConcurrency,
        notes
      });
    },
    onSuccess: () => {
      setFeedback({ type: "success", text: "部署任务已提交" });
      void queryClient.invalidateQueries({ queryKey: ["deployments", selectedWorkspaceId] });
    },
    onError: (error: Error) => {
      setFeedback({ type: "error", text: error.message });
    }
  });

  const trafficMutation = useMutation({
    mutationFn: ({ deploymentId, percent }: { deploymentId: number; percent: number }) =>
      deploymentApi.updateTraffic(deploymentId, { traffic_percent: percent }),
    onSuccess: (_, variables) => {
      setFeedback({ type: "success", text: `已更新部署 #${variables.deploymentId} 流量` });
      void queryClient.invalidateQueries({ queryKey: ["deployments", selectedWorkspaceId] });
    },
    onError: (error: Error) => setFeedback({ type: "error", text: error.message })
  });

  const rollbackMutation = useMutation({
    mutationFn: ({ deploymentId, reason }: { deploymentId: number; reason: string }) =>
      deploymentApi.rollback(deploymentId, { reason }),
    onSuccess: (_, variables) => {
      setFeedback({ type: "success", text: `部署 #${variables.deploymentId} 已回滚` });
      void queryClient.invalidateQueries({ queryKey: ["deployments", selectedWorkspaceId] });
    },
    onError: (error: Error) => setFeedback({ type: "error", text: error.message })
  });

  const workspaces = workspacesQuery.data ?? [];
  const models = modelsQuery.data ?? [];
  const deployments = deploymentsQuery.data?.deployments ?? [];

  const productionVersions: ModelVersionSummary[] = useMemo(() => {
    return models.flatMap((model) => model.versions.filter((version) => version.status === "production"));
  }, [models]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/60">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-6">
          <div>
            <h1 className="text-xl font-semibold text-sky-400">vLLM 部署流水线</h1>
            <p className="text-sm text-slate-400">选择模型版本、配置资源，一键触发部署并查看健康状态、事件与流量切换。</p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-6 py-10">
        <section className="grid gap-4 rounded-lg border border-slate-800 bg-slate-900/40 p-4 md:grid-cols-3">
          <label className="flex flex-col gap-1 text-xs text-slate-400">
            工作空间
            <select
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
              value={selectedWorkspaceId ?? ""}
              onChange={(event) => {
                const value = event.target.value ? Number(event.target.value) : null;
                setSelectedWorkspaceId(value);
                setSelectedModelVersionId(null);
              }}
            >
              <option value="">请选择</option>
              {workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-xs text-slate-400">
            模型版本
            <select
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
              value={selectedModelVersionId ?? ""}
              onChange={(event) => setSelectedModelVersionId(event.target.value ? Number(event.target.value) : null)}
            >
              <option value="">请选择模型版本</option>
              {productionVersions.map((version) => (
                <option key={version.id} value={version.id}>
                  v{version.version} · 模型 #{version.model_id}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-xs text-slate-400">
            部署环境
            <input
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
              value={environment}
              onChange={(event) => setEnvironment(event.target.value)}
            />
          </label>
        </section>

        <section className="grid gap-4 rounded-lg border border-slate-800 bg-slate-900/40 p-4 md:grid-cols-4">
          <label className="flex flex-col gap-1 text-xs text-slate-400">
            副本数
            <input
              type="number"
              min={1}
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
              value={replicas}
              onChange={(event) => setReplicas(Number(event.target.value))}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-400">
            最大 Batch Size
            <input
              type="number"
              min={1}
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
              value={maxBatchSize}
              onChange={(event) => setMaxBatchSize(Number(event.target.value))}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-400">
            最大并发
            <input
              type="number"
              min={1}
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
              value={maxConcurrency}
              onChange={(event) => setMaxConcurrency(Number(event.target.value))}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-400 md:col-span-1">
            备注
            <input
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            />
          </label>
        </section>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => createMutation.mutate()}
            className="rounded-md bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-sky-400 disabled:cursor-not-allowed disabled:bg-slate-700"
            disabled={createMutation.isPending || selectedWorkspaceId === null || selectedModelVersionId === null}
          >
            {createMutation.isPending ? "部署中..." : "立即部署"}
          </button>
          {feedback ? (
            <span
              className={
                feedback.type === "error"
                  ? "text-sm text-rose-300"
                  : "text-sm text-emerald-300"
              }
            >
              {feedback.text}
            </span>
          ) : null}
        </div>

        <section className="space-y-4">
          <h2 className="text-sm font-semibold text-slate-200">部署实例</h2>
          {deploymentsQuery.isLoading ? <p className="text-xs text-slate-400">加载部署信息...</p> : null}
          {deployments.length === 0 && !deploymentsQuery.isLoading ? (
            <p className="text-xs text-slate-400">尚未存在部署记录。</p>
          ) : null}
          <div className="grid gap-4">
            {deployments.map((deployment) => (
              <DeploymentCard
                key={deployment.id}
                deployment={deployment}
                onSetTraffic={(percent) =>
                  trafficMutation.mutate({ deploymentId: deployment.id, percent })
                }
                onRollback={() => rollbackMutation.mutate({ deploymentId: deployment.id, reason: "manual" })}
              />
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
