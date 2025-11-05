import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";

import {
  evaluationApi,
  EvaluationReport,
  EvaluationReportCase,
  EvaluationReportShare
} from "../../lib/api";
import { EvaluationNav } from "./EvaluationNav";
import { EvaluationFeedbackPanel } from "./EvaluationFeedbackPanel";

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function renderCaseList(title: string, cases: EvaluationReportCase[]) {
  if (!cases.length) {
    return null;
  }
  return (
    <section className="space-y-2 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
      <div className="space-y-3 text-sm text-slate-200">
        {cases.map((item, index) => (
          <div key={`${title}-${index}`} className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
            <p className="text-xs uppercase text-slate-500">Reference</p>
            <p className="whitespace-pre-line text-sm">{item.reference}</p>
            <p className="mt-2 text-xs uppercase text-slate-500">Prediction</p>
            <p className="whitespace-pre-line text-sm">{item.prediction}</p>
            {item.score != null ? (
              <p className="mt-2 text-xs text-slate-400">Match Score: {item.score.toFixed(4)}</p>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}

type TrainingContext = Record<string, unknown> & {
  run?: Record<string, unknown>;
  job?: Record<string, unknown>;
  project?: Record<string, unknown>;
  dataset?: Record<string, unknown>;
  dataset_version?: Record<string, unknown>;
};

type DatasetContext = Record<string, unknown> & {
  dataset?: Record<string, unknown>;
  dataset_version?: Record<string, unknown>;
  location_uri?: string;
};

export function EvaluationReportPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = Number(params.jobId);
  const [shareInfo, setShareInfo] = useState<EvaluationReportShare | null>(null);
  const [shareError, setShareError] = useState<string | null>(null);

  const reportQuery = useQuery<EvaluationReport, Error>({
    queryKey: ["evaluation-report", jobId],
    enabled: Number.isFinite(jobId),
    queryFn: () => evaluationApi.getReport(jobId)
  });

  const shareMutation = useMutation({
    mutationFn: () => evaluationApi.shareReport(jobId),
    onSuccess: (payload) => {
      setShareInfo(payload);
      setShareError(null);
      if (navigator?.clipboard) {
        void navigator.clipboard.writeText(`${window.location.origin}${payload.share_path}`).catch(() => {
          /* ignore clipboard failures */
        });
      }
    },
    onError: (error: Error) => {
      setShareError(error.message);
    }
  });

  const metrics = reportQuery.data?.metrics ?? {};
  const thresholds = (metrics["thresholds"] ?? {}) as Record<string, { threshold?: number; triggered?: boolean }>;
  const metricEntries = useMemo(() => {
    return Object.entries(metrics)
      .filter(([key]) => !["thresholds", "baseline", "delta", "generated_at"].includes(key))
      .map(([key, value]) => ({ key, value }));
  }, [metrics]);

  const improvedCases = reportQuery.data?.cases?.improved ?? [];
  const regressedCases = reportQuery.data?.cases?.regressed ?? [];

  const trainingInfo = (reportQuery.data?.training ?? {}) as TrainingContext;
  const datasetInfo = (reportQuery.data?.dataset ?? {}) as DatasetContext;
  const jobSummary = (reportQuery.data?.job ?? {}) as Record<string, unknown>;
  const workspaceId = typeof jobSummary.workspace_id === "number" ? (jobSummary.workspace_id as number) : undefined;
  const projectId = typeof jobSummary.project_id === "number" ? (jobSummary.project_id as number) : undefined;
  const trainingRunId = typeof jobSummary.training_run_id === "number" ? (jobSummary.training_run_id as number) : undefined;

  const runInfo = trainingInfo.run ?? {};
  const jobInfo = trainingInfo.job ?? {};
  const projectInfo = trainingInfo.project ?? {};
  const datasetVersionInfo =
    trainingInfo.dataset_version ?? datasetInfo.dataset_version ?? {};
  const datasetMeta = trainingInfo.dataset ?? datasetInfo.dataset ?? {};

  const shareUrl = shareInfo ? `${window.location.origin}${shareInfo.share_path}` : null;

  const handleExport = async (format: "markdown" | "json" | "pdf") => {
    try {
      const blob = await evaluationApi.exportJob(jobId, format);
      const extension = format === "json" ? "json" : format === "pdf" ? "pdf" : "md";
      downloadBlob(blob, `evaluation-report-${jobId}.${extension}`);
    } catch (error) {
      setShareError((error as Error).message);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/60">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-6 py-6 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl font-semibold text-cyan-300">评估报告</h1>
            <p className="text-sm text-slate-400">查看指标对比、典型案例并导出报告或生成分享链接。</p>
          </div>
          {reportQuery.data?.job?.training_run_id ? (
            <Link
              to={`/training/monitor?runId=${reportQuery.data.job.training_run_id}`}
              className="rounded-md border border-cyan-500 px-3 py-2 text-xs text-cyan-200 hover:border-cyan-400"
            >
              查看关联训练运行
            </Link>
          ) : null}
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-8 px-6 py-8">
        <EvaluationNav />

        {Number.isNaN(jobId) ? (
          <p className="text-sm text-rose-300">无效的评估任务 ID。</p>
        ) : null}

        {reportQuery.isLoading ? (
          <p className="text-sm text-slate-400">加载报告中...</p>
        ) : null}

        {reportQuery.isError ? (
          <p className="text-sm text-rose-300">{reportQuery.error?.message ?? "获取报告失败"}</p>
        ) : null}

        {reportQuery.data ? (
          <div className="space-y-6">
            <section className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => handleExport("markdown")}
                className="rounded-md border border-slate-800 bg-slate-900/60 px-3 py-2 text-xs text-slate-200 hover:border-slate-600"
              >
                下载 Markdown
              </button>
              <button
                type="button"
                onClick={() => handleExport("pdf")}
                className="rounded-md border border-slate-800 bg-slate-900/60 px-3 py-2 text-xs text-slate-200 hover:border-slate-600"
              >
                下载 PDF
              </button>
              <button
                type="button"
                onClick={() => handleExport("json")}
                className="rounded-md border border-slate-800 bg-slate-900/60 px-3 py-2 text-xs text-slate-200 hover:border-slate-600"
              >
                下载指标 JSON
              </button>
              <button
                type="button"
                disabled={shareMutation.isPending}
                onClick={() => shareMutation.mutate()}
                className="rounded-md border border-cyan-500 px-3 py-2 text-xs text-cyan-200 hover:border-cyan-400 disabled:border-slate-700 disabled:text-slate-500"
              >
                {shareMutation.isPending ? "生成分享链接中..." : "生成分享链接"}
              </button>
            </section>

            {shareError ? <p className="text-sm text-rose-300">{shareError}</p> : null}
            {shareUrl ? (
              <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 p-4 text-sm text-emerald-100">
                分享链接已生成：
                <a href={shareUrl} className="ml-1 underline" target="_blank" rel="noreferrer">
                  {shareUrl}
                </a>
                <p className="mt-1 text-xs">有效期至 {new Date(shareInfo!.expires_at).toLocaleString()}</p>
              </div>
            ) : null}

            <section className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-3 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
                <h2 className="text-lg font-semibold text-slate-100">关联训练信息</h2>
                {Object.keys(runInfo).length === 0 && Object.keys(jobInfo).length === 0 ? (
                  <p className="text-sm text-slate-400">该报告未关联训练运行。</p>
                ) : (
                  <div className="space-y-2 text-sm text-slate-200">
                    {"id" in runInfo ? <div>运行编号：#{runInfo.id as number}</div> : null}
                    {"status" in runInfo ? <div>状态：{String(runInfo.status)}</div> : null}
                    {"started_at" in runInfo && runInfo.started_at ? (
                      <div>开始时间：{new Date(String(runInfo.started_at)).toLocaleString()}</div>
                    ) : null}
                    {"finished_at" in runInfo && runInfo.finished_at ? (
                      <div>结束时间：{new Date(String(runInfo.finished_at)).toLocaleString()}</div>
                    ) : null}
                    {"artifact_uri" in runInfo && runInfo.artifact_uri ? (
                      <div>产物路径：{String(runInfo.artifact_uri)}</div>
                    ) : null}
                    {"base_model" in jobInfo ? <div>基础模型：{String(jobInfo.base_model)}</div> : null}
                    {"adapter_type" in jobInfo ? <div>Adapter 类型：{String(jobInfo.adapter_type)}</div> : null}
                    {"id" in jobInfo ? <div>训练任务：#{jobInfo.id as number}</div> : null}
                    {"name" in projectInfo ? <div>所属项目：{String(projectInfo.name)}</div> : null}
                  </div>
                )}
              </div>

              <div className="space-y-3 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
                <h2 className="text-lg font-semibold text-slate-100">数据集与版本</h2>
                {Object.keys(datasetVersionInfo).length === 0 && Object.keys(datasetMeta).length === 0 ? (
                  <p className="text-sm text-slate-400">暂无可展示的数据集信息。</p>
                ) : (
                  <div className="space-y-2 text-sm text-slate-200">
                    {"name" in datasetMeta ? <div>数据集：{String(datasetMeta.name)}</div> : null}
                    {"id" in datasetMeta ? <div>数据集 ID：#{datasetMeta.id as number}</div> : null}
                    {"version" in datasetVersionInfo ? (
                      <div>版本号：v{String(datasetVersionInfo.version)}</div>
                    ) : null}
                    {"id" in datasetVersionInfo ? (
                      <div>版本 ID：#{datasetVersionInfo.id as number}</div>
                    ) : null}
                    {"location_uri" in datasetInfo && datasetInfo.location_uri ? (
                      <div>存储路径：{String(datasetInfo.location_uri)}</div>
                    ) : null}
                  </div>
                )}
              </div>
            </section>

            {workspaceId ? (
              <EvaluationFeedbackPanel
                jobId={jobId}
                workspaceId={workspaceId}
                projectId={projectId}
                defaultTrainingRunId={trainingRunId}
              />
            ) : null}

            <section className="grid gap-4 lg:grid-cols-[2fr_1fr]">
              <div className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
                <h2 className="text-lg font-semibold text-slate-100">核心指标</h2>
                <div className="grid gap-3 md:grid-cols-2">
                  {metricEntries.map((item) => (
                    <div key={item.key} className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
                      <p className="text-xs uppercase text-slate-500">{item.key}</p>
                      <p className="text-xl font-semibold text-slate-100">{String(item.value)}</p>
                    </div>
                  ))}
                </div>
              </div>
              <div className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
                <h2 className="text-lg font-semibold text-slate-100">阈值校验</h2>
                {Object.keys(thresholds).length === 0 ? (
                  <p className="text-sm text-slate-400">暂无阈值数据。</p>
                ) : (
                  <ul className="space-y-2 text-sm text-slate-200">
                    {Object.entries(thresholds).map(([name, info]) => (
                      <li key={name} className="flex items-center justify-between rounded-md border border-slate-800 bg-slate-950/60 px-3 py-2">
                        <span>{name}</span>
                        <span className={info.triggered ? "text-amber-300" : "text-emerald-300"}>
                          阈值 {info.threshold} {info.triggered ? "⚠️" : "✅"}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </section>

            <section className="space-y-4">
              <h2 className="text-lg font-semibold text-slate-100">案例分析</h2>
              <div className="grid gap-4 lg:grid-cols-2">
                {renderCaseList("典型提升样例", improvedCases)}
                {renderCaseList("需要关注的劣化样例", regressedCases)}
              </div>
            </section>

            {reportQuery.data.report_html ? (
              <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
                <h2 className="text-lg font-semibold text-slate-100">报告概览</h2>
                <div
                  className="prose prose-invert mt-2 max-w-none text-sm"
                  dangerouslySetInnerHTML={{ __html: reportQuery.data.report_html }}
                />
              </section>
            ) : null}
          </div>
        ) : null}
      </main>
    </div>
  );
}
