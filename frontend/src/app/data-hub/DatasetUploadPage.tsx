import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";

import {
  CreateDatasetPayload,
  DataCleaningJob,
  Dataset,
  DatasetSourceType,
  DatasetVersion,
  DatasetVersionCreateResult,
  dataHubApi,
  workspaceApi,
  WorkspaceDetail
} from "../../lib/api";
import { DataHubNav } from "./DataHubNav";
import { AppShell } from "../layout/AppShell";

type Feedback = { type: "success" | "error"; text: string };

interface DatasetFormValues {
  workspaceId: string;
  name: string;
  description?: string;
  dataType?: string;
  customDataType?: string;
  tags?: string;
  notes?: string;
  sourceType: DatasetSourceType;
  sourceUri?: string;
  referenceDatasetId?: string;
  file?: FileList;
}

const SOURCE_OPTIONS: { value: DatasetSourceType; label: string }[] = [
  { value: "upload", label: "上传文件" },
  { value: "external", label: "对象存储/外部地址" },
  { value: "reference", label: "引用已有数据集" }
];

const DATA_TYPE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "conversation/jsonl", label: "会话 JSONL" },
  { value: "qa/jsonl", label: "问答 JSONL" },
  { value: "classification/csv", label: "分类 CSV" },
  { value: "knowledge/markdown", label: "知识库 Markdown" },
  { value: "custom", label: "自定义…" }
];

function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) {
    return "未知";
  }
  if (bytes < 1024) {
    return `${bytes}B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(2)}KB`;
  }
  if (bytes < 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(2)}MB`;
  }
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)}GB`;
}

