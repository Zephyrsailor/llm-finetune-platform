import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  evaluationApi,
  EvaluationFeedback,
  EvaluationFeedbackKind,
  EvaluationFeedbackStatus,
  EvaluationFeedbackExportResult
} from "../../lib/api";

const KIND_OPTIONS: Array<{ value: EvaluationFeedbackKind; label: string }> = [
  { value: "comment", label: "评论" },
  { value: "todo", label: "待办" },
  { value: "business_metric", label: "业务指标" }
];

const STATUS_LABEL: Record<EvaluationFeedbackStatus, string> = {
  open: "未完成",
  resolved: "已完成"
};

type MessageState = { type: "success" | "error"; text: string } | null;

type FeedbackFilters = {
  status?: EvaluationFeedbackStatus;
  kind?: EvaluationFeedbackKind;
  tag?: string;
};

type FormState = {
  kind: EvaluationFeedbackKind;
  body: string;
  tags: string;
  metricName: string;
  metricValue: string;
};

type EvaluationFeedbackPanelProps = {
  jobId: number;
  workspaceId: number;
  projectId?: number | null;
  defaultTrainingRunId?: number | null;
};

function normalizeTags(input: string): string[] {
  return input
    .split(",")
    .map((value) => value.trim())
    .filter((value) => value.length > 0);
}

