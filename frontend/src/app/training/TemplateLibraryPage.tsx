import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  TrainingAdapterType,
  TrainingJob,
  TrainingTemplate,
  trainingApi,
  workspaceApi,
  WorkspaceDetail
} from "../../lib/api";
import { TrainingNav } from "./TrainingNav";

type TemplateFormValues = {
  name: string;
  baseModel: string;
  adapterType: TrainingAdapterType;
  description?: string;
  learningRate: number;
  loraRank: number;
  numEpochs: number;
  batchSize: number;
  extraParams: string;
};

type TrainingJobFormValues = {
  templateId: string;
  datasetVersionId: string;
  datasetFormatVersionId?: string;
  projectId?: string;
  notes?: string;
  overrideParams?: string;
};

type Feedback = { type: "success" | "error"; text: string } | null;

const DEFAULT_TEMPLATE_VALUES: TemplateFormValues = {
  name: "",
  baseModel: "meta-llama/Llama-3-8b-instruct",
  adapterType: "lora",
  description: "",
  learningRate: 5e-4,
  loraRank: 16,
  numEpochs: 3,
  batchSize: 4,
  extraParams: ""
};

const KNOWN_PARAM_KEYS = new Set([
  "learning_rate",
  "lora_rank",
  "num_epochs",
  "per_device_train_batch_size",
  "lora_alpha",
  "gradient_accumulation_steps",
  "gradient_checkpointing"
]);

const ADAPTER_LABELS: Record<TrainingAdapterType, string> = {
  lora: "LoRA",
  qlora: "QLoRA",
  dora: "DoRA",
  "full-finetune": "全量微调"
};

function buildParams(values: TemplateFormValues, extra: Record<string, unknown>): Record<string, unknown> {
  const params: Record<string, unknown> = {
    learning_rate: values.learningRate,
    lora_rank: values.loraRank,
    num_epochs: values.numEpochs,
    per_device_train_batch_size: values.batchSize
  };
  return { ...params, ...extra };
}

function parseExtraParams(text: string): Record<string, unknown> | never {
  if (!text.trim()) {
    return {};
  }
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch (error) {
    throw new Error("额外参数必须为 JSON 对象格式。");
  }
  throw new Error("额外参数必须为 JSON 对象格式。");
}

