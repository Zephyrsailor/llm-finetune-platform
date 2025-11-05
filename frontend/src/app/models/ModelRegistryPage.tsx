import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  modelRegistryApi,
  ModelVersionStatusValue,
  RegisteredModelSummary,
  ModelVersionSummary,
  workspaceApi,
  WorkspaceDetail
} from "../../lib/api";

const STATUS_LABEL: Record<ModelVersionStatusValue, string> = {
  candidate: "候选",
  production: "生产",
  deprecated: "废弃"
};

const STATUS_BADGE: Record<ModelVersionStatusValue, string> = {
  candidate: "bg-slate-800 text-slate-200",
  production: "bg-emerald-500/20 text-emerald-300",
  deprecated: "bg-rose-500/20 text-rose-300"
};

type Feedback = { type: "success" | "error"; text: string } | null;

function formatDate(value?: string | null): string {
  if (!value) {
    return "--";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function VersionCard({
  version,
  onPromote,
  onDemote,
  onDeprecate,
  onExport
}: {
  version: ModelVersionSummary;
  onPromote: () => void;
  onDemote: () => void;
  onDeprecate: () => void;
  onExport: (format: "json" | "markdown") => void;
}) {
  const metrics = version.evaluation_metrics ?? {};
  const thresholds = (metrics.thresholds as Record<string, { triggered?: boolean; threshold?: number }>) || {};
  const triggered = Object.values(thresholds).some((item) => item && item.triggered);

  return (
    <article className="space-y-3 rounded-lg border border-slate-800 bg-slate-900/60 p-4 shadow">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-emerald-200">版本 v{version.version}</h3>
          <p className="text-xs text-slate-400">创建于 {formatDate(version.created_at)}</p>
        </div>
        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${STATUS_BADGE[version.status]}`}>
          {STATUS_LABEL[version.status]}
        </span>
      </header>

      {version.notes ? <p className="text-sm text-slate-200">{version.notes}</p> : null}

      <dl className="grid gap-3 text-xs text-slate-400 md:grid-cols-2">
        <div>
          <dt className="font-semibold text-slate-300">训练运行</dt>
          <dd className="text-slate-200">{version.training_run_id ?? "未关联"}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-300">评估任务</dt>
          <dd className="text-slate-200">
            {version.evaluation_job_id ? (
              <a
                href={`/evaluation/reports/${version.evaluation_job_id}`}
                className="text-sky-300 hover:underline"
              >
                #{version.evaluation_job_id}
              </a>
            ) : (
              "未关联"
            )}
          </dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-300">Artefact 路径</dt>
          <dd className="font-mono text-slate-300">{version.artifact_path ?? "--"}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-300">部署目标</dt>
          <dd className="text-slate-200">{version.deployment_target ?? "未设置"}</dd>
        </div>
      </dl>

      {version.evaluation_job_id ? (
        <section className="rounded-md border border-slate-800 bg-slate-950/50 p-3 text-xs text-slate-400">
          <h4 className="text-xs font-semibold text-slate-200">评估指标摘要</h4>
          {triggered ? (
            <p className="mt-1 text-amber-300">存在未通过的阈值（{Object.keys(thresholds).length} 项）。</p>
          ) : (
            <p className="mt-1 text-slate-300">评估指标全部达标。</p>
          )}
          <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-all font-mono text-slate-400">
            {JSON.stringify(version.evaluation_metrics, null, 2)}
          </pre>
        </section>
      ) : null}

      <footer className="flex flex-wrap gap-2 text-xs">
        {version.status !== "production" ? (
          <button
            type="button"
            onClick={onPromote}
            className="rounded-md border border-emerald-500/60 px-3 py-1 text-emerald-300 hover:border-emerald-400"
          >
            标记为生产
          </button>
        ) : (
          <button
            type="button"
            onClick={onDemote}
            className="rounded-md border border-sky-500/60 px-3 py-1 text-sky-300 hover:border-sky-400"
          >
            降级为候选
          </button>
        )}
        {version.status !== "deprecated" ? (
          <button
            type="button"
            onClick={onDeprecate}
            className="rounded-md border border-rose-500/60 px-3 py-1 text-rose-300 hover:border-rose-400"
          >
            标记为废弃
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => onExport("json")}
          className="rounded-md border border-slate-700 px-3 py-1 text-slate-200 hover:border-slate-500"
        >
          导出 JSON
        </button>
        <button
          type="button"
          onClick={() => onExport("markdown")}
          className="rounded-md border border-slate-700 px-3 py-1 text-slate-200 hover:border-slate-500"
        >
          导出 Markdown
        </button>
      </footer>
    </article>
  );
}

export function ModelRegistryPage() {
  const queryClient = useQueryClient();
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<ModelVersionStatusValue | "all">("all");
  const [selectedModelId, setSelectedModelId] = useState<number | null>(null);
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
    queryKey: ["model-registry", selectedWorkspaceId, selectedProjectId, statusFilter],
    queryFn: () =>
      modelRegistryApi.list({
        workspaceId: selectedWorkspaceId!,
        projectId: selectedProjectId ?? undefined,
        status: statusFilter === "all" ? undefined : statusFilter
      }),
    enabled: selectedWorkspaceId !== null,
    staleTime: 30_000
  });

  useEffect(() => {
    if (modelsQuery.data && modelsQuery.data.length > 0 && selectedModelId === null) {
      setSelectedModelId(modelsQuery.data[0].id);
    }
  }, [modelsQuery.data, selectedModelId]);

  const promoteMutation = useMutation({
    mutationFn: ({
      modelId,
      versionId,
      status
    }: {
      modelId: number;
      versionId: number;
      status: ModelVersionStatusValue;
    }) =>
      modelRegistryApi.updateVersionStatus(modelId, versionId, {
        status
      }),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({
        queryKey: ["model-registry", selectedWorkspaceId, selectedProjectId, statusFilter]
      });
      setFeedback({
        type: "success",
        text: `模型 #${variables.modelId} 版本 #${variables.versionId} 状态已更新为 ${STATUS_LABEL[variables.status]}`
      });
    },
    onError: (error: Error) => {
      setFeedback({ type: "error", text: error.message });
    }
  });

  const exportMutation = useMutation({
    mutationFn: ({
      modelId,
      versionId,
      format
    }: {
      modelId: number;
      versionId: number;
      format: "json" | "markdown";
    }) => modelRegistryApi.exportVersion(modelId, versionId, format),
    onSuccess: (payload) => {
      setFeedback({ type: "success", text: `已导出，本地路径：${payload.path}` });
    },
    onError: (error: Error) => {
      setFeedback({ type: "error", text: error.message });
    }
  });

  const workspaces = workspacesQuery.data ?? [];
  const selectedWorkspace = workspaces.find((item) => item.id === selectedWorkspaceId);
  const projects = selectedWorkspace?.projects ?? [];

  const models = modelsQuery.data ?? [];
  const selectedModel = models.find((item) => item.id === selectedModelId) ?? null;

  const versions = useMemo<ModelVersionSummary[]>(() => {
    if (!selectedModel) {
      return [];
    }
    return [...selectedModel.versions].sort((a, b) => b.version - a.version);
  }, [selectedModel]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/60">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-6">
          <div>
            <h1 className="text-xl font-semibold text-sky-400">模型注册与版本管理</h1>
            <p className="text-sm text-slate-400">
              追踪训练产出的模型版本、评估合规状态以及部署审批流水，支持导出与回滚。
            </p>
          </div>
          <nav aria-label="模型模块导航" className="flex flex-wrap gap-2 text-xs">
            <a href="/training/templates" className="rounded-md border border-slate-800 px-3 py-1 text-slate-300 hover:border-slate-600">
              训练模板
            </a>
            <a href="/evaluation/suite" className="rounded-md border border-slate-800 px-3 py-1 text-slate-300 hover:border-slate-600">
              评估套件
            </a>
            <a
              href="/models/registry"
              className="rounded-md border border-sky-500/40 bg-sky-500/10 px-3 py-1 text-sky-200"
            >
              模型仓库
            </a>
            <a href="/dashboard" className="rounded-md border border-slate-800 px-3 py-1 text-slate-300 hover:border-slate-600">
              仪表盘
            </a>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-6 py-10">
        <section className="grid gap-4 rounded-lg border border-slate-800 bg-slate-900/40 p-4 md:grid-cols-4">
          <label className="flex flex-col gap-1 text-xs text-slate-400">
            工作空间
            <select
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
              value={selectedWorkspaceId ?? ""}
              onChange={(event) => {
                const value = event.target.value ? Number(event.target.value) : null;
                setSelectedWorkspaceId(value);
                setSelectedProjectId(null);
                setSelectedModelId(null);
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
            项目筛选
            <select
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
              value={selectedProjectId ?? ""}
              onChange={(event) => {
                const value = event.target.value ? Number(event.target.value) : null;
                setSelectedProjectId(value);
                setSelectedModelId(null);
              }}
            >
              <option value="">全部项目</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-xs text-slate-400">
            版本状态
            <select
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as ModelVersionStatusValue | "all")}
            >
              <option value="all">全部</option>
              <option value="candidate">候选</option>
              <option value="production">生产</option>
              <option value="deprecated">废弃</option>
            </select>
          </label>
        </section>

        {feedback ? (
          <div
            role="status"
            className={`rounded-md border px-4 py-3 text-sm ${
              feedback.type === "error"
                ? "border-rose-500/60 bg-rose-500/10 text-rose-200"
                : "border-emerald-500/60 bg-emerald-500/10 text-emerald-200"
            }`}
          >
            {feedback.text}
          </div>
        ) : null}

        <section className="grid gap-6 md:grid-cols-[260px_1fr]">
          <aside className="space-y-3">
            <h2 className="text-sm font-semibold text-slate-200">模型列表</h2>
            {modelsQuery.isLoading ? (
              <p className="text-xs text-slate-400">加载模型中...</p>
            ) : null}
            {models.length === 0 && !modelsQuery.isLoading ? (
              <p className="text-xs text-slate-500">尚未注册任何模型。</p>
            ) : null}
            <ul className="space-y-2">
              {models.map((model) => (
                <li key={model.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedModelId(model.id)}
                    className={`w-full rounded-md border px-3 py-2 text-left text-sm ${
                      selectedModelId === model.id
                        ? "border-sky-500/60 bg-sky-500/10 text-sky-200"
                        : "border-slate-700 bg-slate-900/60 text-slate-200 hover:border-slate-500"
                    }`}
                  >
                    <div className="font-semibold">{model.name}</div>
                    <div className="mt-1 text-xs text-slate-400">
                      {model.base_model ? `基座：${model.base_model}` : "未填写"}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1 text-xs text-slate-500">
                      {model.tags.map((tag) => (
                        <span key={tag} className="rounded bg-slate-800 px-1 py-0.5">
                          #{tag}
                        </span>
                      ))}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </aside>

          <section className="space-y-4">
            {selectedModel ? (
              <>
                <header className="space-y-1">
                  <h2 className="text-lg font-semibold text-slate-100">{selectedModel.name}</h2>
                  <p className="text-sm text-slate-400">
                    注册于 {formatDate(selectedModel.created_at)} · 最近更新 {formatDate(selectedModel.updated_at)}
                  </p>
                  {selectedModel.description ? (
                    <p className="text-sm text-slate-200">{selectedModel.description}</p>
                  ) : null}
                </header>

                <div className="grid gap-4">
                  {versions.map((version) => (
                    <VersionCard
                      key={version.id}
                      version={version}
                      onPromote={() =>
                        promoteMutation.mutate({
                          modelId: selectedModel.id,
                          versionId: version.id,
                          status: "production"
                        })
                      }
                      onDemote={() =>
                        promoteMutation.mutate({
                          modelId: selectedModel.id,
                          versionId: version.id,
                          status: "candidate"
                        })
                      }
                      onDeprecate={() =>
                        promoteMutation.mutate({
                          modelId: selectedModel.id,
                          versionId: version.id,
                          status: "deprecated"
                        })
                      }
                      onExport={(format) =>
                        exportMutation.mutate({
                          modelId: selectedModel.id,
                          versionId: version.id,
                          format
                        })
                      }
                    />
                  ))}
                  {versions.length === 0 ? (
                    <p className="text-sm text-slate-400">该模型还没有版本记录。</p>
                  ) : null}
                </div>
              </>
            ) : (
              <p className="text-sm text-slate-400">请选择左侧的模型查看详情。</p>
            )}
          </section>
        </section>
      </main>
    </div>
  );
}
