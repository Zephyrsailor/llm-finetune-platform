import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  dataHubApi,
  Dataset,
  DatasetFormatVersion,
  DatasetVersion,
  formatApi,
  TrainingAdapterType,
  TrainingJob,
  TrainingTemplate,
  TrainingWizardDraft,
  TrainingWizardValidation,
  TrainingWizardValidatePayload,
  TrainingFeedbackSummary,
  TrainingFeedbackSummaryItem,
  trainingApi,
  workspaceApi,
  WorkspaceDetail
} from "../../lib/api";
import { TrainingNav } from "./TrainingNav";
import { AppShell } from "../layout/AppShell";

type WizardState = {
  templateId: string;
  datasetVersionId: string;
  datasetFormatVersionId: string;
  projectId: string;
  baseModel: string;
  adapterType: TrainingAdapterType;
  params: string;
  notes: string;
  requestedGpus: string;
  queueName: string;
};

const DEFAULT_STATE: WizardState = {
  templateId: "",
  datasetVersionId: "",
  datasetFormatVersionId: "",
  projectId: "",
  baseModel: "",
  adapterType: "lora",
  params: "{}",
  notes: "",
  requestedGpus: "1",
  queueName: "default"
};

type Feedback = { type: "success" | "error"; text: string } | null;

const STEP_LABELS = ["选择模板", "绑定数据", "资源与参数", "预览并提交"];
const QUEUE_OPTIONS = ["default", "high-memory", "spot"];
const FORMAT_STATUS_LABEL: Record<DatasetFormatVersion["status"], string> = {
  pending: "待处理",
  running: "处理中",
  completed: "已完成",
  failed: "失败"
};
const VERSION_STATUS_LABEL: Record<DatasetVersion["status"], string> = {
  pending: "待处理",
  processing: "处理中",
  completed: "已完成",
  failed: "失败"
};

function parseParamsText(text: string): Record<string, unknown> {
  if (!text.trim()) {
    return {};
  }
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch (error) {
    throw new Error("参数需为 JSON 对象格式。");
  }
  throw new Error("参数需为 JSON 对象格式。");
}

function draftToState(draft: TrainingWizardDraft | null): WizardState {
  if (!draft?.payload) {
    return DEFAULT_STATE;
  }
  return {
    templateId: String(draft.payload.templateId ?? ""),
    datasetVersionId: String(draft.payload.datasetVersionId ?? ""),
    datasetFormatVersionId: String(draft.payload.datasetFormatVersionId ?? ""),
    projectId: String(draft.payload.projectId ?? ""),
    baseModel: String(draft.payload.baseModel ?? ""),
    adapterType: (draft.payload.adapterType as TrainingAdapterType) ?? "lora",
    params: draft.payload.params ? JSON.stringify(draft.payload.params, null, 2) : "{}",
    notes: String(draft.payload.notes ?? ""),
    requestedGpus: String(draft.payload.requestedGpus ?? "1"),
    queueName: String(draft.payload.queueName ?? "default")
  };
}