export function TemplateLibraryPage() {
  const queryClient = useQueryClient();
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [editingTemplate, setEditingTemplate] = useState<TrainingTemplate | null>(null);
  const [templateFeedback, setTemplateFeedback] = useState<Feedback>(null);
  const [jobFeedback, setJobFeedback] = useState<Feedback>(null);
  const [lastJob, setLastJob] = useState<TrainingJob | null>(null);

  const templateForm = useForm<TemplateFormValues>({
    defaultValues: DEFAULT_TEMPLATE_VALUES
  });

  const jobForm = useForm<TrainingJobFormValues>({
    defaultValues: {
      templateId: "",
      datasetVersionId: "",
      datasetFormatVersionId: "",
      projectId: "",
      notes: "",
      overrideParams: ""
    }
  });

  const workspaceQuery = useQuery<WorkspaceDetail[]>({
    queryKey: ["workspaces"],
    queryFn: () => workspaceApi.list(),
    refetchOnWindowFocus: false
  });

  const templatesQuery = useQuery<TrainingTemplate[]>({
    queryKey: ["training-templates", selectedWorkspaceId],
    enabled: selectedWorkspaceId != null,
    queryFn: () => trainingApi.listTemplates(selectedWorkspaceId ?? 0),
    refetchOnWindowFocus: false
  });

  const createTemplateMutation = useMutation({
    mutationFn: trainingApi.createTemplate,
    onSuccess: () => {
      setTemplateFeedback({ type: "success", text: "模板创建成功。" });
      setEditingTemplate(null);
      templateForm.reset(DEFAULT_TEMPLATE_VALUES);
      queryClient.invalidateQueries({ queryKey: ["training-templates", selectedWorkspaceId] });
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "模板创建失败。";
      setTemplateFeedback({ type: "error", text: message });
    }
  });

  const updateTemplateMutation = useMutation({
    mutationFn: ({
      templateId,
      payload
    }: {
      templateId: number;
      payload: {
        name?: string;
        base_model?: string;
        adapter_type?: TrainingAdapterType;
        description?: string | null;
        params?: Record<string, unknown>;
      };
    }) => trainingApi.updateTemplate(templateId, payload),
    onSuccess: () => {
      setTemplateFeedback({ type: "success", text: "模板已更新。" });
      setEditingTemplate(null);
      templateForm.reset(DEFAULT_TEMPLATE_VALUES);
      queryClient.invalidateQueries({ queryKey: ["training-templates", selectedWorkspaceId] });
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "模板更新失败。";
      setTemplateFeedback({ type: "error", text: message });
    }
  });

  const cloneTemplateMutation = useMutation({
    mutationFn: ({ templateId, name }: { templateId: number; name?: string }) =>
      trainingApi.cloneTemplate(templateId, { name }),
    onSuccess: () => {
      setTemplateFeedback({ type: "success", text: "模板克隆成功。" });
      queryClient.invalidateQueries({ queryKey: ["training-templates", selectedWorkspaceId] });
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "模板克隆失败。";
      setTemplateFeedback({ type: "error", text: message });
    }
  });

  const deleteTemplateMutation = useMutation({
    mutationFn: (templateId: number) => trainingApi.deleteTemplate(templateId),
    onSuccess: () => {
      setTemplateFeedback({ type: "success", text: "模板已删除。" });
      setEditingTemplate(null);
      templateForm.reset(DEFAULT_TEMPLATE_VALUES);
      queryClient.invalidateQueries({ queryKey: ["training-templates", selectedWorkspaceId] });
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "模板删除失败。";
      setTemplateFeedback({ type: "error", text: message });
    }
  });

  const createJobMutation = useMutation({
    mutationFn: trainingApi.createJob,
    onSuccess: (job) => {
      setJobFeedback({ type: "success", text: `训练任务已创建：状态 ${job.status}` });
      setLastJob(job);
      jobForm.reset({
        templateId: job.training_template_id ? String(job.training_template_id) : "",
        datasetVersionId: "",
        datasetFormatVersionId: "",
        projectId: "",
        notes: "",
        overrideParams: ""
      });
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "训练任务创建失败。";
      setJobFeedback({ type: "error", text: message });
    }
  });

  useEffect(() => {
    if (workspaceQuery.data && workspaceQuery.data.length > 0 && selectedWorkspaceId == null) {
      setSelectedWorkspaceId(workspaceQuery.data[0].id);
    }
  }, [workspaceQuery.data, selectedWorkspaceId]);

  useEffect(() => {
    if (templatesQuery.data && templatesQuery.data.length > 0) {
      const defaultTemplateId = String(templatesQuery.data[0].id);
      const currentTemplateId = jobForm.getValues("templateId");
      if (!currentTemplateId) {
        jobForm.setValue("templateId", defaultTemplateId);
      }
    }
  }, [templatesQuery.data, jobForm]);

  const workspaceOptions = workspaceQuery.data ?? [];
  const templates = templatesQuery.data ?? [];

  const selectedTemplateForJob = useMemo(() => {
    const templateId = jobForm.watch("templateId");
    return templates.find((item) => String(item.id) === templateId) ?? templates[0] ?? null;
  }, [templates, jobForm.watch("templateId")]);

  function handleEditTemplate(template: TrainingTemplate) {
    setTemplateFeedback(null);
    setEditingTemplate(template);
    const params = template.params ?? {};
    const knownParams: Record<string, unknown> = {};
    const extraParams: Record<string, unknown> = {};
    Object.entries(params).forEach(([key, value]) => {
      if (KNOWN_PARAM_KEYS.has(key)) {
        knownParams[key] = value;
      } else {
        extraParams[key] = value;
      }
    });

    templateForm.reset({
      name: template.name,
      baseModel: template.base_model,
      adapterType: template.adapter_type,
      description: template.description ?? "",
      learningRate: typeof knownParams["learning_rate"] === "number" ? (knownParams["learning_rate"] as number) : 5e-4,
      loraRank: typeof knownParams["lora_rank"] === "number" ? (knownParams["lora_rank"] as number) : 16,
      numEpochs: typeof knownParams["num_epochs"] === "number" ? (knownParams["num_epochs"] as number) : 3,
      batchSize:
        typeof knownParams["per_device_train_batch_size"] === "number"
          ? (knownParams["per_device_train_batch_size"] as number)
          : 4,
      extraParams: Object.keys(extraParams).length > 0 ? JSON.stringify(extraParams, null, 2) : ""
    });
  }

  function handleCancelEdit() {
    setEditingTemplate(null);
    setTemplateFeedback(null);
    templateForm.reset(DEFAULT_TEMPLATE_VALUES);
  }

  const submitting = createTemplateMutation.isPending || updateTemplateMutation.isPending;

  const onSubmitTemplate = (values: TemplateFormValues) => {
    if (selectedWorkspaceId == null) {
      setTemplateFeedback({ type: "error", text: "请先选择工作空间。" });
      return;
    }
    let extraParams: Record<string, unknown> = {};
    try {
      extraParams = parseExtraParams(values.extraParams ?? "");
    } catch (error) {
      setTemplateFeedback({ type: "error", text: (error as Error).message });
      return;
    }
    const params = buildParams(values, extraParams);
    if (editingTemplate) {
      updateTemplateMutation.mutate({
        templateId: editingTemplate.id,
        payload: {
          name: values.name,
          base_model: values.baseModel,
          adapter_type: values.adapterType,
          description: values.description,
          params
        }
      });
      return;
    }
    createTemplateMutation.mutate({
      workspace_id: selectedWorkspaceId,
      name: values.name,
      base_model: values.baseModel,
      adapter_type: values.adapterType,
      description: values.description,
      params
    });
  };

  const onSubmitTrainingJob = (values: TrainingJobFormValues) => {
    if (selectedWorkspaceId == null) {
      setJobFeedback({ type: "error", text: "请先选择工作空间。" });
      return;
    }
    if (!values.templateId) {
      setJobFeedback({ type: "error", text: "请选择模板。" });
      return;
    }
    if (!values.datasetVersionId) {
      setJobFeedback({ type: "error", text: "请输入数据集版本 ID。" });
      return;
    }
    let overrideParams: Record<string, unknown> = {};
    try {
      overrideParams = parseExtraParams(values.overrideParams ?? "");
    } catch (error) {
      setJobFeedback({ type: "error", text: (error as Error).message });
      return;
    }
    const payload = {
      workspace_id: selectedWorkspaceId,
      training_template_id: Number(values.templateId),
      dataset_version_id: Number(values.datasetVersionId),
      dataset_format_version_id: values.datasetFormatVersionId
        ? Number(values.datasetFormatVersionId)
        : undefined,
      project_id: values.projectId ? Number(values.projectId) : undefined,
      params: Object.keys(overrideParams).length > 0 ? overrideParams : undefined,
      notes: values.notes ?? undefined
    };
    createJobMutation.mutate(payload);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/60">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="text-xl font-semibold text-purple-300">训练方案模板库</h1>
            <p className="text-sm text-slate-400">
              选择并配置 LoRA/QLoRA/DoRA 等模板，保存常用参数以加速训练启动。
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-8 px-6 py-10">
        <TrainingNav />

        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
          <label className="text-xs font-semibold text-slate-400" htmlFor="workspace-select">
            工作空间
          </label>
          <select
            id="workspace-select"
            className="mt-2 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-purple-500 focus:outline-none"
            value={selectedWorkspaceId ?? ""}
            onChange={(event) => {
              const workspaceId = Number(event.target.value);
              setSelectedWorkspaceId(Number.isNaN(workspaceId) ? null : workspaceId);
              setEditingTemplate(null);
              templateForm.reset(DEFAULT_TEMPLATE_VALUES);
              setTemplateFeedback(null);
              setJobFeedback(null);
              setLastJob(null);
            }}
          >
            {workspaceOptions.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.name}
              </option>
            ))}
          </select>
          {workspaceOptions.length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">暂无工作空间，请先创建或加入一个工作空间。</p>
          ) : null}
        </section>

        <section className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-100">{editingTemplate ? "编辑模板" : "创建模板"}</h2>
              <p className="text-sm text-slate-400">
                填写模板基础信息与关键参数，额外参数可使用 JSON 格式补充。
              </p>
            </div>
            {editingTemplate ? (
              <button
                type="button"
                className="rounded-md border border-slate-700 px-3 py-1 text-xs text-slate-200 hover:border-slate-500"
                onClick={handleCancelEdit}
              >
                取消编辑
              </button>
            ) : null}
          </div>

          {templateFeedback ? (
            <p
              className={`rounded-md px-3 py-2 text-sm ${
                templateFeedback.type === "success"
                  ? "bg-emerald-500/10 text-emerald-300"
                  : "bg-rose-500/10 text-rose-300"
              }`}
            >
              {templateFeedback.text}
            </p>
          ) : null}

          <form className="grid gap-4 md:grid-cols-2" onSubmit={templateForm.handleSubmit(onSubmitTemplate)}>
            <label className="flex flex-col text-sm text-slate-300">
              模板名称
              <input
                className="mt-1 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                placeholder="例如：客服场景 LoRA"
                {...templateForm.register("name", { required: true })}
              />
            </label>
            <label className="flex flex-col text-sm text-slate-300">
              基座模型
              <input
                className="mt-1 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                placeholder="meta-llama/Llama-3-8b-instruct"
                {...templateForm.register("baseModel", { required: true })}
              />
            </label>
            <label className="flex flex-col text-sm text-slate-300">
              Adapter 类型
              <select
                className="mt-1 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                {...templateForm.register("adapterType")}
              >
                {Object.entries(ADAPTER_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col text-sm text-slate-300 md:col-span-2">
              描述（可选）
              <textarea
                className="mt-1 h-20 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                placeholder="说明适用场景与参数特点"
                {...templateForm.register("description")}
              />
            </label>

            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 text-xs text-slate-300 md:col-span-2">
              <h3 className="text-sm font-semibold text-slate-100">关键参数</h3>
              <div className="mt-3 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                <label className="flex flex-col gap-1">
                  <span>Learning Rate</span>
                  <input
                    type="number"
                    step="0.00001"
                    className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                    {...templateForm.register("learningRate", { valueAsNumber: true })}
                  />
                  <span className="text-[11px] text-slate-500">建议范围 1e-5 ~ 5e-4</span>
                </label>
                <label className="flex flex-col gap-1">
                  <span>LoRA Rank</span>
                  <input
                    type="number"
                    className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                    {...templateForm.register("loraRank", { valueAsNumber: true })}
                  />
                  <span className="text-[11px] text-slate-500">常用 8/16/32</span>
                </label>
                <label className="flex flex-col gap-1">
                  <span>训练 Epoch</span>
                  <input
                    type="number"
                    className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                    {...templateForm.register("numEpochs", { valueAsNumber: true })}
                  />
                  <span className="text-[11px] text-slate-500">建议 1~5</span>
                </label>
                <label className="flex flex-col gap-1">
                  <span>每卡 Batch Size</span>
                  <input
                    type="number"
                    className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                    {...templateForm.register("batchSize", { valueAsNumber: true })}
                  />
                  <span className="text-[11px] text-slate-500">根据显存设置 1~8</span>
                </label>
              </div>
            </div>

            <label className="md:col-span-2 flex flex-col text-sm text-slate-300">
              额外参数（JSON，可选）
              <textarea
                className="mt-1 h-32 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100 focus:border-purple-500 focus:outline-none"
                placeholder='{"gradient_accumulation_steps": 8}'
                {...templateForm.register("extraParams")}
              />
            </label>

            <div className="flex items-center gap-3 md:col-span-2">
              <button
                type="submit"
                className="rounded-md bg-purple-500 px-4 py-2 text-sm font-medium text-slate-100 hover:bg-purple-400 disabled:cursor-not-allowed disabled:bg-slate-700"
                disabled={submitting}
              >
                {submitting ? "提交中..." : editingTemplate ? "保存模板" : "创建模板"}
              </button>
              <button
                type="button"
                className="rounded-md border border-slate-700 px-4 py-2 text-sm text-slate-200 hover:border-slate-500"
                onClick={() => templateForm.reset(DEFAULT_TEMPLATE_VALUES)}
              >
                重置表单
              </button>
            </div>
          </form>
        </section>

        <section className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-100">模板列表</h2>
              <p className="text-sm text-slate-400">查看已存在的模板，快速克隆或进入编辑。</p>
            </div>
            {templatesQuery.isFetching ? <span className="text-xs text-slate-500">刷新中…</span> : null}
          </div>

          {templatesQuery.isLoading ? (
            <p className="text-sm text-slate-400">正在加载模板...</p>
          ) : templates.length === 0 ? (
            <p className="text-sm text-slate-400">暂无模板，请先创建或等待系统生成默认模板。</p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {templates.map((template) => (
                <div
                  key={template.id}
                  className="space-y-3 rounded-lg border border-slate-800 bg-slate-900/50 p-4 text-sm text-slate-200"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-base font-semibold text-slate-100">{template.name}</h3>
                      <p className="text-xs text-slate-400">{template.description ?? "暂无描述"}</p>
                    </div>
                    <span className="rounded-full bg-purple-500/20 px-3 py-1 text-xs text-purple-200">
                      {ADAPTER_LABELS[template.adapter_type]}
                    </span>
                  </div>
                  <dl className="grid gap-2 text-xs text-slate-400 md:grid-cols-2">
                    <div>
                      <dt>基座模型</dt>
                      <dd className="font-mono text-[11px] text-slate-200">{template.base_model}</dd>
                    </div>
                    <div>
                      <dt>最后更新</dt>
                      <dd>{new Date(template.updated_at).toLocaleString()}</dd>
                    </div>
                    <div className="md:col-span-2">
                      <dt>参数预览</dt>
                      <dd className="mt-1 space-y-1 font-mono text-[11px] text-slate-200">
                        {Object.entries(template.params ?? {}).map(([key, value]) => (
                          <div key={key}>
                            {key}: {JSON.stringify(value)}
                          </div>
                        ))}
                      </dd>
                    </div>
                  </dl>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="rounded-md border border-slate-700 px-3 py-1 text-xs text-slate-200 hover:border-slate-500"
                      onClick={() => handleEditTemplate(template)}
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      className="rounded-md border border-purple-500/50 px-3 py-1 text-xs text-purple-200 hover:border-purple-400/80"
                      onClick={() =>
                        cloneTemplateMutation.mutate({ templateId: template.id, name: `${template.name} 副本` })
                      }
                    >
                      克隆
                    </button>
                    {template.is_builtin ? (
                      <span className="rounded-md border border-slate-700 px-3 py-1 text-xs text-slate-500">
                        系统模板
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="rounded-md border border-rose-500/60 px-3 py-1 text-xs text-rose-200 hover:border-rose-400/80"
                        onClick={() => {
                          if (window.confirm(`确认删除模板「${template.name}」？该操作不可撤销。`)) {
                            deleteTemplateMutation.mutate(template.id);
                          }
                        }}
                        disabled={deleteTemplateMutation.isPending}
                      >
                        删除
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-100">基于模板发起训练任务</h2>
              <p className="text-sm text-slate-400">
                选择模板并填写数据集版本 ID（可在 Data Hub 中查看），可选地覆盖部分参数。
              </p>
            </div>
          </div>

          {jobFeedback ? (
            <p
              className={`rounded-md px-3 py-2 text-sm ${
                jobFeedback.type === "success" ? "bg-emerald-500/10 text-emerald-300" : "bg-rose-500/10 text-rose-300"
              }`}
            >
              {jobFeedback.text}
            </p>
          ) : null}

          <form className="grid gap-4 md:grid-cols-2" onSubmit={jobForm.handleSubmit(onSubmitTrainingJob)}>
            <label className="flex flex-col text-sm text-slate-300">
              训练模板
              <select
                className="mt-1 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                {...jobForm.register("templateId")}
              >
                {templates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col text-sm text-slate-300">
              数据集版本 ID
              <input
                className="mt-1 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                placeholder="例如：42"
                {...jobForm.register("datasetVersionId")}
              />
            </label>
            <label className="flex flex-col text-sm text-slate-300">
              标准化格式 ID（可选）
              <input
                className="mt-1 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                placeholder="默认使用激活的格式"
                {...jobForm.register("datasetFormatVersionId")}
              />
            </label>
            <label className="flex flex-col text-sm text-slate-300">
              项目 ID（可选）
              <input
                className="mt-1 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                placeholder="关联到项目时填写"
                {...jobForm.register("projectId")}
              />
            </label>
            <label className="md:col-span-2 flex flex-col text-sm text-slate-300">
              备注（可选）
              <textarea
                className="mt-1 h-16 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                placeholder="例如：使用清洗版本 v3，重点关注客服场景"
                {...jobForm.register("notes")}
              />
            </label>
            <label className="md:col-span-2 flex flex-col text-sm text-slate-300">
              覆盖参数（JSON，可选）
              <textarea
                className="mt-1 h-24 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100 focus:border-purple-500 focus:outline-none"
                placeholder='{"num_epochs": 1}'
                {...jobForm.register("overrideParams")}
              />
            </label>
            <button
              type="submit"
              className="md:col-span-2 inline-flex items-center justify-center rounded-md bg-emerald-500 px-4 py-2 text-sm font-semibold text-emerald-950 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
              disabled={createJobMutation.isPending}
            >
              {createJobMutation.isPending ? "提交中..." : "创建训练任务"}
            </button>
          </form>

          {selectedTemplateForJob ? (
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4 text-xs text-slate-300">
              <h3 className="text-sm font-semibold text-slate-100">模板参数预览</h3>
              <p className="mt-1 text-slate-400">基座模型：{selectedTemplateForJob.base_model}</p>
              <pre className="mt-2 whitespace-pre-wrap font-mono text-[11px] text-slate-200">
                {JSON.stringify(selectedTemplateForJob.params ?? {}, null, 2)}
              </pre>
            </div>
          ) : null}

          {lastJob ? (
            <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4 text-xs text-slate-300">
              <h3 className="text-sm font-semibold text-slate-100">最近训练任务</h3>
              <p>任务 ID：{lastJob.id}</p>
              <p>状态：{lastJob.status}</p>
              {lastJob.latest_run ? (
                <div className="mt-2 space-y-1">
                  <p>最新运行：{new Date(lastJob.latest_run.started_at).toLocaleString()}</p>
                  <p>最终指标：{JSON.stringify(lastJob.latest_run.metrics ?? {}, null, 2)}</p>
                </div>
              ) : null}
            </div>
          ) : null}
        </section>
      </main>
    </div>
  );
}
