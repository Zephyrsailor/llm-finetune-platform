import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cleaningApi,
  CleaningAssignment,
  CleaningSummary,
  CleaningTemplate,
  CleaningTemplateStep,
  dataHubApi,
  Dataset,
  DatasetVersion,
  workspaceApi,
  WorkspaceDetail
} from "../../lib/api";
import { DataHubNav } from "./DataHubNav";
import { AppShell } from "../layout/AppShell";

interface TemplateFormValues {
  name: string;
  description?: string;
}

interface StepDraft {
  type: string;
  field: string;
  fields: string;
  keywords: string;
  replacement: string;
  mode: "lower" | "upper";
}

type Feedback = { type: "success" | "error"; text: string } | null;

type NavTab = "templates" | "binding" | "summary";

function parseList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function buildStepFromDraft(draft: StepDraft): CleaningTemplateStep | null {
  switch (draft.type) {
    case "deduplicate": {
      const fields = parseList(draft.fields || draft.field);
      if (fields.length === 0) {
        return null;
      }
      return {
        type: "deduplicate",
        fields
      };
    }
    case "drop_noise": {
      const keywords = parseList(draft.keywords);
      if (!draft.field || keywords.length === 0) {
        return null;
      }
      return {
        type: "drop_noise",
        field: draft.field.trim(),
        keywords
      };
    }
    case "mask_field": {
      const fields = parseList(draft.fields || draft.field);
      if (fields.length === 0) {
        return null;
      }
      return {
        type: "mask_field",
        fields,
        replacement: draft.replacement || "***"
      };
    }
    case "normalize_case": {
      if (!draft.field) {
        return null;
      }
      return {
        type: "normalize_case",
        field: draft.field.trim(),
        mode: draft.mode
      };
    }
    case "trim_whitespace": {
      if (!draft.field) {
        return null;
      }
      return {
        type: "trim_whitespace",
        field: draft.field.trim()
      };
    }
    default:
      return null;
  }
}

function StepPreview({ step, onRemove }: { step: CleaningTemplateStep; onRemove: () => void }) {
  return (
    <div className="flex items-start justify-between rounded-2xl border border-sky-100 bg-sky-50 px-4 py-3 text-xs text-slate-600">
      <div className="space-y-1">
        <div className="font-semibold text-slate-700">步骤类型：{step.type}</div>
        <pre className="whitespace-pre-wrap text-[11px] text-slate-500">{JSON.stringify(step, null, 2)}</pre>
      </div>
      <button
        type="button"
        onClick={onRemove}
        className="rounded-md border border-sky-200 px-2 py-1 text-[11px] text-sky-600 hover:bg-sky-100"
      >
        删除
      </button>
    </div>
  );
}

function SummaryPanel({ summary }: { summary: CleaningSummary }) {
  const stats = summary.stats ?? {};
  const pairs = Object.entries(stats);
  return (
    <div className="space-y-4 rounded-3xl border border-slate-200 bg-white px-6 py-6 text-sm text-slate-600 shadow-sm">
      <h3 className="text-sm font-semibold text-slate-900">运行指标</h3>
      {pairs.length === 0 ? (
        <p className="text-xs text-slate-500">暂无统计数据。</p>
      ) : (
        <dl className="grid gap-3 text-xs text-slate-500 md:grid-cols-2">
          {pairs.map(([key, value]) => (
            <div key={key}>
              <dt className="text-slate-400">{key}</dt>
              <dd className="font-mono text-[11px] text-slate-700">{JSON.stringify(value)}</dd>
            </div>
          ))}
        </dl>
      )}
      {summary.export_manifest ? (
        <div className="rounded-2xl bg-slate-50 px-4 py-2 text-xs text-slate-500">
          已生成导出文件：{Object.keys(summary.export_manifest).join(", ")}
        </div>
      ) : null}
    </div>
  );
}

function HeroStat({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="rounded-3xl bg-gradient-to-br from-sky-50 via-white to-white px-6 py-6 shadow-sm">
      <div className="text-sm font-semibold text-slate-500">{label}</div>
      <div className="mt-4 flex items-baseline gap-2 text-3xl font-semibold text-slate-900">
        <span>{value}</span>
        {unit ? <span className="text-sm text-slate-500">{unit}</span> : null}
      </div>
      <div className="mt-2 text-xs text-slate-400">等待接入真实指标</div>
    </div>
  );
}