export function EvaluationFeedbackPanel({
  jobId,
  workspaceId,
  projectId,
  defaultTrainingRunId
}: EvaluationFeedbackPanelProps) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<MessageState>(null);
  const [form, setForm] = useState<FormState>({
    kind: "comment",
    body: "",
    tags: "",
    metricName: "",
    metricValue: ""
  });
  const [filters, setFilters] = useState<FeedbackFilters>({});

  const feedbackQuery = useQuery<EvaluationFeedback[], Error>({
    queryKey: ["evaluation-feedback", jobId, filters.status ?? "*", filters.kind ?? "*", filters.tag ?? ""],
    queryFn: () =>
      evaluationApi.listFeedback(jobId, {
        status: filters.status,
        kind: filters.kind,
        tag: filters.tag?.trim() ? filters.tag.trim() : undefined
      })
  });

  const invalidateFeedback = () => {
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: ["evaluation-feedback", jobId] }),
      queryClient.invalidateQueries({ queryKey: ["training-feedback-summaries"] })
    ]);
  };

  const createMutation = useMutation({
    mutationFn: async (): Promise<EvaluationFeedback> => {
      const tags = normalizeTags(form.tags);
      const metricName = form.kind === "business_metric" ? form.metricName.trim() : undefined;
      const metricValue =
        form.kind === "business_metric" && form.metricValue ? Number(form.metricValue) : undefined;
      if (form.kind === "business_metric" && metricName && Number.isNaN(metricValue)) {
        throw new Error("业务指标的数值需为数字");
      }
      return evaluationApi.createFeedback(jobId, {
        workspace_id: workspaceId,
        kind: form.kind,
        body: form.body,
        tags,
        training_run_id: defaultTrainingRunId ?? undefined,
        metric_name: metricName,
        metric_value: metricValue
      });
    },
    onSuccess: () => {
      setMessage({ type: "success", text: "反馈已添加" });
      setForm({ kind: "comment", body: "", tags: "", metricName: "", metricValue: "" });
      void invalidateFeedback();
    },
    onError: (error: Error) => {
      setMessage({ type: "error", text: error.message });
    }
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ entry, status }: { entry: EvaluationFeedback; status: EvaluationFeedbackStatus }) =>
      evaluationApi.updateFeedback(jobId, entry.id, { status }),
    onSuccess: () => {
      setMessage({ type: "success", text: "反馈状态已更新" });
      void invalidateFeedback();
    },
    onError: (error: Error) => setMessage({ type: "error", text: error.message })
  });

  const deleteMutation = useMutation({
    mutationFn: (feedbackId: number) => evaluationApi.deleteFeedback(jobId, feedbackId),
    onSuccess: () => {
      setMessage({ type: "success", text: "反馈已删除" });
      void invalidateFeedback();
    },
    onError: (error: Error) => setMessage({ type: "error", text: error.message })
  });

  const exportMutation = useMutation({
    mutationFn: (format: "markdown" | "json") =>
      evaluationApi.exportFeedback(jobId, { format, status: filters.status, kind: filters.kind, tag: filters.tag }),
    onSuccess: (payload: EvaluationFeedbackExportResult) => {
      setMessage({ type: "success", text: `已导出到 ${payload.path}` });
    },
    onError: (error: Error) => setMessage({ type: "error", text: error.message })
  });

  const handleCreate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.body.trim()) {
      setMessage({ type: "error", text: "请填写反馈内容" });
      return;
    }
    setMessage(null);
    createMutation.mutate();
  };

  const entries = useMemo(() => feedbackQuery.data ?? [], [feedbackQuery.data]);

  return (
    <section className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">反馈与复盘</h2>
          <p className="text-sm text-slate-400">记录业务观点、TODO 与指标，供后续迭代引用。</p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <button
            type="button"
            onClick={() => exportMutation.mutate("markdown")}
            className="rounded-md border border-slate-700 px-3 py-2 text-slate-200 hover:border-slate-500"
            disabled={exportMutation.isPending}
          >
            导出 Markdown
          </button>
          <button
            type="button"
            onClick={() => exportMutation.mutate("json")}
            className="rounded-md border border-slate-700 px-3 py-2 text-slate-200 hover:border-slate-500"
            disabled={exportMutation.isPending}
          >
            导出 JSON
          </button>
        </div>
      </div>

      <form className="space-y-3 rounded-md border border-slate-800 bg-slate-950/60 p-4" onSubmit={handleCreate}>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm text-slate-300">
            类型
            <select
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
              value={form.kind}
              onChange={(event) =>
                setForm((prev) => ({
                  ...prev,
                  kind: event.target.value as EvaluationFeedbackKind,
                  metricName: "",
                  metricValue: ""
                }))
              }
            >
              {KIND_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-300">
            标签（逗号分隔）
            <input
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
              value={form.tags}
              onChange={(event) => setForm((prev) => ({ ...prev, tags: event.target.value }))}
              placeholder="如：release, v1"
            />
          </label>
        </div>

        {form.kind === "business_metric" ? (
          <div className="grid gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm text-slate-300">
              指标名称
              <input
                className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
                value={form.metricName}
                onChange={(event) => setForm((prev) => ({ ...prev, metricName: event.target.value }))}
                placeholder="如：csat_target"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm text-slate-300">
              指标目标值
              <input
                className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
                value={form.metricValue}
                onChange={(event) => setForm((prev) => ({ ...prev, metricValue: event.target.value }))}
                placeholder="如：4.3"
              />
            </label>
          </div>
        ) : null}

        <label className="flex flex-col gap-1 text-sm text-slate-300">
          反馈内容
          <textarea
            className="min-h-[96px] rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
            value={form.body}
            onChange={(event) => setForm((prev) => ({ ...prev, body: event.target.value }))}
            placeholder="记录业务反馈、TODO 或指标目标"
          />
        </label>
        <div className="flex items-center gap-3">
          <button
            type="submit"
            className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-slate-900 hover:bg-emerald-400"
            disabled={createMutation.isPending}
          >
            新增反馈
          </button>
          {message ? (
            <span className={message.type === "error" ? "text-rose-300" : "text-emerald-300"}>{message.text}</span>
          ) : null}
        </div>
      </form>

      <div className="space-y-3 rounded-md border border-slate-800 bg-slate-950/40 p-4">
        <div className="grid gap-3 md:grid-cols-3">
          <label className="flex flex-col gap-1 text-xs text-slate-400">
            状态筛选
            <select
              className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
              value={filters.status ?? ""}
              onChange={(event) =>
                setFilters((prev) => ({
                  ...prev,
                  status: event.target.value ? (event.target.value as EvaluationFeedbackStatus) : undefined
                }))
              }
            >
              <option value="">全部</option>
              <option value="open">未完成</option>
              <option value="resolved">已完成</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-400">
            类型筛选
            <select
              className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
              value={filters.kind ?? ""}
              onChange={(event) =>
                setFilters((prev) => ({
                  ...prev,
                  kind: event.target.value ? (event.target.value as EvaluationFeedbackKind) : undefined
                }))
              }
            >
              <option value="">全部</option>
              {KIND_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-400">
            标签筛选
            <input
              className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
              value={filters.tag ?? ""}
              onChange={(event) => setFilters((prev) => ({ ...prev, tag: event.target.value }))}
              placeholder="输入标签关键字"
            />
          </label>
        </div>

        {feedbackQuery.isLoading ? (
          <p className="text-sm text-slate-400">加载反馈中...</p>
        ) : null}
        {feedbackQuery.isError ? (
          <p className="text-sm text-rose-300">{feedbackQuery.error?.message ?? "获取反馈失败"}</p>
        ) : null}

        <ul className="space-y-3">
          {entries.map((entry) => (
            <li key={entry.id} className="space-y-2 rounded-md border border-slate-800 bg-slate-900/60 p-3 text-sm text-slate-200">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
                <span className="rounded border border-slate-700 px-2 py-0.5 text-slate-200">
                  {KIND_OPTIONS.find((option) => option.value === entry.kind)?.label ?? entry.kind}
                </span>
                <span className={entry.status === "resolved" ? "text-emerald-300" : "text-amber-300"}>
                  {STATUS_LABEL[entry.status]}
                </span>
              </div>
              <div className="space-y-1">
                <p className="whitespace-pre-wrap text-slate-100">{entry.body}</p>
                {entry.metric_name ? (
                  <p className="text-xs text-slate-400">
                    指标：{entry.metric_name}
                    {entry.metric_value != null ? ` = ${entry.metric_value}` : ""}
                  </p>
                ) : null}
                {entry.tags.length > 0 ? (
                  <p className="text-xs text-slate-500">标签：{entry.tags.join(", ")}</p>
                ) : null}
                <p className="text-xs text-slate-500">
                  创建人 #{entry.created_by} · {new Date(entry.created_at).toLocaleString()}
                </p>
                {entry.resolved_at ? (
                  <p className="text-xs text-slate-500">
                    完成于 {new Date(entry.resolved_at).toLocaleString()}
                  </p>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <button
                  type="button"
                  onClick={() =>
                    updateStatusMutation.mutate({
                      entry,
                      status: entry.status === "resolved" ? "open" : "resolved"
                    })
                  }
                  className="rounded-md border border-slate-700 px-3 py-1 text-slate-200 hover:border-slate-500"
                  disabled={updateStatusMutation.isPending}
                >
                  {entry.status === "resolved" ? "重新打开" : "标记完成"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm("确认删除该反馈？")) {
                      deleteMutation.mutate(entry.id);
                    }
                  }}
                  className="rounded-md border border-rose-500/60 px-3 py-1 text-rose-300 hover:border-rose-500"
                  disabled={deleteMutation.isPending}
                >
                  删除
                </button>
              </div>
            </li>
          ))}
        </ul>

        {entries.length === 0 && !feedbackQuery.isLoading ? (
          <p className="text-sm text-slate-400">尚无反馈记录，欢迎添加。</p>
        ) : null}
      </div>

      <p className="text-xs text-slate-500">
        导出文件存放在知识库目录 · 工作空间 {workspaceId}
        {projectId != null ? ` / 项目 ${projectId}` : " / 通用"}
      </p>
    </section>
  );
}