function formatDateTime(value?: string | null): string {
  if (!value) {
    return "--";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export function DatasetUploadPage() {
  const [workspaces, setWorkspaces] = useState<WorkspaceDetail[]>([]);
  const [workspaceLoading, setWorkspaceLoading] = useState(true);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);

  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [creating, setCreating] = useState(false);
  const [triggeringVersion, setTriggeringVersion] = useState(false);
  const [createdDataset, setCreatedDataset] = useState<Dataset | null>(null);
  const [latestVersion, setLatestVersion] = useState<DatasetVersion | null>(null);
  const [latestJob, setLatestJob] = useState<DataCleaningJob | null>(null);
  const [cleaningNotes, setCleaningNotes] = useState("");

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { isSubmitting }
  } = useForm<DatasetFormValues>({
    defaultValues: {
      workspaceId: "",
      dataType: "",
      customDataType: "",
      sourceType: "upload"
    }
  });

  const watchedSourceType = watch("sourceType");
  const watchedDataType = watch("dataType");

  useEffect(() => {
    async function loadWorkspaces() {
      try {
        const data = await workspaceApi.list();
        setWorkspaces(data);
      } catch (error) {
        setWorkspaceError((error as Error).message);
      } finally {
        setWorkspaceLoading(false);
      }
    }
    loadWorkspaces();
  }, []);

  const activeWorkspace = workspaces[0] ?? null;
  const activeWorkspaceName = activeWorkspace?.name ?? "未配置工作空间";
  const workspaceReady = Boolean(activeWorkspace);

  useEffect(() => {
    if (activeWorkspace) {
      setValue("workspaceId", String(activeWorkspace.id));
    }
  }, [activeWorkspace, setValue]);

  const onSubmit = handleSubmit(async (values) => {
    if (!values.workspaceId) {
      setFeedback({ type: "error", text: "当前缺少可用工作空间，请先联系管理员创建。" });
      return;
    }
    if (values.sourceType === "upload" && (!values.file || values.file.length === 0)) {
      setFeedback({ type: "error", text: "请选择要上传的文件。" });
      return;
    }
    if (values.sourceType === "external" && !values.sourceUri) {
      setFeedback({ type: "error", text: "请填写对象存储路径或外部链接。" });
      return;
    }
    if (values.sourceType === "reference" && !values.referenceDatasetId) {
      setFeedback({ type: "error", text: "请提供要引用的数据集 ID。" });
      return;
    }

    const resolvedDataType =
      values.dataType === "custom"
        ? values.customDataType?.trim() || undefined
        : values.dataType?.trim() || undefined;

    const payload: CreateDatasetPayload = {
      workspaceId: Number(values.workspaceId),
      name: values.name.trim(),
      description: values.description?.trim() || undefined,
      dataType: resolvedDataType,
      tags:
        values.tags && values.tags.trim().length > 0
          ? values.tags
              .split(",")
              .map((tag) => tag.trim())
              .filter(Boolean)
          : [],
      notes: values.notes?.trim() || undefined,
      sourceType: values.sourceType,
      sourceUri: values.sourceUri?.trim() || undefined,
      referenceDatasetId: values.referenceDatasetId ? Number(values.referenceDatasetId) : undefined,
      file: values.file && values.file.length > 0 ? values.file[0] : undefined
    };

    setCreating(true);
    setFeedback(null);
    setLatestVersion(null);
    setLatestJob(null);
    try {
      const dataset = await dataHubApi.createDataset(payload);
      setCreatedDataset(dataset);
      setCleaningNotes(values.notes?.trim() ?? "");
      setFeedback({ type: "success", text: "数据集创建成功，可继续触发清洗流水线。" });
      reset({
        workspaceId: values.workspaceId,
        sourceType: values.sourceType,
        name: "",
        description: "",
        dataType: "",
        customDataType: "",
        tags: "",
        notes: "",
        sourceUri: "",
        referenceDatasetId: "",
        file: undefined
      });
    } catch (error) {
      setFeedback({ type: "error", text: (error as Error).message });
      setCreatedDataset(null);
    } finally {
      setCreating(false);
    }
  });

  const triggerCleaning = async () => {
    if (!createdDataset) {
      return;
    }
    setTriggeringVersion(true);
    setFeedback(null);
    try {
      const result: DatasetVersionCreateResult = await dataHubApi.createVersion(createdDataset.id, {
        notes: cleaningNotes.trim() || undefined
      });
      setLatestVersion(result.version);
      setLatestJob(result.job);
      setFeedback({
        type: "success",
        text: `清洗任务已启动，当前状态：${
          result.job.status === "completed" ? "已完成（占位流程）" : result.job.status
        }`
      });
    } catch (error) {
      setFeedback({ type: "error", text: (error as Error).message });
    } finally {
      setTriggeringVersion(false);
    }
  };

  const toolbar = (
    <div className="mx-auto w-full max-w-7xl px-8 py-3">
      <DataHubNav />
    </div>
  );

  return (
    <AppShell
      title="数据集与流水线"
      subtitle="导入多源数据、监控清洗状态并掌握质量概览"
      searchPlaceholder="搜索数据集、流水线或清洗模板"
      primaryAction={{ label: "新建训练任务", to: "/training/wizard" }}
      toolbar={toolbar}
    >
      <section className="grid gap-6 xl:grid-cols-[2fr_1fr]">
        <div className="space-y-6">
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col gap-2 border-b border-slate-200 pb-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">新建数据集</h2>
                <p className="text-sm text-slate-500">支持上传文件、引用外部存储或复用已登记数据集。</p>
              </div>
              {workspaceLoading && <span className="text-xs text-slate-500">正在加载工作空间...</span>}
              {workspaceError && <span className="text-xs text-rose-500">加载工作空间失败：{workspaceError}</span>}
            </div>

            <form className="mt-6 space-y-6" onSubmit={onSubmit}>
              <input type="hidden" {...register("workspaceId")} />
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-slate-50 px-4 py-3">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-semibold text-slate-500">目标工作空间</span>
                  <span className="inline-flex items-center rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 shadow-sm">
                    {workspaceLoading ? "正在加载..." : activeWorkspaceName}
                  </span>
                </div>
                {workspaceError && <span className="text-xs text-rose-500">{workspaceError}</span>}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium text-slate-700" htmlFor="dataset-name">
                    数据集名称
                  </label>
                  <input
                    id="dataset-name"
                    type="text"
                    {...register("name", { required: true })}
                    placeholder="如：retail_orders_v2"
                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-200"
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium text-slate-700" htmlFor="dataset-type">
                    数据类型
                  </label>
                  <select
                    id="dataset-type"
                    {...register("dataType")}
                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-200"
                  >
                    <option value="">请选择类型</option>
                    {DATA_TYPE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  {watchedDataType === "custom" && (
                    <input
                      type="text"
                      {...register("customDataType")}
                      placeholder="请输入自定义类型代码"
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-200"
                    />
                  )}
                </div>
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium text-slate-700" htmlFor="dataset-tags">
                    标签
                  </label>
                  <input
                    id="dataset-tags"
                    type="text"
                    {...register("tags")}
                    placeholder="例如：finance,chatlog"
                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-200"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="dataset-description">
                  描述
                </label>
                <textarea
                  id="dataset-description"
                  rows={3}
                  {...register("description")}
                  placeholder="说明数据来源、用途以及特殊处理要求"
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-200"
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium text-slate-700">数据来源</label>
                  <div className="flex flex-wrap gap-2">
                    {SOURCE_OPTIONS.map((option) => (
                      <label key={option.value} className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                        <input
                          type="radio"
                          value={option.value}
                          {...register("sourceType")}
                          className="text-blue-600 focus:ring-blue-500"
                        />
                        {option.label}
                      </label>
                    ))}
                  </div>
                </div>

                {watchedSourceType === "external" && (
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="source-uri">
                      对象存储 URI
                    </label>
                    <input
                      id="source-uri"
                      type="text"
                      {...register("sourceUri")}
                      placeholder="如：s3://bucket/path/to/file.jsonl"
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-200"
                    />
                  </div>
                )}

                {watchedSourceType === "reference" && (
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="reference-dataset">
                      引用数据集 ID
                    </label>
                    <input
                      id="reference-dataset"
                      type="text"
                      {...register("referenceDatasetId")}
                      placeholder="请输入已有数据集 ID"
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-200"
                    />
                  </div>
                )}

                {watchedSourceType === "upload" && (
                  <div className="flex flex-col gap-2 md:col-span-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="dataset-file">
                      上传文件
                    </label>
                    <input
                      id="dataset-file"
                      type="file"
                      accept=".jsonl,.json,.csv,.txt"
                      {...register("file")}
                      className="block w-full rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3 py-6 text-sm text-slate-500 file:mr-4 file:rounded-md file:border-0 file:bg-blue-600 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-blue-500"
                    />
                    <span className="text-xs text-slate-500">支持 JSONL / CSV / TXT，单文件 2 GB 以内。</span>
                  </div>
                )}
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="notes">
                  清洗备注
                </label>
                <textarea
                  id="notes"
                  rows={2}
                  {...register("notes")}
                  placeholder="记录适配模板、字段映射或清洗注意事项"
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-200"
                />
              </div>

              {feedback && (
                <div
                  className={`rounded-lg border px-4 py-3 text-sm ${
                    feedback.type === "success"
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : "border-rose-200 bg-rose-50 text-rose-600"
                  }`}
                >
                  {feedback.text}
                </div>
              )}

              <div className="flex justify-end">
                <button
                  type="submit"
                disabled={isSubmitting || creating || !workspaceReady}
                  className="inline-flex items-center rounded-md bg-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {creating ? "正在创建..." : "提交数据集"}
                </button>
              </div>
            </form>
          </section>

          {createdDataset && (
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex flex-col gap-2 border-b border-slate-200 pb-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">数据集概览</h2>
                  <p className="text-sm text-slate-500">已成功登记的数据集，后续可在右侧触发清洗。</p>
                </div>
              </div>

              <dl className="mt-6 grid gap-4 md:grid-cols-2">
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">数据集 ID</dt>
                  <dd className="mt-1 text-sm font-semibold text-slate-800">{createdDataset.id}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">名称</dt>
                  <dd className="mt-1 text-sm font-semibold text-slate-800">{createdDataset.name}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">来源类型</dt>
                  <dd className="mt-1 text-sm font-semibold text-slate-800">{createdDataset.source_type}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">数据类型</dt>
                  <dd className="mt-1 text-sm font-semibold text-slate-800">
                    {createdDataset.data_type ?? "未指定"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">标签</dt>
                  <dd className="mt-1 text-sm font-semibold text-slate-800">
                    {createdDataset.tags.length ? createdDataset.tags.join("、") : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">文件大小</dt>
                  <dd className="mt-1 text-sm font-semibold text-slate-800">
                    {formatBytes(createdDataset.file_size_bytes)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">创建时间</dt>
                  <dd className="mt-1 text-sm font-semibold text-slate-800">{formatDateTime(createdDataset.created_at)}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">更新时间</dt>
                  <dd className="mt-1 text-sm font-semibold text-slate-800">{formatDateTime(createdDataset.updated_at)}</dd>
                </div>
              </dl>
            </section>
          )}
        </div>

        <aside className="space-y-6">
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col gap-2 border-b border-slate-200 pb-4">
              <h3 className="text-lg font-semibold text-slate-900">清洗流水线</h3>
              <p className="text-sm text-slate-500">根据备注触发清洗模板并查看任务反馈。</p>
            </div>
            <div className="mt-6 space-y-4">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="cleaning-notes">
                  执行说明
                </label>
                <textarea
                  id="cleaning-notes"
                  value={cleaningNotes}
                  onChange={(event) => setCleaningNotes(event.target.value)}
                  rows={3}
                  placeholder="记录清洗模板、质检维度或负责人"
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-200"
                  disabled={!createdDataset}
                />
              </div>
              <button
                type="button"
                onClick={triggerCleaning}
                disabled={!createdDataset || triggeringVersion}
                className="inline-flex w-full justify-center rounded-md bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {triggeringVersion ? "正在触发..." : "启动清洗任务"}
              </button>
            </div>
            {!createdDataset && (
              <p className="mt-4 text-xs text-slate-500">请先创建数据集，随后可在此触发清洗。</p>
            )}
          </section>

          {latestVersion && (
            <section className="rounded-2xl border border-slate-200 bg-slate-50 p-6 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900">最新版本信息</h3>
              <dl className="mt-4 space-y-3 text-sm text-slate-600">
                <div className="flex justify-between">
                  <dt>版本号</dt>
                  <dd className="font-medium text-slate-800">v{latestVersion.version}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>状态</dt>
                  <dd className="font-medium text-slate-800">{latestVersion.status}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>创建时间</dt>
                  <dd className="text-right text-slate-600">{formatDateTime(latestVersion.created_at)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>更新时间</dt>
                  <dd className="text-right text-slate-600">{formatDateTime(latestVersion.updated_at)}</dd>
                </div>
              </dl>
            </section>
          )}

          {latestJob && (
            <section className="rounded-2xl border border-slate-200 bg-slate-50 p-6 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900">清洗任务追踪</h3>
              <dl className="mt-4 space-y-3 text-sm text-slate-600">
                <div className="flex justify-between">
                  <dt>任务 ID</dt>
                  <dd className="font-medium text-slate-800">{latestJob.id}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>状态</dt>
                  <dd className="font-medium text-slate-800">{latestJob.status}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>触发时间</dt>
                  <dd className="font-medium text-slate-800">{formatDateTime(latestJob.created_at)}</dd>
                </div>
              </dl>
              <p className="mt-4 text-xs text-slate-500">默认开启 eager 模式，便于本地快速验证流程。</p>
            </section>
          )}
        </aside>
      </section>
    </AppShell>
  );
}