function SecondaryNav({ activeTab, onChange }: { activeTab: NavTab; onChange: (tab: NavTab) => void }) {
  const tabs: Array<{ key: NavTab; label: string }> = [
    { key: "templates", label: "模板管理" },
    { key: "binding", label: "模板绑定" },
    { key: "summary", label: "清洗结果" }
  ];
  return (
    <div className="flex gap-2">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => onChange(tab.key)}
          className={`rounded-2xl px-4 py-2 text-sm font-medium transition ${
            tab.key === activeTab
              ? "bg-sky-500/10 text-sky-600"
              : "bg-white text-slate-500 hover:bg-slate-100 hover:text-slate-700"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export function CleaningPipelinePage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<NavTab>("templates");
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [selectedDatasetId, setSelectedDatasetId] = useState<number | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [steps, setSteps] = useState<CleaningTemplateStep[]>([]);
  const [stepDraft, setStepDraft] = useState<StepDraft>({
    type: "deduplicate",
    field: "",
    fields: "",
    keywords: "",
    replacement: "***",
    mode: "lower"
  });
  const [templateFeedback, setTemplateFeedback] = useState<Feedback>(null);
  const [assignmentFeedback, setAssignmentFeedback] = useState<Feedback>(null);
  const [summaryFeedback, setSummaryFeedback] = useState<Feedback>(null);

  const templateForm = useForm<TemplateFormValues>({
    defaultValues: {
      name: "",
      description: ""
    }
  });

  const workspaceQuery = useQuery<WorkspaceDetail[]>({
    queryKey: ["workspaces"],
    queryFn: () => workspaceApi.list()
  });

  useEffect(() => {
    if (!workspaceQuery.data || workspaceQuery.data.length === 0) {
      return;
    }
    if (selectedWorkspaceId == null) {
      setSelectedWorkspaceId(workspaceQuery.data[0].id);
    }
  }, [workspaceQuery.data, selectedWorkspaceId]);

  const templatesQuery = useQuery<CleaningTemplate[]>({
    queryKey: ["cleaning-templates", selectedWorkspaceId],
    enabled: selectedWorkspaceId != null,
    queryFn: () => cleaningApi.listTemplates(selectedWorkspaceId ?? 0)
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

  const assignmentQuery = useQuery<CleaningAssignment | null>({
    queryKey: ["cleaning-assignment", selectedDatasetId],
    enabled: selectedDatasetId != null,
    queryFn: () => cleaningApi.getAssignment(selectedDatasetId ?? 0)
  });

  const summaryQuery = useQuery<CleaningSummary>({
    queryKey: ["cleaning-summary", selectedDatasetId, selectedVersionId],
    enabled: false,
    queryFn: () => cleaningApi.getSummary(selectedDatasetId ?? 0, selectedVersionId ?? 0)
  });

  const createTemplateMutation = useMutation({
    mutationFn: cleaningApi.createTemplate,
    onSuccess: () => {
      setTemplateFeedback({ type: "success", text: "模板创建成功" });
      setSteps([]);
      templateForm.reset();
      queryClient.invalidateQueries({ queryKey: ["cleaning-templates", selectedWorkspaceId] });
    },
    onError: (error: Error) => {
      setTemplateFeedback({ type: "error", text: error.message });
    }
  });

  const addStep = () => {
    const step = buildStepFromDraft(stepDraft);
    if (!step) {
      setTemplateFeedback({ type: "error", text: "请完善步骤参数后再添加。" });
      return;
    }
    setSteps((prev) => [...prev, step]);
    setStepDraft((draft) => ({ ...draft, field: "", fields: "", keywords: "" }));
    setTemplateFeedback(null);
  };

  const removeStep = (index: number) => {
    setSteps((prev) => prev.filter((_, idx) => idx !== index));
  };

  const onCreateTemplate = templateForm.handleSubmit(async (values) => {
    if (selectedWorkspaceId == null) {
      setTemplateFeedback({ type: "error", text: "请选择工作空间。" });
      return;
    }
    if (steps.length === 0) {
      setTemplateFeedback({ type: "error", text: "至少添加一个清洗步骤。" });
      return;
    }
    setTemplateFeedback(null);
    await createTemplateMutation.mutateAsync({
      workspaceId: selectedWorkspaceId,
      name: values.name.trim(),
      description: values.description?.trim() || undefined,
      steps
    });
  });

  const assignTemplateMutation = useMutation({
    mutationFn: ({ datasetId, templateId }: { datasetId: number; templateId: number | null }) =>
      cleaningApi.assignTemplate(datasetId, { templateId, enabled: templateId != null }),
    onSuccess: () => {
      setAssignmentFeedback({ type: "success", text: "模板绑定已更新。" });
      queryClient.invalidateQueries({ queryKey: ["cleaning-assignment", selectedDatasetId] });
    },
    onError: (error: Error) => {
      setAssignmentFeedback({ type: "error", text: error.message });
    }
  });

  const handleAssignTemplate = async (templateId: number | null) => {
    if (!selectedDatasetId) {
      setAssignmentFeedback({ type: "error", text: "请先选择数据集。" });
      return;
    }
    setAssignmentFeedback(null);
    await assignTemplateMutation.mutateAsync({ datasetId: selectedDatasetId, templateId });
  };

  const handleLoadSummary = async () => {
    if (!selectedDatasetId || !selectedVersionId) {
      setSummaryFeedback({ type: "error", text: "请选择数据集与版本。" });
      return;
    }
    setSummaryFeedback(null);
    const result = await summaryQuery.refetch();
    if (result.error) {
      setSummaryFeedback({ type: "error", text: (result.error as Error).message });
    }
  };

  const handleDownload = async (format: "jsonl" | "csv") => {
    if (!selectedDatasetId || !selectedVersionId) {
      setSummaryFeedback({ type: "error", text: "请先选择数据集版本。" });
      return;
    }
    try {
      const blob = await cleaningApi.downloadExport(selectedDatasetId, selectedVersionId, format);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `cleaning-${selectedDatasetId}-v${selectedVersionId}.${format}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setSummaryFeedback({ type: "success", text: `已开始下载 ${format} 文件。` });
    } catch (error) {
      setSummaryFeedback({ type: "error", text: (error as Error).message });
    }
  };

  const currentAssignment = assignmentQuery.data;
  const assignedTemplate = useMemo(() => {
    if (!currentAssignment || !currentAssignment.enabled) {
      return null;
    }
    return (templatesQuery.data ?? []).find((template) => template.id === currentAssignment.template_id) ?? null;
  }, [currentAssignment, templatesQuery.data]);

  const workspaceOptions = workspaceQuery.data ?? [];
  const datasetOptions = useMemo(() => datasetsQuery.data ?? [], [datasetsQuery.data]);
  const versionOptions = useMemo(() => versionsQuery.data ?? [], [versionsQuery.data]);

  const toolbar = (
    <div className="mx-auto w-full max-w-7xl px-10 py-4">
      <DataHubNav />
    </div>
  );

  return (
    <AppShell
      title="数据集与流水线"
      subtitle="导入多源数据、配置清洗模板并监控流水线运行"
      searchPlaceholder="搜索数据集、流水线或模板"
      primaryAction={{ label: "新建训练", to: "/training/wizard" }}
      toolbar={toolbar}
    >
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <HeroStat label="已登记数据集" value={String(datasetOptions.length)} unit="个" />
        <HeroStat label="激活清洗模板" value={String(templatesQuery.data?.length ?? 0)} unit="套" />
        <HeroStat label="最近流转版本" value={selectedVersionId ? `v${selectedVersionId}` : "待选择"} />
        <HeroStat label="待处理告警" value="0" unit="条" />
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white px-6 py-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor="workspace-select">
              工作空间
            </label>
            <select
              id="workspace-select"
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
              value={selectedWorkspaceId ?? ""}
              onChange={(event) => {
                const workspaceId = Number(event.target.value);
                setSelectedWorkspaceId(Number.isNaN(workspaceId) ? null : workspaceId);
                setSelectedDatasetId(null);
                setSelectedVersionId(null);
              }}
              disabled={workspaceQuery.isLoading || workspaceOptions.length === 0}
            >
              {workspaceOptions.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span>数据集</span>
            <select
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
              value={selectedDatasetId ?? ""}
              onChange={(event) => {
                const datasetId = Number(event.target.value);
                setSelectedDatasetId(Number.isNaN(datasetId) ? null : datasetId);
                setSelectedVersionId(null);
              }}
              disabled={datasetOptions.length === 0}
            >
              <option value="">选择数据集</option>
              {datasetOptions.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>
                  {dataset.name}
                </option>
              ))}
            </select>
            <select
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
              value={selectedVersionId ?? ""}
              onChange={(event) => {
                const versionId = Number(event.target.value);
                setSelectedVersionId(Number.isNaN(versionId) ? null : versionId);
              }}
              disabled={versionOptions.length === 0}
            >
              <option value="">选择版本</option>
              {versionOptions.map((version) => (
                <option key={version.id} value={version.id}>
                  v{version.version}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      <section className="space-y-6 rounded-3xl border border-slate-200 bg-white px-6 py-6 shadow-sm">
        <SecondaryNav activeTab={activeTab} onChange={setActiveTab} />

        {activeTab === "templates" ? (
          <div className="space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">清洗模板管理</h2>
              <p className="mt-1 text-xs text-slate-500">为各类数据集配置去重、噪声过滤与脱敏策略。</p>
            </div>

            <form className="grid gap-4 md:grid-cols-2" onSubmit={onCreateTemplate}>
              <div className="space-y-2">
                <label className="block text-xs font-semibold text-slate-600" htmlFor="template-name">
                  模板名称
                </label>
                <input
                  id="template-name"
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
                  placeholder="例如：默认脱敏模板"
                  {...templateForm.register("name", { required: true })}
                />
              </div>
              <div className="space-y-2">
                <label className="block text-xs font-semibold text-slate-600" htmlFor="template-desc">
                  模板说明
                </label>
                <textarea
                  id="template-desc"
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
                  placeholder="可选：描述该模板适用场景"
                  rows={2}
                  {...templateForm.register("description")}
                />
              </div>

              <div className="grid gap-3 md:col-span-2 md:grid-cols-5">
                <label className="text-xs text-slate-500">
                  类型
                  <select
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
                    value={stepDraft.type}
                    onChange={(event) => setStepDraft((prev) => ({ ...prev, type: event.target.value }))}
                  >
                    <option value="deduplicate">去重</option>
                    <option value="drop_noise">噪声过滤</option>
                    <option value="mask_field">字段脱敏</option>
                    <option value="normalize_case">大小写归一</option>
                    <option value="trim_whitespace">空白裁剪</option>
                  </select>
                </label>
                <label className="text-xs text-slate-500">
                  字段
                  <input
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
                    placeholder="topic,title"
                    value={stepDraft.fields || stepDraft.field}
                    onChange={(event) =>
                      setStepDraft((prev) => ({ ...prev, fields: event.target.value, field: event.target.value }))
                    }
                  />
                </label>
                <label className="text-xs text-slate-500">
                  关键词
                  <input
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
                    placeholder="违规,违禁"
                    value={stepDraft.keywords}
                    onChange={(event) => setStepDraft((prev) => ({ ...prev, keywords: event.target.value }))}
                    disabled={stepDraft.type !== "drop_noise"}
                  />
                </label>
                <label className="text-xs text-slate-500">
                  替换文本
                  <input
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
                    placeholder="***"
                    value={stepDraft.replacement}
                    onChange={(event) => setStepDraft((prev) => ({ ...prev, replacement: event.target.value }))}
                    disabled={stepDraft.type !== "mask_field"}
                  />
                </label>
                <label className="text-xs text-slate-500">
                  大小写模式
                  <select
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
                    value={stepDraft.mode}
                    onChange={(event) => setStepDraft((prev) => ({ ...prev, mode: event.target.value as StepDraft["mode"] }))}
                    disabled={stepDraft.type !== "normalize_case"}
                  >
                    <option value="lower">lower</option>
                    <option value="upper">upper</option>
                  </select>
                </label>
              </div>

              <div className="flex items-center gap-3 md:col-span-2">
                <button
                  type="button"
                  onClick={addStep}
                  className="rounded-xl bg-sky-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-400"
                >
                  添加步骤
                </button>
                <span className="text-xs text-slate-500">当前步骤：{steps.length} 个</span>
              </div>
            </form>

            {templateFeedback && (
              <div
                className={`rounded-2xl border px-4 py-3 text-sm ${
                  templateFeedback.type === "success"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-rose-200 bg-rose-50 text-rose-700"
                }`}
              >
                {templateFeedback.text}
              </div>
            )}

            {steps.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-slate-900">预览步骤</h3>
                <div className="space-y-3">
                  {steps.map((step, index) => (
                    <StepPreview key={`${step.type}-${index}`} step={step} onRemove={() => removeStep(index)} />
                  ))}
                </div>
              </div>
            )}

            <div className="flex justify-end">
              <button
                type="button"
                onClick={onCreateTemplate}
                className="inline-flex items-center rounded-xl bg-sky-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-500"
                disabled={createTemplateMutation.isPending}
              >
                {createTemplateMutation.isPending ? "创建中..." : "保存模板"}
              </button>
            </div>

            <div className="space-y-3 rounded-3xl border border-slate-200 bg-slate-50 px-6 py-6">
              <h3 className="text-sm font-semibold text-slate-900">已有模板</h3>
              <ul className="grid gap-3 text-sm text-slate-600 md:grid-cols-2">
                {(templatesQuery.data ?? []).map((template) => (
                  <li
                    key={template.id}
                    className="rounded-2xl border border-white/60 bg-white px-4 py-3 shadow-sm transition hover:border-sky-200"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-800">{template.name}</span>
                      <span className="text-xs text-slate-400">步骤 {template.steps.length}</span>
                    </div>
                    {template.description && (
                      <p className="mt-1 text-xs text-slate-500">{template.description}</p>
                    )}
                  </li>
                ))}
                {templatesQuery.data && templatesQuery.data.length === 0 ? (
                  <li className="text-xs text-slate-500">尚无模板，创建后可在此管理。</li>
                ) : null}
              </ul>
            </div>
          </div>
        ) : null}

        {activeTab === "binding" ? (
          <div className="space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">模板绑定与触发</h2>
              <p className="mt-1 text-xs text-slate-500">为数据集选择默认清洗模板并触发流水线。</p>
            </div>

            <div className="space-y-3 rounded-3xl border border-slate-200 bg-slate-50 px-6 py-6">
              <h3 className="text-sm font-semibold text-slate-900">当前绑定</h3>
              <p className="text-xs text-slate-500">
                {assignedTemplate ? `已绑定模板：${assignedTemplate.name}` : "尚未绑定模板"}
              </p>
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => handleAssignTemplate(null)}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-medium text-slate-600 hover:border-slate-300"
                >
                  清除绑定
                </button>
                {(templatesQuery.data ?? []).map((template) => (
                  <button
                    key={template.id}
                    type="button"
                    onClick={() => handleAssignTemplate(template.id)}
                    className="rounded-xl border border-sky-200 bg-white px-4 py-2 text-xs font-medium text-sky-600 hover:bg-sky-50"
                  >
                    {template.name}
                  </button>
                ))}
              </div>
              {assignmentFeedback && (
                <div
                  className={`rounded-2xl border px-4 py-2 text-xs ${
                    assignmentFeedback.type === "success"
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : "border-rose-200 bg-rose-50 text-rose-700"
                  }`}
                >
                  {assignmentFeedback.text}
                </div>
              )}
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleLoadSummary}
                className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-500"
              >
                拉取最新清洗结果
              </button>
              <button
                type="button"
                onClick={() => handleDownload("jsonl")}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 hover:border-slate-300"
              >
                导出 JSONL
              </button>
              <button
                type="button"
                onClick={() => handleDownload("csv")}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 hover:border-slate-300"
              >
                导出 CSV
              </button>
            </div>

            {summaryFeedback && (
              <div
                className={`rounded-2xl border px-4 py-2 text-sm ${
                  summaryFeedback.type === "success"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-rose-200 bg-rose-50 text-rose-700"
                }`}
              >
                {summaryFeedback.text}
              </div>
            )}
          </div>
        ) : null}

        {activeTab === "summary" ? (
          <div className="space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">清洗结果总览</h2>
              <p className="mt-1 text-xs text-slate-500">查看关键指标、导出记录与最近的流水线状态。</p>
            </div>

            {summaryQuery.data ? (
              <SummaryPanel summary={summaryQuery.data} />
            ) : (
              <p className="rounded-3xl border border-slate-200 bg-white px-6 py-6 text-sm text-slate-500">
                尚未加载清洗结果，请先在“模板绑定”标签触发拉取。
              </p>
            )}
          </div>
        ) : null}
      </section>
    </AppShell>
  );
}