export function TrainingWizardPage() {
  const queryClient = useQueryClient();
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [selectedDatasetId, setSelectedDatasetId] = useState<number | null>(null);
  const [state, setState] = useState<WizardState>(DEFAULT_STATE);
  const [currentStep, setCurrentStep] = useState(0);
  const [historyJobId, setHistoryJobId] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [validationResult, setValidationResult] = useState<TrainingWizardValidation | null>(null);
  const [lastJob, setLastJob] = useState<TrainingJob | null>(null);

  const workspaceQuery = useQuery<WorkspaceDetail[]>({
    queryKey: ["workspaces"],
    queryFn: () => workspaceApi.list(),
    refetchOnWindowFocus: false
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

  const templatesQuery = useQuery<TrainingTemplate[]>({
    queryKey: ["training-templates", selectedWorkspaceId],
    enabled: selectedWorkspaceId != null,
    queryFn: () => trainingApi.listTemplates(selectedWorkspaceId ?? 0),
    staleTime: 30_000
  });

  const draftQuery = useQuery<TrainingWizardDraft>({
    queryKey: ["training-wizard-draft", selectedWorkspaceId],
    enabled: selectedWorkspaceId != null,
    queryFn: () => trainingApi.getWizardDraft(selectedWorkspaceId ?? 0),
    staleTime: 30_000
  });

  const feedbackSummaryQuery = useQuery<TrainingFeedbackSummary>({
    queryKey: ["training-feedback-summaries", selectedWorkspaceId, state.projectId],
    enabled: selectedWorkspaceId != null,
    queryFn: () =>
      trainingApi.listFeedbackSummaries(selectedWorkspaceId ?? 0, {
        projectId: state.projectId ? Number(state.projectId) : null,
        limit: 10
      }),
    staleTime: 30_000
  });

  const numericDatasetVersionId = state.datasetVersionId ? Number(state.datasetVersionId) : null;
  const formatVersionsQuery = useQuery<DatasetFormatVersion[]>({
    queryKey: ["dataset-format-versions", selectedDatasetId, state.datasetVersionId],
    enabled:
      selectedDatasetId != null &&
      numericDatasetVersionId != null &&
      !Number.isNaN(numericDatasetVersionId) &&
      numericDatasetVersionId > 0,
    queryFn: () => formatApi.listFormats(selectedDatasetId ?? 0, numericDatasetVersionId ?? 0),
    refetchInterval: (records) =>
      Array.isArray(records) && records.some((item) => item.status === "pending" || item.status === "running")
        ? 4000
        : false
  });

  const templates = templatesQuery.data ?? [];
  const selectedTemplate = useMemo(
    () => templates.find((item) => String(item.id) === state.templateId),
    [templates, state.templateId]
  );
  const feedbackItems = feedbackSummaryQuery.data?.items ?? [];
  const datasetOptions = datasetsQuery.data ?? [];
  const versionOptions = useMemo(() => {
    const versions = versionsQuery.data ?? [];
    return [...versions].sort((a, b) => b.version - a.version);
  }, [versionsQuery.data]);
  const formatOptions = useMemo(
    () => (formatVersionsQuery.data ?? []).slice(),
    [formatVersionsQuery.data]
  );
  const isDatasetVersionReady =
    numericDatasetVersionId != null && !Number.isNaN(numericDatasetVersionId) && numericDatasetVersionId > 0;
  const selectedDataset = useMemo(
    () => datasetOptions.find((item) => item.id === selectedDatasetId) ?? null,
    [datasetOptions, selectedDatasetId]
  );
  const selectedDatasetVersion = useMemo(
    () => versionOptions.find((item) => String(item.id) === state.datasetVersionId) ?? null,
    [versionOptions, state.datasetVersionId]
  );
  const selectedFormatVersion = useMemo(
    () => formatOptions.find((item) => String(item.id) === state.datasetFormatVersionId) ?? null,
    [formatOptions, state.datasetFormatVersionId]
  );

  useEffect(() => {
    if (workspaceQuery.data && workspaceQuery.data.length > 0 && selectedWorkspaceId == null) {
      setSelectedWorkspaceId(workspaceQuery.data[0].id);
    }
  }, [workspaceQuery.data, selectedWorkspaceId]);

  useEffect(() => {
    if (draftQuery.data && selectedWorkspaceId != null) {
      setState(draftToState(draftQuery.data));
      if (draftQuery.data.payload?.currentStep != null) {
        setCurrentStep(draftQuery.data.payload.currentStep as number);
      }
      setValidationResult(null);
    }
  }, [draftQuery.data, selectedWorkspaceId]);

  useEffect(() => {
    if (!datasetOptions.length) {
      setSelectedDatasetId(null);
      setState((prev) => {
        if (!prev.datasetVersionId && !prev.datasetFormatVersionId) {
          return prev;
        }
        return { ...prev, datasetVersionId: "", datasetFormatVersionId: "" };
      });
      return;
    }
    if (selectedDatasetId == null) {
      if (!state.datasetVersionId) {
        setSelectedDatasetId(datasetOptions[0].id);
      }
      return;
    }
    if (!datasetOptions.some((item) => item.id === selectedDatasetId)) {
      setSelectedDatasetId(datasetOptions[0].id);
    }
  }, [datasetOptions, selectedDatasetId, state.datasetVersionId]);

  useEffect(() => {
    if (!state.datasetVersionId || !datasetOptions.length) {
      return;
    }
    const initialVersionId = state.datasetVersionId;
    const targetVersionId = Number(state.datasetVersionId);
    if (Number.isNaN(targetVersionId)) {
      return;
    }
    if (versionOptions.some((item) => item.id === targetVersionId)) {
      return;
    }
    let isActive = true;
    (async () => {
      let matchedDatasetId: number | null = null;
      for (const dataset of datasetOptions) {
        const versions =
          dataset.id === selectedDatasetId
            ? versionOptions
            : await queryClient.ensureQueryData<DatasetVersion[]>({
                queryKey: ["dataset-versions", dataset.id],
                queryFn: () => dataHubApi.listVersions(dataset.id)
              });
        if (!isActive) {
          return;
        }
        if (versions.some((version) => version.id === targetVersionId)) {
          matchedDatasetId = dataset.id;
          setSelectedDatasetId(dataset.id);
          return;
        }
      }
      if (isActive && matchedDatasetId == null) {
        let changed = false;
        setState((prev) => {
          if (prev.datasetVersionId !== initialVersionId) {
            return prev;
          }
          if (!prev.datasetVersionId && !prev.datasetFormatVersionId) {
            return prev;
          }
          changed = true;
          return {
            ...prev,
            datasetVersionId: "",
            datasetFormatVersionId: ""
          };
        });
        if (changed) {
          resetValidationState();
        }
      }
    })();
    return () => {
      isActive = false;
    };
  }, [datasetOptions, state.datasetVersionId, selectedDatasetId, versionOptions, queryClient]);

  useEffect(() => {
    if (!versionOptions.length) {
      setState((prev) => {
        if (!prev.datasetVersionId && !prev.datasetFormatVersionId) {
          return prev;
        }
        return { ...prev, datasetVersionId: "", datasetFormatVersionId: "" };
      });
      return;
    }
    if (!state.datasetVersionId) {
      const latestVersion = versionOptions[0];
      if (latestVersion) {
        setState((prev) => ({
          ...prev,
          datasetVersionId: String(latestVersion.id),
          datasetFormatVersionId: ""
        }));
      }
    } else if (!versionOptions.some((item) => String(item.id) === state.datasetVersionId)) {
      const latestVersion = versionOptions[0];
      if (latestVersion) {
        setState((prev) => ({
          ...prev,
          datasetVersionId: String(latestVersion.id),
          datasetFormatVersionId: ""
        }));
      }
    }
  }, [versionOptions, state.datasetVersionId]);

  useEffect(() => {
    if (!isDatasetVersionReady) {
      if (state.datasetFormatVersionId) {
        setState((prev) => ({ ...prev, datasetFormatVersionId: "" }));
      }
      return;
    }
    if (!formatOptions.length) {
      if (state.datasetFormatVersionId) {
        setState((prev) => ({ ...prev, datasetFormatVersionId: "" }));
      }
      return;
    }
    if (state.datasetFormatVersionId) {
      const exists = formatOptions.some((item) => String(item.id) === state.datasetFormatVersionId);
      if (exists) {
        return;
      }
    }
    const activeFormat = formatOptions.find(
      (item) => item.is_active && item.status === "completed"
    );
    const completedFormat = activeFormat ?? formatOptions.find((item) => item.status === "completed");
    if (completedFormat) {
      setState((prev) => ({
        ...prev,
        datasetFormatVersionId: String(completedFormat.id)
      }));
    } else if (state.datasetFormatVersionId) {
      setState((prev) => ({ ...prev, datasetFormatVersionId: "" }));
    }
  }, [formatOptions, isDatasetVersionReady, state.datasetFormatVersionId]);

  useEffect(() => {
    if (!selectedTemplate) {
      return;
    }
    setState((prev) => ({
      ...prev,
      baseModel: selectedTemplate.base_model,
      adapterType: selectedTemplate.adapter_type,
      params: JSON.stringify(selectedTemplate.params ?? {}, null, 2)
    }));
  }, [selectedTemplate?.id]);

  const saveDraftMutation = useMutation({
    mutationFn: trainingApi.saveWizardDraft,
    onSuccess: (draft) => {
      setFeedback({ type: "success", text: "草稿已保存。" });
      queryClient.setQueryData(["training-wizard-draft", selectedWorkspaceId], draft);
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "草稿保存失败。";
      setFeedback({ type: "error", text: message });
    }
  });

  const validateMutation = useMutation({
    mutationFn: (payload: TrainingWizardValidatePayload) => trainingApi.validateWizard(payload),
    onSuccess: (result) => {
      setValidationResult(result);
      setFeedback({ type: "success", text: "配置校验通过。" });
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "配置校验失败。";
      setFeedback({ type: "error", text: message });
    }
  });

  const loadJobMutation = useMutation({
    mutationFn: (jobId: number) => trainingApi.getJob(jobId),
    onSuccess: (job) => {
      setState({
        templateId: job.training_template_id ? String(job.training_template_id) : "",
        datasetVersionId: String(job.dataset_version_id),
        datasetFormatVersionId: job.dataset_format_version_id ? String(job.dataset_format_version_id) : "",
        projectId: job.project_id ? String(job.project_id) : "",
        baseModel: job.base_model,
        adapterType: job.adapter_type,
        params: JSON.stringify(job.params ?? {}, null, 2),
        notes: job.notes ?? "",
        requestedGpus: job.requested_gpus ? String(job.requested_gpus) : "1",
        queueName: job.queue_name ?? "default"
      });
      setValidationResult(null);
      setFeedback({ type: "success", text: "已从历史任务复制配置。" });
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "加载历史任务失败。";
      setFeedback({ type: "error", text: message });
    }
  });

  const createJobMutation = useMutation({
    mutationFn: trainingApi.createJob,
    onSuccess: (job) => {
      setLastJob(job);
      setFeedback({ type: "success", text: "训练任务已创建，可在实时监控中查看进度。" });
      setValidationResult(null);
      setHistoryJobId("");
      queryClient.invalidateQueries({ queryKey: ["training-monitor", "runs"] });
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "训练任务创建失败。";
      setFeedback({ type: "error", text: message });
    }
  });

  const workspaceOptions = workspaceQuery.data ?? [];
  const resetValidationState = () => {
    setFeedback(null);
    setValidationResult(null);
  };

  const handleTemplateSelect = (templateId: string) => {
    setState((prev) => ({
      ...prev,
      templateId,
      baseModel: "",
      adapterType: "lora",
      params: "{}"
    }));
    resetValidationState();
  };

  const handleFieldChange = (field: keyof WizardState, value: string) => {
    setState((prev) => ({
      ...prev,
      [field]: value
    }));
    resetValidationState();
  };

  const handleDatasetVersionSelect = (value: string) => {
    setState((prev) => ({
      ...prev,
      datasetVersionId: value,
      datasetFormatVersionId: ""
    }));
    resetValidationState();
  };

  const handleSaveDraft = () => {
    if (selectedWorkspaceId == null) {
      setFeedback({ type: "error", text: "请先选择工作空间。" });
      return;
    }
    saveDraftMutation.mutate({
      workspace_id: selectedWorkspaceId,
      payload: {
        templateId: state.templateId,
        datasetVersionId: state.datasetVersionId,
        datasetFormatVersionId: state.datasetFormatVersionId,
        projectId: state.projectId,
        baseModel: state.baseModel,
        adapterType: state.adapterType,
        params: (() => {
          try {
            return parseParamsText(state.params);
          } catch {
            return {};
          }
        })(),
        notes: state.notes,
        requestedGpus: (() => {
          const parsed = Number.parseInt(state.requestedGpus, 10);
          return Number.isNaN(parsed) || parsed <= 0 ? 1 : parsed;
        })(),
        queueName: state.queueName.trim() || "default",
        currentStep
      }
    });
  };

  const handleValidate = () => {
    if (selectedWorkspaceId == null) {
      setFeedback({ type: "error", text: "请先选择工作空间。" });
      return;
    }
    if (selectedDatasetId == null) {
      setFeedback({ type: "error", text: "请先选择数据集。" });
      return;
    }
    if (!state.datasetVersionId) {
      setFeedback({ type: "error", text: "请选择数据集版本。" });
      return;
    }
    const requestedGpus = Number.parseInt(state.requestedGpus, 10);
    if (Number.isNaN(requestedGpus) || requestedGpus <= 0) {
      setFeedback({ type: "error", text: "GPU 数量需为正整数。" });
      return;
    }
    const queueName = state.queueName.trim();
    if (!queueName) {
      setFeedback({ type: "error", text: "请选择训练队列。" });
      return;
    }
    let paramsObject: Record<string, unknown>;
    try {
      paramsObject = parseParamsText(state.params);
    } catch (error) {
      setFeedback({ type: "error", text: (error as Error).message });
      return;
    }
    validateMutation.mutate({
      workspace_id: selectedWorkspaceId,
      project_id: state.projectId ? Number(state.projectId) : undefined,
      dataset_version_id: Number(state.datasetVersionId),
      dataset_format_version_id: state.datasetFormatVersionId ? Number(state.datasetFormatVersionId) : undefined,
      training_template_id: state.templateId ? Number(state.templateId) : undefined,
      base_model: state.baseModel,
      adapter_type: state.adapterType,
      params: paramsObject,
      requested_gpus: requestedGpus,
      queue_name: queueName
    });
  };

  const handleSubmit = () => {
    if (selectedWorkspaceId == null) {
      setFeedback({ type: "error", text: "请先选择工作空间。" });
      return;
    }
    if (selectedDatasetId == null) {
      setFeedback({ type: "error", text: "请先选择数据集。" });
      return;
    }
    if (!state.datasetVersionId) {
      setFeedback({ type: "error", text: "请选择数据集版本。" });
      return;
    }
    if (!state.templateId) {
      setFeedback({ type: "error", text: "请先选择模板。" });
      return;
    }
    if (!state.baseModel.trim()) {
      setFeedback({ type: "error", text: "请填写基座模型。" });
      return;
    }
    const requestedGpus = Number.parseInt(state.requestedGpus, 10);
    if (Number.isNaN(requestedGpus) || requestedGpus <= 0) {
      setFeedback({ type: "error", text: "GPU 数量需为正整数。" });
      return;
    }
    const queueName = state.queueName.trim();
    if (!queueName) {
      setFeedback({ type: "error", text: "请选择训练队列。" });
      return;
    }
    let paramsObject: Record<string, unknown>;
    try {
      paramsObject = parseParamsText(state.params);
    } catch (error) {
      setFeedback({ type: "error", text: (error as Error).message });
      return;
    }
    createJobMutation.mutate({
      workspace_id: selectedWorkspaceId,
      training_template_id: Number(state.templateId),
      dataset_version_id: Number(state.datasetVersionId),
      dataset_format_version_id: state.datasetFormatVersionId ? Number(state.datasetFormatVersionId) : undefined,
      project_id: state.projectId ? Number(state.projectId) : undefined,
      base_model: state.baseModel,
      adapter_type: state.adapterType,
      params: paramsObject,
      notes: state.notes || undefined,
      requested_gpus: requestedGpus,
      queue_name: queueName
    });
  };

  const canProceedToNext = () => {
    if (currentStep === 0) {
      return Boolean(state.templateId);
    }
    if (currentStep === 1) {
      return selectedDatasetId != null && Boolean(state.datasetVersionId);
    }
    if (currentStep === 2) {
      const requestedGpus = Number.parseInt(state.requestedGpus, 10);
      return (
        Boolean(state.baseModel.trim()) && !Number.isNaN(requestedGpus) && requestedGpus > 0 && Boolean(state.queueName.trim())
      );
    }
    return true;
  };

  const goToNext = () => {
    if (!canProceedToNext()) {
      setFeedback({ type: "error", text: "请先填写必填信息。" });
      return;
    }
    setFeedback(null);
    setCurrentStep((prev) => Math.min(prev + 1, STEP_LABELS.length - 1));
  };

  const goToPrevious = () => {
    setFeedback(null);
    setCurrentStep((prev) => Math.max(prev - 1, 0));
  };

  const handleLoadHistory = () => {
    if (!historyJobId.trim()) {
      setFeedback({ type: "error", text: "请输入历史任务 ID。" });
      return;
    }
    const jobId = Number(historyJobId);
    if (Number.isNaN(jobId)) {
      setFeedback({ type: "error", text: "任务 ID 必须为数字。" });
      return;
    }
    loadJobMutation.mutate(jobId);
  };

  const handleApplyFeedback = (item: TrainingFeedbackSummaryItem) => {
    const noteLine = `TODO: ${item.body}`;
    setState((prev) => {
      if (prev.notes.includes(noteLine)) {
        return prev;
      }
      const nextNotes = prev.notes ? `${prev.notes}\n${noteLine}` : noteLine;
      return { ...prev, notes: nextNotes };
    });
    setFeedback({ type: "success", text: "已将反馈添加至备注，可在提交前完善细节。" });
  };

  const toolbar = (
    <div className="mx-auto w-full max-w-7xl px-8 py-3">
      <TrainingNav />
    </div>
  );

  return (
    <AppShell
      title="向导式训练编排"
      subtitle="通过模板、数据与资源配置向导，快速发起训练任务并保持参数一致性。"
      searchPlaceholder="搜索模板、项目或历史任务"
      primaryAction={{ label: "查看训练监控", to: "/training/monitor" }}
      toolbar={toolbar}
    >
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor="workspace-select">
          工作空间
        </label>
        <select
          id="workspace-select"
          className="mt-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
          value={selectedWorkspaceId ?? ""}
          onChange={(event) => {
            const workspaceId = Number(event.target.value);
            setSelectedWorkspaceId(Number.isNaN(workspaceId) ? null : workspaceId);
            setSelectedDatasetId(null);
            setState(DEFAULT_STATE);
            setCurrentStep(0);
            setFeedback(null);
            setValidationResult(null);
            setLastJob(null);
            setHistoryJobId("");
          }}
        >
          {workspaceOptions.map((workspace) => (
            <option key={workspace.id} value={workspace.id}>
              {workspace.name}
            </option>
          ))}
        </select>
        {workspaceOptions.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">暂无工作空间，请先创建或加入一个工作空间。</p>
        ) : null}
      </section>

      {feedback ? (
        <div
          className={`rounded-lg border px-4 py-3 text-sm ${
            feedback.type === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-rose-200 bg-rose-50 text-rose-700"
          }`}
        >
          {feedback.text}
        </div>
      ) : null}

      <section className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <ol className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
          {STEP_LABELS.map((label, index) => (
            <li
              key={label}
              className={`flex items-center gap-2 rounded-full px-3 py-1 ${
                index === currentStep ? "bg-purple-100 text-purple-600" : "bg-slate-100 text-slate-500"
              }`}
            >
              <span className="font-semibold">{index + 1}</span>
              <span>{label}</span>
            </li>
          ))}
        </ol>

        {currentStep === 0 ? (
          <div className="space-y-5">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <h2 className="text-lg font-semibold text-slate-900">选择模板</h2>
              <div className="flex items-center gap-2">
                <input
                  value={historyJobId}
                  onChange={(event) => setHistoryJobId(event.target.value)}
                  placeholder="输入历史任务 ID"
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
                />
                <button
                  type="button"
                  onClick={handleLoadHistory}
                  className="rounded-md border border-purple-300 bg-purple-50 px-3 py-2 text-xs font-medium text-purple-700 transition hover:border-purple-400"
                >
                  从历史任务复制
                </button>
              </div>
            </div>
            {templatesQuery.isLoading ? (
              <p className="text-sm text-slate-500">正在加载模板...</p>
            ) : templates.length === 0 ? (
              <p className="text-sm text-slate-500">暂无模板，请先在模板库中创建或等待系统生成。</p>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {templates.map((template) => (
                  <label
                    key={template.id}
                    className={`flex cursor-pointer flex-col gap-3 rounded-xl border px-4 py-4 transition ${
                      String(template.id) === state.templateId
                        ? "border-purple-400 bg-purple-50"
                        : "border-slate-200 bg-slate-50 hover:border-slate-300"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-slate-900">{template.name}</span>
                      <input
                        type="radio"
                        name="template"
                        value={template.id}
                        checked={String(template.id) === state.templateId}
                        onChange={(event) => handleTemplateSelect(event.target.value)}
                        className="h-4 w-4 border-purple-500 text-purple-500 focus:ring-purple-500"
                      />
                    </div>
                    <p className="text-xs text-slate-500">{template.description ?? "暂无描述"}</p>
                    <dl className="text-[11px] text-slate-500">
                      <div>
                        <dt className="inline text-slate-500">基座模型：</dt>
                        <dd className="inline font-mono text-slate-700">{template.base_model}</dd>
                      </div>
                      <div>
                        <dt className="inline text-slate-500">Adapter：</dt>
                        <dd className="inline text-slate-700">{template.adapter_type.toUpperCase()}</dd>
                      </div>
                    </dl>
                  </label>
                ))}
              </div>
            )}
          </div>
        ) : currentStep === 1 ? (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-slate-900">绑定数据版本</h2>
            <p className="text-xs text-slate-500">确认所选数据集已完成质量评估与格式标准化。</p>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="flex flex-col text-sm text-slate-600">
                数据集
                <select
                  className="mt-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
                  value={selectedDatasetId != null ? String(selectedDatasetId) : ""}
                  onChange={(event) => {
                    const datasetIdValue = Number(event.target.value);
                    const nextDatasetId = Number.isNaN(datasetIdValue) ? null : datasetIdValue;
                    if (nextDatasetId === selectedDatasetId) {
                      return;
                    }
                    setSelectedDatasetId(nextDatasetId);
                    setState((prev) => ({
                      ...prev,
                      datasetVersionId: "",
                      datasetFormatVersionId: ""
                    }));
                    resetValidationState();
                  }}
                >
                  <option value="">请选择数据集</option>
                  {datasetOptions.map((dataset) => (
                    <option key={dataset.id} value={String(dataset.id)}>
                      {dataset.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col text-sm text-slate-600">
                数据集版本
                <select
                  className="mt-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
                  value={state.datasetVersionId}
                  onChange={(event) => handleDatasetVersionSelect(event.target.value)}
                  disabled={selectedDatasetId == null || versionOptions.length === 0}
                >
                  <option value="">请选择版本</option>
                  {versionOptions.map((version) => (
                    <option key={version.id} value={String(version.id)}>
                      v{version.version} · {VERSION_STATUS_LABEL[version.status]}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col text-sm text-slate-600">
                标准化格式（可选）
                <select
                  className="mt-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
                  value={state.datasetFormatVersionId}
                  onChange={(event) => handleFieldChange("datasetFormatVersionId", event.target.value)}
                  disabled={!isDatasetVersionReady || formatOptions.length === 0}
                >
                  <option value="">使用激活格式</option>
                  {formatOptions.map((format) => (
                    <option
                      key={format.id}
                      value={String(format.id)}
                      disabled={format.status !== "completed"}
                    >
                      {`${format.format.toUpperCase()} · ${FORMAT_STATUS_LABEL[format.status]}${
                        format.is_active ? "（当前启用）" : ""
                      }`}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col text-sm text-slate-600">
                关联项目 ID（可选）
                <input
                  className="mt-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
                  placeholder="可关联工作空间下的项目"
                  value={state.projectId}
                  onChange={(event) => handleFieldChange("projectId", event.target.value)}
                />
              </label>
            </div>
            {!datasetOptions.length && !datasetsQuery.isLoading ? (
              <p className="text-xs text-amber-600">当前工作空间尚未接入数据集，请先完成数据导入。</p>
            ) : null}
            {selectedDatasetId != null && !versionsQuery.isLoading && !versionsQuery.isFetching && versionOptions.length === 0 ? (
              <p className="text-xs text-amber-600">该数据集暂无可用版本，需在数据导入流程中生成版本后再继续。</p>
            ) : null}
            {isDatasetVersionReady &&
            !formatVersionsQuery.isLoading &&
            !formatVersionsQuery.isFetching &&
            formatOptions.length === 0 ? (
              <p className="text-xs text-slate-400">
                未选择格式时将使用激活格式；如需启用其它格式，可先在“格式标准化”页生成并激活。
              </p>
            ) : null}
          </div>
        ) : currentStep === 2 ? (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-slate-900">配置资源与参数</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="flex flex-col text-sm text-slate-600">
                基座模型
                <input
                  className="mt-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
                  value={state.baseModel}
                  onChange={(event) => handleFieldChange("baseModel", event.target.value)}
                />
              </label>
              <label className="flex flex-col text-sm text-slate-600">
                Adapter 类型
                <select
                  className="mt-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
                  value={state.adapterType}
                  onChange={(event) => handleFieldChange("adapterType", event.target.value as TrainingAdapterType)}
                >
                  <option value="lora">LoRA</option>
                  <option value="qlora">QLoRA</option>
                  <option value="dora">DoRA</option>
                  <option value="full-finetune">全量微调</option>
                </select>
              </label>
              <label className="flex flex-col text-sm text-slate-600">
                GPU 数量
                <input
                  className="mt-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
                  value={state.requestedGpus}
                  onChange={(event) => handleFieldChange("requestedGpus", event.target.value)}
                  inputMode="numeric"
                  pattern="[0-9]*"
                />
              </label>
              <label className="flex flex-col text-sm text-slate-600">
                训练队列
                <select
                  className="mt-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
                  value={state.queueName}
                  onChange={(event) => handleFieldChange("queueName", event.target.value)}
                >
                  {QUEUE_OPTIONS.map((queue) => (
                    <option key={queue} value={queue}>
                      {queue}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="flex flex-col text-sm text-slate-600">
              参数（JSON）
              <textarea
                className="mt-1 h-32 rounded-lg border border-slate-200 bg-white px-3 py-2 font-mono text-xs text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
                value={state.params}
                onChange={(event) => handleFieldChange("params", event.target.value)}
              />
              <span className="mt-1 text-[11px] text-slate-500">示例：{"{ \"learning_rate\": 3e-4, \"num_epochs\": 3 }"}</span>
            </label>
            <label className="flex flex-col text-sm text-slate-600">
              备注（可选）
              <textarea
                className="mt-1 h-20 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-200"
                value={state.notes}
                onChange={(event) => handleFieldChange("notes", event.target.value)}
              />
            </label>
            {selectedWorkspaceId != null ? (
              <div className="space-y-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs text-emerald-700">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-emerald-700">历史反馈引用</h3>
                  {feedbackSummaryQuery.isLoading ? <span>加载中…</span> : null}
                </div>
                {feedbackSummaryQuery.isError ? (
                  <p className="text-rose-600">{feedbackSummaryQuery.error?.message ?? "获取反馈失败"}</p>
                ) : null}
                {!feedbackSummaryQuery.isLoading && feedbackItems.length === 0 ? (
                  <p className="text-emerald-700/80">暂无打开的反馈 TODO，可在评估报告中添加。</p>
                ) : null}
                <ul className="space-y-2">
                  {feedbackItems.map((item) => (
                    <li key={item.id} className="rounded-lg border border-emerald-200 bg-white p-3">
                      <p className="text-xs text-slate-700">{item.body}</p>
                      {item.tags.length > 0 ? (
                        <p className="mt-1 text-[11px] text-slate-500">标签：{item.tags.join(", ")}</p>
                      ) : null}
                      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                        <span className="text-[11px] text-slate-500">
                          创建人 #{item.created_by} · {new Date(item.created_at).toLocaleString()}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleApplyFeedback(item)}
                          className="rounded-md border border-emerald-300 bg-emerald-500/10 px-2 py-1 text-[11px] font-medium text-emerald-700 hover:border-emerald-400"
                        >
                          添加到备注
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleValidate}
                className="rounded-md border border-purple-300 bg-purple-50 px-4 py-2 text-sm font-medium text-purple-700 transition hover:border-purple-400"
                disabled={validateMutation.isPending}
              >
                {validateMutation.isPending ? "校验中..." : "预校验配置"}
              </button>
              <button
                type="button"
                onClick={handleSaveDraft}
                className="rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-800"
                disabled={saveDraftMutation.isPending}
              >
                {saveDraftMutation.isPending ? "保存中..." : "保存草稿"}
              </button>
            </div>
            {validationResult ? (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs text-emerald-700">
                <h3 className="text-sm font-semibold text-emerald-700">校验结果</h3>
                <pre className="mt-2 whitespace-pre-wrap font-mono text-[11px] text-emerald-800">
                  {JSON.stringify(validationResult, null, 2)}
                </pre>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-slate-900">确认训练配置</h2>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <dl className="space-y-3 text-sm text-slate-600">
                <div className="grid gap-2 md:grid-cols-2">
                  <div>
                    <dt className="text-slate-500">模板</dt>
                    <dd>{selectedTemplate?.name ?? "未选择"}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">基座模型</dt>
                    <dd>{state.baseModel || "未填写"}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Adapter 类型</dt>
                    <dd>{state.adapterType.toUpperCase()}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">数据集</dt>
                    <dd>{selectedDataset?.name ?? "未选择"}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">数据集版本</dt>
                    <dd>
                      {selectedDatasetVersion
                        ? `v${selectedDatasetVersion.version} · ${
                            VERSION_STATUS_LABEL[selectedDatasetVersion.status]
                          }`
                        : "未选择"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">标准化格式</dt>
                    <dd>
                      {selectedFormatVersion
                        ? `${selectedFormatVersion.format.toUpperCase()} · ${
                            FORMAT_STATUS_LABEL[selectedFormatVersion.status]
                          }${selectedFormatVersion.is_active ? "（当前启用）" : ""}`
                        : "默认激活格式"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">GPU 数量</dt>
                    <dd>{state.requestedGpus || "1"}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">训练队列</dt>
                    <dd>{state.queueName || "default"}</dd>
                  </div>
                </div>
                <div>
                  <dt className="text-slate-500">参数</dt>
                  <dd>
                    <pre className="mt-1 whitespace-pre-wrap font-mono text-[11px] text-slate-700">{state.params}</pre>
                  </dd>
                </div>
                {state.notes ? (
                  <div>
                    <dt className="text-slate-500">备注</dt>
                    <dd>{state.notes}</dd>
                  </div>
                ) : null}
              </dl>
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleValidate}
                className="rounded-md border border-purple-300 bg-purple-50 px-4 py-2 text-sm font-medium text-purple-700 transition hover:border-purple-400"
                disabled={validateMutation.isPending}
              >
                {validateMutation.isPending ? "校验中..." : "重新校验"}
              </button>
              <button
                type="button"
                onClick={handleSaveDraft}
                className="rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-800"
                disabled={saveDraftMutation.isPending}
              >
                保存草稿
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={createJobMutation.isPending}
              >
                {createJobMutation.isPending ? "提交中..." : "发起训练"}
              </button>
            </div>
          </div>
        )}

        <div className="flex items-center justify-between pt-4">
          <button
            type="button"
            onClick={goToPrevious}
            className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-800"
            disabled={currentStep === 0}
          >
            上一步
          </button>
          <button
            type="button"
            onClick={goToNext}
            className="rounded-md border border-purple-300 bg-purple-50 px-3 py-2 text-xs font-medium text-purple-700 transition hover:border-purple-400"
            disabled={currentStep === STEP_LABELS.length - 1}
          >
            下一步
          </button>
        </div>
      </section>

      {lastJob ? (
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">最新训练任务</h2>
          <dl className="mt-4 grid gap-3 text-sm text-slate-600 md:grid-cols-2">
            <div>
              <dt className="text-slate-500">任务 ID</dt>
              <dd>{lastJob.id}</dd>
            </div>
            <div>
              <dt className="text-slate-500">状态</dt>
              <dd>{lastJob.status}</dd>
            </div>
            <div>
              <dt className="text-slate-500">GPU 数量</dt>
              <dd>{lastJob.requested_gpus}</dd>
            </div>
            <div>
              <dt className="text-slate-500">训练队列</dt>
              <dd>{lastJob.queue_name}</dd>
            </div>
            {lastJob.latest_run ? (
              <>
                <div>
                  <dt className="text-slate-500">开始时间</dt>
                  <dd>{new Date(lastJob.latest_run.started_at).toLocaleString()}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">指标</dt>
                  <dd className="font-mono text-xs text-slate-700">
                    {JSON.stringify(lastJob.latest_run.metrics ?? {}, null, 2)}
                  </dd>
                </div>
              </>
            ) : null}
          </dl>
          <p className="mt-4 text-xs text-slate-500">训练日志面板将在后续故事中提供（可通过任务 ID 查询）。</p>
        </section>
      ) : null}
    </AppShell>
  );
}
