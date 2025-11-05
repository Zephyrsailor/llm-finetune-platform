import { ChangeEvent, Fragment, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  dataHubApi,
  Dataset,
  DatasetVersion,
  evaluationApi,
  EvaluationJob,
  EvaluationTemplate,
  trainingMonitorApi,
  TrainingMonitorRun,
  workspaceApi,
  WorkspaceDetail
} from "../../lib/api";
import { EvaluationNav } from "./EvaluationNav";

interface CreateJobFormState {
  projectId: string;
  datasetId: string;
  datasetVersionId: string;
  trainingRunId: string;
  file?: File | null;
}

export function EvaluationSuitePage() {
  const queryClient = useQueryClient();
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [formState, setFormState] = useState<CreateJobFormState>({
    projectId: "",
    datasetId: "",
    datasetVersionId: "",
    trainingRunId: ""
  });
  const [feedback, setFeedback] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const workspacesQuery = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => workspaceApi.list(),
    staleTime: 60_000
  });

  useEffect(() => {
    if (workspacesQuery.data && workspacesQuery.data.length > 0 && selectedWorkspaceId == null) {
      setSelectedWorkspaceId(workspacesQuery.data[0].id);
    }
  }, [workspacesQuery.data, selectedWorkspaceId]);

  const selectedWorkspace: WorkspaceDetail | undefined = useMemo(() => {
    return workspacesQuery.data?.find((item) => item.id === selectedWorkspaceId);
  }, [workspacesQuery.data, selectedWorkspaceId]);

  const templatesQuery = useQuery({
    queryKey: ["evaluation", "templates", selectedWorkspaceId],
    enabled: selectedWorkspaceId != null,
    queryFn: () => evaluationApi.listTemplates(selectedWorkspaceId ?? 0)
  });

  useEffect(() => {
    if (templatesQuery.data && templatesQuery.data.length > 0 && selectedTemplateId == null) {
      setSelectedTemplateId(templatesQuery.data[0].id);
    }
  }, [templatesQuery.data, selectedTemplateId]);

  const jobsQuery = useQuery({
    queryKey: ["evaluation", "jobs", selectedWorkspaceId],
    enabled: selectedWorkspaceId != null,
    queryFn: () => evaluationApi.listJobs(selectedWorkspaceId ?? 0),
    refetchInterval: 15_000
  });

  const datasetsQuery = useQuery({
    queryKey: ["evaluation", "datasets", selectedWorkspaceId],
    enabled: selectedWorkspaceId != null,
    queryFn: () => dataHubApi.listDatasets(selectedWorkspaceId ?? 0)
  });

  const selectedDatasetId = formState.datasetId ? Number(formState.datasetId) : null;
  const datasetVersionsQuery = useQuery({
    queryKey: ["evaluation", "datasetVersions", selectedDatasetId],
    enabled: selectedDatasetId != null,
    queryFn: () => dataHubApi.listVersions(selectedDatasetId ?? 0)
  });

  const runsQuery = useQuery({
    queryKey: ["evaluation", "runs", selectedWorkspaceId],
    enabled: selectedWorkspaceId != null,
    queryFn: () => trainingMonitorApi.listRuns(selectedWorkspaceId ?? 0)
  });

  const createJobMutation = useMutation({
    mutationFn: evaluationApi.createJob,
    onSuccess: () => {
      setFeedback("评估任务创建成功，已开始执行。");
      setErrorMessage(null);
      setFormState((prev) => ({
        projectId: prev.projectId,
        datasetId: prev.datasetId,
        datasetVersionId: prev.datasetVersionId,
        trainingRunId: prev.trainingRunId,
        file: null
      }));
      queryClient.invalidateQueries({ queryKey: ["evaluation", "jobs"] });
    },
    onError: (error: unknown) => {
      setFeedback(null);
      setErrorMessage(error instanceof Error ? error.message : "创建评估任务失败");
    }
  });

  useEffect(() => {
    if (datasetsQuery.data && datasetsQuery.data.length > 0 && !formState.datasetId) {
      setFormState((prev) => ({
        ...prev,
        datasetId: String(datasetsQuery.data[0].id)
      }));
    }
  }, [datasetsQuery.data, formState.datasetId]);

  useEffect(() => {
    if (datasetVersionsQuery.data && datasetVersionsQuery.data.length > 0) {
      setFormState((prev) => ({
        ...prev,
        datasetVersionId: String(datasetVersionsQuery.data[0].id)
      }));
    }
  }, [datasetVersionsQuery.data]);

  const handleWorkspaceChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const value = Number(event.target.value);
    setSelectedWorkspaceId(Number.isNaN(value) ? null : value);
    setSelectedTemplateId(null);
    setFormState({
      projectId: "",
      datasetId: "",
      datasetVersionId: "",
      trainingRunId: "",
      file: null
    });
    setFeedback(null);
    setErrorMessage(null);
  };

  const handleTemplateChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const value = Number(event.target.value);
    setSelectedTemplateId(Number.isNaN(value) ? null : value);
  };

  const handleFormChange = (event: ChangeEvent<HTMLSelectElement | HTMLInputElement>) => {
    const { name, value } = event.target;
    if (name === "dataset_file") {
      const input = event.target as HTMLInputElement;
      setFormState((prev) => ({ ...prev, file: input.files?.[0] ?? null }));
      return;
    }
    setFormState((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = () => {
    if (!selectedWorkspaceId || !selectedTemplateId) {
      setErrorMessage("请先选择工作空间和评估模板。");
      return;
    }
    const payload = {
      workspace_id: selectedWorkspaceId,
      evaluation_template_id: selectedTemplateId,
      project_id: formState.projectId ? Number(formState.projectId) : undefined,
      training_run_id: formState.trainingRunId ? Number(formState.trainingRunId) : undefined,
      dataset_version_id:
        formState.file == null && formState.datasetVersionId
          ? Number(formState.datasetVersionId)
          : undefined,
      dataset_file: formState.file ?? undefined
    };
    createJobMutation.mutate(payload);
  };

  const isLoading =
    workspacesQuery.isLoading ||
    templatesQuery.isLoading ||
    jobsQuery.isLoading ||
    datasetsQuery.isLoading;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/60">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-6 py-6 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl font-semibold text-cyan-300">标准化评估套件</h1>
            <p className="text-sm text-slate-400">
              选择评估模板、绑定训练运行或上传定制测试集，生成统一的评估结果。
            </p>
          </div>
          {selectedWorkspace && (
            <div className="text-xs text-slate-400">
              项目数量：{selectedWorkspace.projects?.length ?? 0}
            </div>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-8 px-6 py-8">
        <EvaluationNav />
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
          <label className="text-xs font-semibold text-slate-400" htmlFor="workspace-select">
            工作空间
          </label>
          <select
            id="workspace-select"
            className="mt-2 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-cyan-500 focus:outline-none"
            value={selectedWorkspaceId ?? ""}
            onChange={handleWorkspaceChange}
          >
            {workspacesQuery.data?.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.name}
              </option>
            ))}
          </select>
          {workspacesQuery.data?.length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">暂无工作空间，请先创建。</p>
          ) : null}
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
          <h2 className="text-lg font-semibold text-slate-100">创建评估任务</h2>
          <p className="text-sm text-slate-400">
            选择内置模板，绑定数据与训练运行，即可生成统一指标与报告。
          </p>

          {feedback ? <p className="mt-3 text-sm text-emerald-300">{feedback}</p> : null}
          {errorMessage ? <p className="mt-3 text-sm text-rose-300">{errorMessage}</p> : null}

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div>
              <label className="text-xs font-semibold text-slate-400" htmlFor="template-select">
                评估模板
              </label>
              <select
                id="template-select"
                className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-cyan-500 focus:outline-none"
                value={selectedTemplateId ?? ""}
                onChange={handleTemplateChange}
              >
                {templatesQuery.data?.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                  </option>
                ))}
              </select>
              {selectedTemplateId != null ? (
                <p className="mt-2 text-xs text-slate-500">
                  {templatesQuery.data?.find((item) => item.id === selectedTemplateId)?.description ??
                    "该模板将生成标准指标并生成报告。"}
                </p>
              ) : null}
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-400" htmlFor="project-select">
                关联项目（可选）
              </label>
              <select
                id="project-select"
                name="projectId"
                className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-cyan-500 focus:outline-none"
                value={formState.projectId}
                onChange={handleFormChange}
              >
                <option value="">未指定</option>
                {selectedWorkspace?.projects?.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-400" htmlFor="dataset-select">
                评估数据集（可选）
              </label>
              <select
                id="dataset-select"
                name="datasetId"
                className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-cyan-500 focus:outline-none"
                value={formState.datasetId}
                onChange={handleFormChange}
              >
                {datasetsQuery.data?.map((dataset: Dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {dataset.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-400" htmlFor="dataset-version-select">
                数据集版本（可选）
              </label>
              <select
                id="dataset-version-select"
                name="datasetVersionId"
                className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-cyan-500 focus:outline-none"
                value={formState.datasetVersionId}
                onChange={handleFormChange}
              >
                {datasetVersionsQuery.data?.map((version: DatasetVersion) => (
                  <option key={version.id} value={version.id}>
                    v{version.version} ({version.status})
                  </option>
                ))}
              </select>
              <p className="mt-2 text-xs text-slate-500">
                如上传自定义测试集，则无需选择数据集版本。
              </p>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-400" htmlFor="run-select">
                关联训练运行（可选）
              </label>
              <select
                id="run-select"
                name="trainingRunId"
                className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-cyan-500 focus:outline-none"
                value={formState.trainingRunId}
                onChange={handleFormChange}
              >
                <option value="">未指定</option>
                {runsQuery.data?.map((run: TrainingMonitorRun) => (
                  <option key={run.run_id} value={run.run_id}>
                    运行 #{run.run_id} · {run.status}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-400" htmlFor="dataset-file">
                上传自定义测试集（可选）
              </label>
              <input
                id="dataset-file"
                name="dataset_file"
                type="file"
                accept=".json,.jsonl,.csv"
                className="mt-2 block w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-cyan-500 focus:outline-none"
                onChange={handleFormChange}
              />
              <p className="mt-2 text-xs text-slate-500">支持 JSONL/CSV 等格式，大小受限于平台配置。</p>
            </div>
          </div>

          <div className="mt-6 flex flex-col gap-3 md:flex-row md:items-center">
            <button
              type="button"
              onClick={handleSubmit}
              disabled={createJobMutation.isPending || isLoading}
              className="rounded-md border border-cyan-500 px-4 py-2 text-sm text-cyan-200 hover:border-cyan-400 disabled:border-slate-700 disabled:text-slate-500"
            >
              创建评估任务
            </button>
            {createJobMutation.isPending ? (
              <span className="text-xs text-slate-400">正在提交评估任务...</span>
            ) : null}
          </div>
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-100">评估任务列表</h2>
            <button
              type="button"
              onClick={() => queryClient.invalidateQueries({ queryKey: ["evaluation", "jobs"] })}
              className="rounded-md border border-slate-700 px-3 py-1 text-xs text-slate-200 hover:border-slate-500"
            >
              刷新
            </button>
          </div>

          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-800 text-left text-sm">
              <thead className="bg-slate-900/40 text-xs uppercase tracking-wide text-slate-400">
                <tr>
                  <th className="px-4 py-3">任务信息</th>
                  <th className="px-4 py-3">模板</th>
                  <th className="px-4 py-3">指标</th>
                  <th className="px-4 py-3">状态</th>
                  <th className="px-4 py-3">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 text-slate-200">
                {jobsQuery.data?.length ? (
                  jobsQuery.data.map((job: EvaluationJob) => {
                    const metrics = job.metrics ?? undefined;
                    const thresholds = metrics?.thresholds ?? {};
                    const baselines = metrics?.baseline ?? {};
                    const deltas = metrics?.delta ?? {};
                    const triggeredMetrics = Object.entries(thresholds)
                      .filter(([, info]) => info?.triggered)
                      .map(([name]) => name.toUpperCase());

                    return (
                      <tr key={job.id}>
                        <td className="px-4 py-3 align-top text-sm text-slate-300">
                          <div className="flex items-center gap-2">
                            <span>任务 #{job.id}</span>
                            <span
                              className={
                                job.trigger_mode === "automatic"
                                  ? "rounded bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-200"
                                  : "rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400"
                              }
                            >
                              {job.trigger_mode === "automatic" ? "自动" : "手动"}
                            </span>
                          </div>
                          <div className="text-xs text-slate-500">
                            创建时间：{new Date(job.created_at).toLocaleString()}
                          </div>
                          {job.training_run_id ? (
                            <div className="text-xs text-slate-500">运行 #{job.training_run_id}</div>
                          ) : null}
                        </td>
                        <td className="px-4 py-3 align-top text-sm text-slate-300">
                          模板 ID：{job.evaluation_template_id}
                        </td>
                        <td className="px-4 py-3 align-top text-sm text-slate-300">
                          {metrics ? (
                            <div className="space-y-1">
                              <div className="flex flex-wrap gap-2">
                                {["bleu", "rouge_l", "exact_match", "perplexity"]
                                  .filter((key) => typeof metrics[key] === "number")
                                  .map((key) => (
                                    <span key={key} className="rounded bg-slate-800 px-2 py-1">
                                      {key.toUpperCase()}: {(metrics[key] as number).toFixed(4)}
                                      {typeof deltas[key] === "number"
                                        ? ` (Δ ${Number(deltas[key]).toFixed(4)})`
                                        : ""}
                                      {typeof baselines[key] === "number"
                                        ? ` · 基线 ${Number(baselines[key]).toFixed(4)}`
                                        : ""}
                                    </span>
                                  ))}
                              </div>
                              {triggeredMetrics.length > 0 ? (
                                <div className="text-xs text-amber-300">
                                  阈值告警：{triggeredMetrics.join("、")}
                                </div>
                              ) : null}
                            </div>
                          ) : (
                            "尚未生成"
                          )}
                        </td>
                        <td className="px-4 py-3 align-top text-sm text-slate-300">
                          <span
                            className={
                              job.status === "completed"
                                ? "text-emerald-300"
                                : job.status === "failed"
                                  ? "text-rose-300"
                                  : "text-amber-300"
                            }
                          >
                            {job.status}
                          </span>
                          {job.error_message ? (
                            <div className="text-xs text-rose-400">{job.error_message}</div>
                          ) : null}
                        </td>
                        <td className="px-4 py-3 align-top text-sm">
                          <div className="flex flex-col gap-2">
                            <button
                              type="button"
                              onClick={() => handleExport(job.id, "markdown")}
                              disabled={job.status !== "completed"}
                              className="rounded-md border border-slate-700 px-3 py-1 text-xs text-slate-200 hover:border-slate-500 disabled:border-slate-800 disabled:text-slate-600"
                            >
                              下载报告 (MD)
                            </button>
                            <button
                              type="button"
                              onClick={() => handleExport(job.id, "json")}
                              disabled={job.status !== "completed"}
                              className="rounded-md border border-slate-700 px-3 py-1 text-xs text-slate-200 hover:border-slate-500 disabled:border-slate-800 disabled:text-slate-600"
                            >
                              下载指标 (JSON)
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td className="px-4 py-6 text-sm text-slate-400" colSpan={5}>
                      {isLoading ? "正在加载评估任务..." : "尚无评估任务"}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );

  async function handleExport(jobId: number, format: "markdown" | "json") {
    try {
      const blob = await evaluationApi.exportJob(jobId, format);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download =
        format === "json" ? `evaluation-${jobId}.json` : `evaluation-report-${jobId}.md`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "导出评估结果失败");
    }
  }
}
