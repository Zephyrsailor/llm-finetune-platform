/** Shared HTTP helpers for backend API calls. */

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";

interface ApiError {
  detail?: string;
  message?: string;
}

let isRedirectingToLogin = false;

function redirectToLogin() {
  if (typeof window === "undefined" || isRedirectingToLogin) {
    return;
  }
  isRedirectingToLogin = true;
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  if (window.location.pathname !== "/") {
    window.location.replace("/");
  } else {
    isRedirectingToLogin = false;
  }
}

function hasAuthorizationHeader(headers?: HeadersInit): boolean {
  if (!headers) {
    return false;
  }
  if (headers instanceof Headers) {
    return headers.has("Authorization");
  }
  if (Array.isArray(headers)) {
    return headers.some(([key]) => key.toLowerCase() === "authorization");
  }
  return Object.keys(headers as Record<string, string>).some((key) => key.toLowerCase() === "authorization");
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem("access_token");
  if (!token) {
    return {};
  }
  return { Authorization: `Bearer ${token}` };
}

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) {
    return refreshPromise;
  }
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) {
    return null;
  }
  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE}/v1/auth/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ refresh_token: refreshToken })
      });
      if (!response.ok) {
        return null;
      }
      const result = (await response.json().catch(() => null)) as TokenPair | null;
      if (result?.access_token && result.refresh_token) {
        localStorage.setItem("access_token", result.access_token);
        localStorage.setItem("refresh_token", result.refresh_token);
        return result.access_token;
      }
      return null;
    } catch {
      return null;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

type RequestOptions = {
  retryOn401?: boolean;
};

async function requestJson<T>(path: string, init: RequestInit, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  const isAuthRequest =
    hasAuthorizationHeader(init.headers) ||
    Boolean(localStorage.getItem("access_token")) ||
    Boolean(localStorage.getItem("refresh_token"));
  const shouldSkipRetry = options.retryOn401 === false;
  const isAuthEndpoint = path.startsWith("/v1/auth/");

  if (response.status === 401 && isAuthRequest && !shouldSkipRetry && !isAuthEndpoint) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      const nextHeaders = new Headers(init.headers ?? {});
      nextHeaders.set("Authorization", `Bearer ${newToken}`);
      return requestJson<T>(
        path,
        {
          ...init,
          headers: nextHeaders
        },
        { retryOn401: false }
      );
    }
    redirectToLogin();
    throw new Error("登录状态已失效，请重新登录。");
  }

  if (response.status === 401 && isAuthRequest && !isAuthEndpoint) {
    redirectToLogin();
  }

  const data = (await response.json().catch(() => ({}))) as T | ApiError;
  if (!response.ok) {
    const errorMessage =
      response.status === 401
        ? "登录状态已失效，请重新登录。"
        : (data as ApiError).detail ?? (data as ApiError).message ?? "请求失败";
    throw new Error(errorMessage);
  }
  return data as T;
}

async function postJson<T>(path: string, payload: unknown, init?: RequestInit): Promise<T> {
  const { headers: initHeaders, method: initMethod, ...rest } = init ?? {};
  const mergedHeaders = new Headers({ "Content-Type": "application/json" });
  if (initHeaders != null) {
    const additional = new Headers(initHeaders as HeadersInit);
    additional.forEach((value, key) => {
      mergedHeaders.set(key, value);
    });
  }
  const headerObject: Record<string, string> = {};
  mergedHeaders.forEach((value, key) => {
    const lower = key.toLowerCase();
    const canonical =
      lower === "content-type"
        ? "Content-Type"
        : lower === "authorization"
          ? "Authorization"
          : key;
    headerObject[canonical] = value;
  });

  return requestJson<T>(path, {
    ...rest,
    method: initMethod ?? "POST",
    headers: headerObject,
    body: JSON.stringify(payload)
  });
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface VerificationResponse {
  message: string;
  verification_code?: string;
}

export interface WorkspaceMember {
  user_id: number;
  email: string;
  role: string;
}

export interface ProjectInfo {
  id: number;
  name: string;
  description?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceDetail {
  id: number;
  name: string;
  description?: string | null;
  plan?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  members: WorkspaceMember[];
  projects: ProjectInfo[];
}

export interface ProjectCreateResponse {
  workspace: WorkspaceDetail;
  created_paths: string[];
}

export type RoleOperationValue =
  | "data_import"
  | "training_launch"
  | "deployment_manage"
  | "inference_use"
  | "evaluation_view"
  | "approval_manage";

export interface RoleSummary {
  id: number;
  key: string;
  name: string;
  description?: string | null;
  is_system: boolean;
  operations: RoleOperationValue[];
}

export interface RoleAssignment {
  user_id: number;
  email: string;
  role_ids: number[];
}

export interface RoleOperationOption {
  value: RoleOperationValue;
  label: string;
}

export interface RoleMatrix {
  roles: RoleSummary[];
  assignments: RoleAssignment[];
  operations: RoleOperationOption[];
}

export type ModelVersionStatusValue = "candidate" | "production" | "deprecated";

export interface ModelVersionSummary {
  id: number;
  model_id: number;
  version: number;
  status: ModelVersionStatusValue;
  artifact_path?: string | null;
  metadata: Record<string, unknown>;
  training_run_id?: number | null;
  evaluation_job_id?: number | null;
  evaluation_metrics: Record<string, unknown>;
  evaluation_report_path?: string | null;
  deployment_target?: string | null;
  notes?: string | null;
  created_by?: number | null;
  updated_by?: number | null;
  promoted_by?: number | null;
  promoted_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RegisteredModelSummary {
  id: number;
  workspace_id: number;
  project_id?: number | null;
  name: string;
  description?: string | null;
  base_model?: string | null;
  tags: string[];
  created_by?: number | null;
  updated_by?: number | null;
  created_at: string;
  updated_at: string;
  versions: ModelVersionSummary[];
}

export interface ModelVersionExportResponse {
  path: string;
  format: "json" | "markdown";
}

export interface DeploymentEventSummary {
  id: number;
  deployment_id: number;
  event_type: string;
  level: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface DeploymentSummary {
  id: number;
  workspace_id: number;
  project_id?: number | null;
  model_version_id: number;
  environment: string;
  status: DeploymentStatusValue;
  endpoint_url?: string | null;
  access_token?: string | null;
  config: Record<string, unknown>;
  metrics: Record<string, unknown>;
  traffic_percent?: number | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  events: DeploymentEventSummary[];
}

export type DeploymentStatusValue = "pending" | "deploying" | "active" | "failed" | "rolled_back";

export interface DeploymentListPayload {
  deployments: DeploymentSummary[];
}

export interface InferenceOutput {
  output: string;
}

export interface InferenceInvokeResult {
  call_id: number;
  deployment_id: number;
  model_version_id: number;
  outputs: InferenceOutput[];
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
}

export interface InferenceLogSummary {
  id: number;
  deployment_id?: number | null;
  model_version_id?: number | null;
  status: string;
  latency_ms?: number | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  created_at: string;
}

export interface InferenceLogDetail extends InferenceLogSummary {
  error_message?: string | null;
}

export interface InferenceLogListResponse {
  logs: InferenceLogSummary[];
}

export interface InferenceApiKeyItem {
  id: number;
  name: string;
  is_active: boolean;
  rate_limit_per_minute?: number | null;
  daily_quota?: number | null;
  created_at: string;
  revoked_at?: string | null;
  last_used_at?: string | null;
}

export interface InferenceApiKeyCreationResponse {
  api_key: InferenceApiKeyItem;
  secret: string;
}

export interface InferenceApiKeyListResponse {
  items: InferenceApiKeyItem[];
}

export const authApi = {
  login: (payload: { email: string; password: string }) =>
    postJson<TokenPair>("/v1/auth/login", payload),
  requestRegistration: (payload: { email: string }) =>
    postJson<VerificationResponse>("/v1/auth/register/request", payload),
  confirmRegistration: (payload: { email: string; password: string; code: string }) =>
    postJson<TokenPair>("/v1/auth/register/confirm", payload),
  requestPasswordReset: (payload: { email: string }) =>
    postJson<VerificationResponse>("/v1/auth/password-reset/request", payload),
  confirmPasswordReset: (payload: { email: string; code: string; new_password: string }) =>
    postJson<VerificationResponse>("/v1/auth/password-reset/confirm", payload)
};

export const workspaceApi = {
  list: () =>
    requestJson<WorkspaceDetail[]>("/v1/workspaces", {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  create: (payload: { name: string; description?: string | null; plan?: string | null; member_ids?: number[] }) =>
    postJson<WorkspaceDetail>("/v1/workspaces", payload, {
      headers: {
        ...authHeaders()
      }
    }),
  update: (workspaceId: number, payload: Partial<{ name: string; description: string | null; plan: string | null; status: string }>) =>
    requestJson<WorkspaceDetail>(`/v1/workspaces/${workspaceId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders()
      },
      body: JSON.stringify(payload)
  }),
  createProject: (workspaceId: number, payload: { name: string; description?: string | null }) =>
    postJson<ProjectCreateResponse>(`/v1/workspaces/${workspaceId}/projects`, payload, {
      headers: {
        ...authHeaders()
      }
    }),
  getRoleMatrix: (workspaceId: number) =>
    requestJson<RoleMatrix>(`/v1/workspaces/${workspaceId}/roles`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  createRole: (
    workspaceId: number,
    payload: { name: string; description?: string | null; operations: RoleOperationValue[] }
  ) =>
    postJson<RoleSummary>(`/v1/workspaces/${workspaceId}/roles`, payload, {
      headers: {
        ...authHeaders()
      }
    }),
  updateRole: (
    workspaceId: number,
    roleId: number,
    payload: Partial<{ name: string; description: string | null; operations: RoleOperationValue[] }>
  ) =>
    requestJson<RoleSummary>(`/v1/workspaces/${workspaceId}/roles/${roleId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders()
      },
      body: JSON.stringify(payload)
    }),
  setMemberRoles: (workspaceId: number, userId: number, roleIds: number[]) =>
    postJson<RoleAssignment>(`/v1/workspaces/${workspaceId}/members/${userId}/roles`, { role_ids: roleIds }, {
      headers: {
        ...authHeaders()
      }
    })
};

export type StageStatusValue = "not_started" | "in_progress" | "completed" | "unknown";

export interface StageStatusSummary {
  stage: string;
  status: StageStatusValue;
  responsible?: string | null;
  updated_at?: string | null;
  notes?: string | null;
}

export interface MetricPlaceholderSummary {
  key: string;
  label: string;
  description: string;
  value?: number | null;
  unit?: string | null;
}

export interface DashboardWorkspaceSummary {
  workspace_id: number;
  workspace_name: string;
  stages: StageStatusSummary[];
  metrics: MetricPlaceholderSummary[];
}

export interface DashboardSummary {
  generated_at: string;
  workspaces: DashboardWorkspaceSummary[];
}

export const dashboardApi = {
  summary: (params: { workspaceId?: number } = {}) => {
    const query = params.workspaceId ? `?workspace_id=${params.workspaceId}` : "";
    return requestJson<DashboardSummary>(`/v1/dashboard/summary${query}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    });
  }
};

export type DatasetSourceType = "upload" | "external" | "reference";

export interface Dataset {
  id: number;
  workspace_id: number;
  name: string;
  description?: string | null;
  source_type: DatasetSourceType;
  source_uri?: string | null;
  storage_path?: string | null;
  data_type?: string | null;
  mime_type?: string | null;
  file_size_bytes?: number | null;
  checksum_sha256?: string | null;
  tags: string[];
  notes?: string | null;
  status: "active" | "archived";
  reference_dataset_id?: number | null;
  created_by: number;
  created_at: string;
  updated_at: string;
}

export interface DatasetVersion {
  id: number;
  dataset_id: number;
  version: number;
  status: "pending" | "processing" | "completed" | "failed";
  location_uri?: string | null;
  stats_json?: Record<string, unknown> | null;
  created_by: number;
  created_at: string;
  updated_at: string;
}

export interface DataCleaningJob {
  id: number;
  dataset_version_id: number;
  status: "pending" | "running" | "completed" | "failed";
  template_id?: number | null;
  logs_path?: string | null;
  error_message?: string | null;
  summary_path?: string | null;
  export_manifest?: Record<string, string> | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface DatasetVersionCreateResult {
  version: DatasetVersion;
  job: DataCleaningJob;
  quality_job?: QualityEvaluationJob | null;
}

export interface CreateDatasetPayload {
  workspaceId: number;
  name: string;
  description?: string;
  dataType?: string;
  tags?: string[];
  notes?: string;
  sourceType?: DatasetSourceType;
  sourceUri?: string;
  referenceDatasetId?: number;
  file?: File;
}

export const dataHubApi = {
  async createDataset(payload: CreateDatasetPayload): Promise<Dataset> {
    const formData = new FormData();
    formData.append("workspace_id", String(payload.workspaceId));
    formData.append("name", payload.name);
    if (payload.description) {
      formData.append("description", payload.description);
    }
    if (payload.dataType) {
      formData.append("data_type", payload.dataType);
    }
    if (payload.tags && payload.tags.length > 0) {
      formData.append("tags", JSON.stringify(payload.tags));
    }
    if (payload.notes) {
      formData.append("notes", payload.notes);
    }
    formData.append("source_type", (payload.sourceType ?? "upload") as string);
    if (payload.sourceUri) {
      formData.append("source_uri", payload.sourceUri);
    }
    if (payload.referenceDatasetId != null) {
      formData.append("reference_dataset_id", String(payload.referenceDatasetId));
    }
    if (payload.file) {
      formData.append("upload_file", payload.file, payload.file.name);
    }

    const response = await fetch(`${API_BASE}/v1/datasets`, {
      method: "POST",
      headers: {
        ...authHeaders()
      },
      body: formData
    });
    const data = (await response.json().catch(() => ({}))) as Dataset | ApiError;
    if (!response.ok) {
      const errorMessage = (data as ApiError).detail ?? (data as ApiError).message ?? "创建数据集失败";
      throw new Error(errorMessage);
    }
    return data as Dataset;
  },

  createVersion: (datasetId: number, payload: { notes?: string } = {}) =>
    postJson<DatasetVersionCreateResult>(`/v1/datasets/${datasetId}/versions`, payload, {
      headers: {
        ...authHeaders()
      }
    }),
  listDatasets: (workspaceId: number) =>
    requestJson<Dataset[]>(`/v1/datasets?workspace_id=${workspaceId}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  listVersions: (datasetId: number) =>
    requestJson<DatasetVersion[]>(`/v1/datasets/${datasetId}/versions`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    })
};

export interface CleaningTemplateStep {
  type: string;
  field?: string;
  fields?: string[];
  keywords?: string[];
  replacement?: string;
  mode?: string;
}

export interface CleaningTemplate {
  id: number;
  workspace_id: number;
  name: string;
  description?: string | null;
  is_active: boolean;
  version: number;
  steps: CleaningTemplateStep[];
  created_at: string;
  updated_at: string;
}

export interface CleaningAssignment {
  dataset_id: number;
  template_id: number;
  enabled: boolean;
  assigned_at: string;
}

export interface CleaningSummary {
  dataset_id: number;
  dataset_version_id: number;
  status?: string | null;
  stats: Record<string, unknown>;
  template?: Record<string, unknown> | null;
  logs_path?: string | null;
  summary_path?: string | null;
  export_manifest?: Record<string, string> | null;
}

export interface QualityEvaluationJob {
  id: number;
  dataset_version_id: number;
  status: "pending" | "running" | "completed" | "failed";
  logs_path?: string | null;
  error_message?: string | null;
  summary_path?: string | null;
  export_manifest?: Record<string, string> | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface QualitySummary {
  dataset_id: number;
  dataset_version_id: number;
  status?: string | null;
  stats: Record<string, unknown>;
  summary_path?: string | null;
  report_manifest?: Record<string, string> | null;
  logs_path?: string | null;
}

export type DatasetFormatType = "jsonl" | "sft" | "parquet";
export type DatasetFormatStatus = "pending" | "running" | "completed" | "failed";

export interface DatasetFormatVersion {
  id: number;
  dataset_version_id: number;
  format: DatasetFormatType;
  status: DatasetFormatStatus;
  path?: string | null;
  logs_path?: string | null;
  checksum_sha256?: string | null;
  file_size_bytes?: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
}

export type TrainingAdapterType = "lora" | "qlora" | "dora" | "full-finetune";
export type TrainingJobStatus = "pending" | "queued" | "running" | "completed" | "failed" | "canceled";

export interface TrainingTemplate {
  id: number;
  workspace_id: number;
  name: string;
  description?: string | null;
  base_model: string;
  adapter_type: TrainingAdapterType;
  params: Record<string, unknown>;
  is_builtin: boolean;
  created_by?: number | null;
  created_at: string;
  updated_at: string;
}

export interface TrainingRun {
  id: number;
  job_id: number;
  resumed_from_snapshot_id?: number | null;
  status: TrainingJobStatus;
  started_at: string;
  finished_at?: string | null;
  metrics?: Record<string, unknown> | null;
  artifact_uri?: string | null;
  exit_code?: number | null;
}

export interface TrainingJob {
  id: number;
  workspace_id: number;
  project_id?: number | null;
  dataset_version_id: number;
  dataset_format_version_id?: number | null;
  training_template_id?: number | null;
  base_model: string;
  adapter_type: TrainingAdapterType;
  status: TrainingJobStatus;
  params: Record<string, unknown>;
  notes?: string | null;
  scheduled_by: number;
  scheduled_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
  requested_gpus: number;
  queue_name: string;
  latest_run?: TrainingRun | null;
}

export type EvaluationJobStatus = "pending" | "running" | "completed" | "failed";

export interface EvaluationTemplate {
  id: number;
  key: string;
  name: string;
  description?: string | null;
  task_type: "question_answering" | "conversation" | "classification";
  metrics: string[];
  config?: Record<string, unknown> | null;
  is_builtin: boolean;
  workspace_id?: number | null;
  created_at: string;
  updated_at: string;
}

export interface EvaluationJobMetrics {
  example_count?: number;
  avg_tokens_per_example?: number;
  bleu?: number;
  rouge_l?: number;
  exact_match?: number;
  perplexity?: number;
  thresholds?: Record<string, { threshold?: number; triggered?: boolean }>;
  baseline?: Record<string, number>;
  delta?: Record<string, number>;
  [key: string]: unknown;
}

export interface EvaluationJob {
  id: number;
  workspace_id: number;
  project_id?: number | null;
  training_run_id?: number | null;
  evaluation_template_id: number;
  dataset_version_id?: number | null;
  dataset_path?: string | null;
  artifact_path?: string | null;
  report_path?: string | null;
  status: EvaluationJobStatus;
  metrics?: EvaluationJobMetrics | null;
  error_message?: string | null;
  created_by?: number | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  trigger_mode: "manual" | "automatic";
}

export interface EvaluationReportCase {
  reference: string;
  prediction: string;
  score?: number | null;
}

export interface EvaluationReport {
  job: Record<string, unknown>;
  metrics: Record<string, unknown>;
  cases: Record<string, EvaluationReportCase[]>;
  artifacts: Record<string, string>;
  training: Record<string, unknown>;
  dataset?: Record<string, unknown> | null;
  report_markdown?: string | null;
  report_html?: string | null;
}

export interface EvaluationReportShare {
  token: string;
  share_path: string;
  expires_at: string;
}

export type EvaluationFeedbackKind = "comment" | "todo" | "business_metric";
export type EvaluationFeedbackStatus = "open" | "resolved";

export interface EvaluationFeedback {
  id: number;
  workspace_id: number;
  project_id?: number | null;
  evaluation_job_id: number;
  training_run_id?: number | null;
  kind: EvaluationFeedbackKind;
  status: EvaluationFeedbackStatus;
  body: string;
  tags: string[];
  metric_name?: string | null;
  metric_value?: number | null;
  created_by: number;
  updated_by?: number | null;
  resolved_by?: number | null;
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
}

export interface EvaluationFeedbackExportResult {
  path: string;
  format: "markdown" | "json";
  count: number;
}

export interface TrainingExperimentSummary {
  run_id: number;
  job_id: number;
  workspace_id: number;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  base_model: string;
  adapter_type: string;
  dataset: Record<string, unknown>;
  metrics: Record<string, unknown>;
  resource: Record<string, unknown>;
}

export interface TrainingExperimentDetail extends TrainingExperimentSummary {
  metadata: Record<string, unknown>;
  artifact_uri?: string | null;
  exit_code?: number | null;
}

export interface TrainingExperimentComparison {
  run_a: TrainingExperimentSummary;
  run_b: TrainingExperimentSummary;
  diff: Record<string, Array<Record<string, unknown>>>;
  snapshots: Record<string, Array<Record<string, unknown>>>;
  alerts: Record<string, Array<Record<string, unknown>>>;
}

export interface TrainingExperimentExportResult {
  workspace_id: number;
  format: string;
  path: string;
  generated_at?: string | null;
  size_bytes: number;
}

export interface TrainingWizardDraft {
  workspace_id: number;
  payload: Record<string, unknown> | null;
  updated_at: string | null;
}

export interface TrainingFeedbackSummaryItem {
  id: number;
  evaluation_job_id: number;
  training_run_id?: number | null;
  kind: EvaluationFeedbackKind;
  status: EvaluationFeedbackStatus;
  body: string;
  tags: string[];
  metric_name?: string | null;
  metric_value?: number | null;
  created_by: number;
  created_at: string;
}

export interface TrainingFeedbackSummary {
  workspace_id: number;
  project_id?: number | null;
  items: TrainingFeedbackSummaryItem[];
}

export interface TrainingWizardValidation {
  workspace_id: number;
  project_id?: number | null;
  dataset_version_id: number;
  dataset_format_version_id?: number | null;
  training_template_id?: number | null;
  base_model: string;
  adapter_type: TrainingAdapterType;
  params: Record<string, unknown>;
  requested_gpus: number;
  queue_name: string;
}

export interface TrainingWizardValidatePayload {
  workspace_id: number;
  project_id?: number | null;
  dataset_version_id: number;
  dataset_format_version_id?: number | null;
  training_template_id?: number | null;
  base_model?: string | null;
  adapter_type?: TrainingAdapterType | null;
  params?: Record<string, unknown>;
  requested_gpus?: number | null;
  queue_name?: string | null;
}

export type TrainingMetricName =
  | "loss"
  | "perplexity"
  | "throughput"
  | "gpu_memory"
  | "evaluation_bleu"
  | "evaluation_rouge_l"
  | "evaluation_exact_match"
  | "evaluation_perplexity"
  | "evaluation_failure";
export type TrainingAlertOperator = "gt" | "gte" | "lt" | "lte";
export type TrainingAlertStatus = "triggered" | "acknowledged" | "resolved";
export type TrainingSnapshotTriggerType = "scheduled" | "metric" | "manual";

export interface TrainingSnapshot {
  id: number;
  workspace_id: number;
  job_id: number;
  run_id: number;
  path: string;
  step?: number | null;
  epoch?: number | null;
  metrics?: Record<string, unknown> | null;
  trigger_type: TrainingSnapshotTriggerType;
  created_by?: number | null;
  created_at: string;
  notes?: string | null;
  restored_at?: string | null;
  restored_by?: number | null;
}

export interface TrainingMetricSample {
  run_id: number;
  metric: TrainingMetricName;
  value: number;
  recorded_at: string;
}

export interface TrainingAlertRule {
  id: number;
  workspace_id: number;
  name: string;
  metric: TrainingMetricName;
  operator: TrainingAlertOperator;
  threshold: number;
  cooldown_seconds: number;
  is_active: boolean;
  channels?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface TrainingAlert {
  id: number;
  rule_id: number;
  run_id: number;
  value: number;
  status: TrainingAlertStatus;
  triggered_at: string;
  acknowledged_at?: string | null;
  resolved_at?: string | null;
  notes?: string | null;
}

export interface TrainingMonitorRun {
  run_id: number;
  job_id: number;
  workspace_id: number;
  project_id?: number | null;
  status: TrainingJobStatus;
  started_at: string;
  finished_at?: string | null;
  job_error_message?: string | null;
  latest_metrics: TrainingMetricSample[];
  alerts: TrainingAlert[];
  latest_evaluation?: {
    job_id?: number;
    metrics?: Record<string, unknown>;
    updated_at?: string;
  } | null;
}

export const cleaningApi = {
  listTemplates: (workspaceId: number, { activeOnly = false }: { activeOnly?: boolean } = {}) =>
    requestJson<CleaningTemplate[]>(`/v1/datasets/cleaning/templates?workspace_id=${workspaceId}&active_only=${activeOnly}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  createTemplate: (payload: {
    workspaceId: number;
    name: string;
    description?: string;
    steps: CleaningTemplateStep[];
    isActive?: boolean;
  }) =>
    postJson<CleaningTemplate>("/v1/datasets/cleaning/templates", {
      workspace_id: payload.workspaceId,
      name: payload.name,
      description: payload.description,
      steps: payload.steps,
      is_active: payload.isActive ?? true
    }, {
      headers: {
        ...authHeaders()
      }
    }),
  updateTemplate: (templateId: number, payload: {
    name?: string;
    description?: string;
    steps?: CleaningTemplateStep[];
    isActive?: boolean;
  }) =>
    requestJson<CleaningTemplate>(`/v1/datasets/cleaning/templates/${templateId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders()
      },
      body: JSON.stringify({
        name: payload.name,
        description: payload.description,
        steps: payload.steps,
        is_active: payload.isActive
      })
    }),
  assignTemplate: (datasetId: number, payload: { templateId: number | null; enabled: boolean }) =>
    postJson<CleaningAssignment | null>(`/v1/datasets/${datasetId}/cleaning/assignment`, {
      template_id: payload.templateId,
      enabled: payload.enabled
    }, {
      headers: {
        ...authHeaders()
      }
    }),
  getAssignment: (datasetId: number) =>
    requestJson<CleaningAssignment | null>(`/v1/datasets/${datasetId}/cleaning/assignment`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  getSummary: (datasetId: number, versionId: number) =>
    requestJson<CleaningSummary>(`/v1/datasets/${datasetId}/versions/${versionId}/cleaning/summary`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  async downloadExport(datasetId: number, versionId: number, format: "jsonl" | "csv"): Promise<Blob> {
    const response = await fetch(
      `${API_BASE}/v1/datasets/${datasetId}/versions/${versionId}/cleaning/export?format=${format}`,
      {
        method: "GET",
        headers: {
          ...authHeaders()
        }
      }
    );
    if (!response.ok) {
      throw new Error("导出失败");
    }
    return response.blob();
  }
};

export const qualityApi = {
  run: (datasetId: number, versionId: number) =>
    postJson<QualityEvaluationJob>(`/v1/datasets/${datasetId}/versions/${versionId}/quality/run`, {}, {
      headers: {
        ...authHeaders()
      }
    }),
  summary: (datasetId: number, versionId: number) =>
    requestJson<QualitySummary>(`/v1/datasets/${datasetId}/versions/${versionId}/quality/summary`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  async downloadExport(datasetId: number, versionId: number, format: "json" | "csv"): Promise<Blob> {
    const response = await fetch(
      `${API_BASE}/v1/datasets/${datasetId}/versions/${versionId}/quality/export?format=${format}`,
      {
        method: "GET",
        headers: {
          ...authHeaders()
        }
      }
    );
    if (!response.ok) {
      throw new Error("导出质量评估报告失败");
    }
    return response.blob();
  }
};

export const formatApi = {
  runConversion: (
    datasetId: number,
    versionId: number,
    formats?: DatasetFormatType[]
  ) =>
    postJson<DatasetFormatVersion[]>(
      `/v1/datasets/${datasetId}/versions/${versionId}/formats/run`,
      formats && formats.length > 0 ? { formats } : {},
      {
        headers: {
          ...authHeaders()
        }
      }
    ),
  listFormats: (datasetId: number, versionId: number) =>
    requestJson<DatasetFormatVersion[]>(
      `/v1/datasets/${datasetId}/versions/${versionId}/formats`,
      {
        method: "GET",
        headers: {
          ...authHeaders()
        }
      }
    ),
  activateFormat: (datasetId: number, versionId: number, formatId: number) =>
    postJson<DatasetFormatVersion>(
      `/v1/datasets/${datasetId}/versions/${versionId}/formats/${formatId}/activate`,
      {},
      {
        headers: {
          ...authHeaders()
        }
      }
    ),
  async downloadExport(datasetId: number, versionId: number, format: DatasetFormatType): Promise<Blob> {
    const response = await fetch(
      `${API_BASE}/v1/datasets/${datasetId}/versions/${versionId}/formats/export?fmt=${format}`,
      {
        method: "GET",
        headers: {
          ...authHeaders()
        }
      }
    );
    if (!response.ok) {
      throw new Error("下载格式文件失败");
    }
    return response.blob();
  }
};

export const trainingApi = {
  listTemplates: (workspaceId: number) =>
    requestJson<TrainingTemplate[]>(`/v1/training/templates?workspace_id=${workspaceId}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  createTemplate: (payload: {
    workspace_id: number;
    name: string;
    base_model: string;
    adapter_type: TrainingAdapterType;
    description?: string | null;
    params?: Record<string, unknown>;
  }) =>
    postJson<TrainingTemplate>("/v1/training/templates", payload, {
      headers: {
        ...authHeaders()
      }
    }),
  updateTemplate: (
    templateId: number,
    payload: {
      name?: string;
      base_model?: string;
      adapter_type?: TrainingAdapterType;
      description?: string | null;
      params?: Record<string, unknown>;
    }
  ) =>
    requestJson<TrainingTemplate>(`/v1/training/templates/${templateId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders()
      },
      body: JSON.stringify(payload)
    }),
  cloneTemplate: (templateId: number, payload: { name?: string | null }) =>
    postJson<TrainingTemplate>(`/v1/training/templates/${templateId}:clone`, payload ?? {}, {
      headers: {
        ...authHeaders()
      }
    }),
  deleteTemplate: async (templateId: number): Promise<void> => {
    const response = await fetch(`${API_BASE}/v1/training/templates/${templateId}`, {
      method: "DELETE",
      headers: {
        ...authHeaders()
      }
    });
    if (!response.ok) {
      const data = (await response.json().catch(() => ({}))) as ApiError;
      const errorMessage = data.detail ?? data.message ?? "模板删除失败";
      throw new Error(errorMessage);
    }
  },
  getWizardDraft: (workspaceId: number) =>
    requestJson<TrainingWizardDraft>(`/v1/training/wizard/draft?workspace_id=${workspaceId}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  saveWizardDraft: (payload: { workspace_id: number; payload?: Record<string, unknown> | null }) =>
    postJson<TrainingWizardDraft>("/v1/training/wizard/draft", payload, {
      headers: {
        ...authHeaders()
      }
    }),
  validateWizard: (payload: TrainingWizardValidatePayload) =>
    postJson<TrainingWizardValidation>("/v1/training/wizard/validate", payload, {
      headers: {
        ...authHeaders()
      }
    }),
  createJob: (payload: {
    workspace_id: number;
    dataset_version_id: number;
    dataset_format_version_id?: number | null;
    training_template_id?: number | null;
    project_id?: number | null;
    base_model?: string | null;
    adapter_type?: TrainingAdapterType | null;
    params?: Record<string, unknown>;
    notes?: string | null;
    requested_gpus?: number | null;
    queue_name?: string | null;
  }) =>
    postJson<TrainingJob>("/v1/training/jobs", payload, {
      headers: {
        ...authHeaders()
      }
    }),
  getJob: (jobId: number) =>
    requestJson<TrainingJob>(`/v1/training/jobs/${jobId}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  listFeedbackSummaries: (
    workspaceId: number,
    options: { projectId?: number | null; limit?: number } = {}
  ) => {
    const params = new URLSearchParams({ workspace_id: String(workspaceId) });
    if (options.projectId != null) {
      params.set("project_id", String(options.projectId));
    }
    if (options.limit) {
      params.set("limit", String(options.limit));
    }
    return requestJson<TrainingFeedbackSummary>(`/v1/training/feedback-summaries?${params.toString()}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    });
  }
};

export const trainingExperimentsApi = {
  list: (workspaceId: number, options: { jobId?: number; limit?: number } = {}) => {
    const params = new URLSearchParams({ workspace_id: String(workspaceId) });
    if (options.jobId) {
      params.set("job_id", String(options.jobId));
    }
    if (options.limit) {
      params.set("limit", String(options.limit));
    }
    return requestJson<TrainingExperimentSummary[]>(`/v1/training/experiments?${params.toString()}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    });
  },
  detail: (runId: number) =>
    requestJson<TrainingExperimentDetail>(`/v1/training/experiments/${runId}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  compare: (runAId: number, runBId: number) =>
    postJson<TrainingExperimentComparison>(
      "/v1/training/experiments/compare",
      {
        run_a_id: runAId,
        run_b_id: runBId
      },
      {
        headers: {
          ...authHeaders()
        }
      }
    ),
  export: (payload: { workspace_id: number; run_ids: number[]; format: "json" | "csv" | "markdown" }) =>
    postJson<TrainingExperimentExportResult>("/v1/training/experiments/export", payload, {
      headers: {
        ...authHeaders()
      }
    })
};

export const evaluationApi = {
  listTemplates: (workspaceId: number) =>
    requestJson<EvaluationTemplate[]>(`/v1/evaluations/templates?workspace_id=${workspaceId}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  getTemplate: (templateId: number) =>
    requestJson<EvaluationTemplate>(`/v1/evaluations/templates/${templateId}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  async createJob(payload: {
    workspace_id: number;
    evaluation_template_id: number;
    project_id?: number | null;
    training_run_id?: number | null;
    dataset_version_id?: number | null;
    dataset_file?: File | null;
  }): Promise<EvaluationJob> {
    const form = new FormData();
    form.append("workspace_id", String(payload.workspace_id));
    form.append("evaluation_template_id", String(payload.evaluation_template_id));
    if (payload.project_id != null) {
      form.append("project_id", String(payload.project_id));
    }
    if (payload.training_run_id != null) {
      form.append("training_run_id", String(payload.training_run_id));
    }
    if (payload.dataset_version_id != null) {
      form.append("dataset_version_id", String(payload.dataset_version_id));
    }
    if (payload.dataset_file) {
      form.append("dataset_file", payload.dataset_file, payload.dataset_file.name);
    }

    const response = await fetch(`${API_BASE}/v1/evaluations/jobs`, {
      method: "POST",
      headers: {
        ...authHeaders()
      },
      body: form
    });
    const data = (await response.json().catch(() => ({}))) as EvaluationJob | ApiError;
    if (!response.ok) {
      const errorMessage = (data as ApiError).detail ?? (data as ApiError).message ?? "创建评估任务失败";
      throw new Error(errorMessage);
    }
    return data as EvaluationJob;
  },
  listJobs: (workspaceId: number, options: { trainingRunId?: number } = {}) => {
    const params = new URLSearchParams({ workspace_id: String(workspaceId) });
    if (options.trainingRunId != null) {
      params.set("training_run_id", String(options.trainingRunId));
    }
    return requestJson<EvaluationJob[]>(`/v1/evaluations/jobs?${params.toString()}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    });
  },
  getJob: (jobId: number) =>
    requestJson<EvaluationJob>(`/v1/evaluations/jobs/${jobId}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  async exportJob(jobId: number, format: "markdown" | "json" | "pdf" = "markdown"): Promise<Blob> {
    const response = await fetch(
      `${API_BASE}/v1/evaluations/jobs/${jobId}/export?format=${format}`,
      {
        method: "GET",
        headers: {
          ...authHeaders()
        }
      }
    );
    if (!response.ok) {
      const data = (await response.json().catch(() => ({}))) as ApiError;
      const errorMessage = data.detail ?? data.message ?? "导出评估结果失败";
      throw new Error(errorMessage);
    }
    return response.blob();
  },
  getReport: (jobId: number) =>
    requestJson<EvaluationReport>(`/v1/evaluations/reports/${jobId}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  shareReport: (jobId: number) =>
    requestJson<EvaluationReportShare>(`/v1/evaluations/reports/${jobId}/share`, {
      method: "POST",
      headers: {
        ...authHeaders()
      }
    }),
  getSharedReport: (token: string) =>
    requestJson<EvaluationReport>(`/v1/evaluations/reports/shared/${token}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  listFeedback: (
    jobId: number,
    options: { status?: EvaluationFeedbackStatus; kind?: EvaluationFeedbackKind; tag?: string } = {}
  ) => {
    const params = new URLSearchParams();
    if (options.status) params.set("status", options.status);
    if (options.kind) params.set("kind", options.kind);
    if (options.tag) params.set("tag", options.tag);
    const query = params.toString();
    const suffix = query ? `?${query}` : "";
    return requestJson<EvaluationFeedback[]>(`/v1/evaluations/jobs/${jobId}/feedback${suffix}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    });
  },
  createFeedback: (
    jobId: number,
    payload: {
      workspace_id: number;
      kind: EvaluationFeedbackKind;
      body: string;
      tags?: string[];
      status?: EvaluationFeedbackStatus;
      training_run_id?: number | null;
      metric_name?: string | null;
      metric_value?: number | null;
    }
  ) =>
    postJson<EvaluationFeedback>(`/v1/evaluations/jobs/${jobId}/feedback`, payload, {
      headers: {
        ...authHeaders()
      }
    }),
  updateFeedback: (
    jobId: number,
    feedbackId: number,
    payload: {
      body?: string;
      status?: EvaluationFeedbackStatus;
      tags?: string[];
      metric_name?: string | null;
      metric_value?: number | null;
    }
  ) =>
    requestJson<EvaluationFeedback>(`/v1/evaluations/jobs/${jobId}/feedback/${feedbackId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders()
      },
      body: JSON.stringify(payload)
    }),
  deleteFeedback: (jobId: number, feedbackId: number) =>
    requestJson<void>(`/v1/evaluations/jobs/${jobId}/feedback/${feedbackId}`, {
      method: "DELETE",
      headers: {
        ...authHeaders()
      }
    }),
  exportFeedback: (
    jobId: number,
    options: {
      format?: "markdown" | "json";
      status?: EvaluationFeedbackStatus;
      kind?: EvaluationFeedbackKind;
      tag?: string;
    } = {}
  ) => {
    const params = new URLSearchParams();
    if (options.format) params.set("format", options.format);
    if (options.status) params.set("status", options.status);
    if (options.kind) params.set("kind", options.kind);
    if (options.tag) params.set("tag", options.tag);
    const query = params.toString();
    const suffix = query ? `?${query}` : "";
    return requestJson<EvaluationFeedbackExportResult>(
      `/v1/evaluations/jobs/${jobId}/feedback:export${suffix}`,
      {
        method: "POST",
        headers: {
          ...authHeaders()
        }
      }
    );
  }
};

export const trainingSnapshotApi = {
  list: ({ workspaceId, runId }: { workspaceId?: number | null; runId?: number | null }) => {
    const params = new URLSearchParams();
    if (workspaceId) params.set("workspace_id", String(workspaceId));
    if (runId) params.set("run_id", String(runId));
    const query = params.toString();
    const suffix = query ? `?${query}` : "";
    return requestJson<TrainingSnapshot[]>(`/v1/training/snapshots${suffix}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    });
  },
  get: (snapshotId: number) =>
    requestJson<TrainingSnapshot>(`/v1/training/snapshots/${snapshotId}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  resume: (snapshotId: number, payload?: { notes?: string }) =>
    postJson<TrainingRun>(`/v1/training/snapshots/${snapshotId}:resume`, payload ?? {}, {
      headers: {
        ...authHeaders()
      }
    }),
  rollback: (snapshotId: number, payload?: { reason?: string }) =>
    postJson<TrainingSnapshot>(`/v1/training/snapshots/${snapshotId}:rollback`, payload ?? {}, {
      headers: {
        ...authHeaders()
      }
    })
};

export const trainingMonitorApi = {
  listRuns: (workspaceId: number) =>
    requestJson<TrainingMonitorRun[]>(`/v1/training/monitor/runs?workspace_id=${workspaceId}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  listMetrics: (runId: number) =>
    requestJson<TrainingMetricSample[]>(`/v1/training/monitor/runs/${runId}/metrics`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  listAlertRules: (workspaceId: number) =>
    requestJson<TrainingAlertRule[]>(`/v1/training/monitor/alert-rules?workspace_id=${workspaceId}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  createAlertRule: (payload: {
    workspace_id: number;
    name: string;
    metric: TrainingMetricName;
    operator: TrainingAlertOperator;
    threshold: number;
    cooldown_seconds?: number;
    channels?: Record<string, unknown> | null;
  }) =>
    postJson<TrainingAlertRule>("/v1/training/monitor/alert-rules", payload, {
      headers: {
        ...authHeaders()
      }
    }),
  updateAlertRule: (ruleId: number, payload: {
    name?: string;
    operator?: TrainingAlertOperator;
    threshold?: number;
    cooldown_seconds?: number;
    is_active?: boolean;
    channels?: Record<string, unknown> | null;
  }) =>
    requestJson<TrainingAlertRule>(`/v1/training/monitor/alert-rules/${ruleId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders()
      },
      body: JSON.stringify(payload)
    }),
  listAlerts: (workspaceId: number) =>
    requestJson<TrainingAlert[]>(`/v1/training/monitor/alerts?workspace_id=${workspaceId}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  updateAlertStatus: (alertId: number, payload: { status: TrainingAlertStatus; notes?: string | null }) =>
    postJson<TrainingAlert>(`/v1/training/monitor/alerts/${alertId}/status`, payload, {
      headers: {
        ...authHeaders()
      }
    }),
  exportMetrics: async (runId: number): Promise<Blob> => {
    const response = await fetch(`${API_BASE}/v1/training/monitor/metrics/export?run_id=${runId}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    });
    if (!response.ok) {
      throw new Error("下载指标数据失败");
    }
    return response.blob();
  },
  exportAlerts: async (workspaceId: number): Promise<Blob> => {
    const response = await fetch(`${API_BASE}/v1/training/monitor/alerts/export?workspace_id=${workspaceId}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    });
    if (!response.ok) {
      throw new Error("下载告警数据失败");
    }
    return response.blob();
  }
};

export const modelRegistryApi = {
  list: ({ workspaceId, projectId, status }: { workspaceId: number; projectId?: number | null; status?: ModelVersionStatusValue | null }) => {
    const params = new URLSearchParams({ workspace_id: String(workspaceId) });
    if (projectId != null) params.set('project_id', String(projectId));
    if (status) params.set('status', status);
    const suffix = `?${params.toString()}`;
    return requestJson<RegisteredModelSummary[]>(`/v1/models${suffix}`, {
      method: 'GET',
      headers: {
        ...authHeaders()
      }
    });
  },
  get: (modelId: number) =>
    requestJson<RegisteredModelSummary>(`/v1/models/${modelId}`, {
      method: 'GET',
      headers: {
        ...authHeaders()
      }
    }),
  create: (payload: {
    workspace_id: number;
    project_id?: number | null;
    name: string;
    description?: string | null;
    base_model?: string | null;
    tags?: string[];
  }) =>
    postJson<RegisteredModelSummary>('/v1/models', payload, {
      headers: {
        ...authHeaders()
      }
    }),
  createVersion: (modelId: number, payload: {
    training_run_id?: number | null;
    evaluation_job_id?: number | null;
    metadata?: Record<string, unknown> | null;
    notes?: string | null;
    deployment_target?: string | null;
    artifact_path?: string | null;
  }) =>
    postJson<ModelVersionSummary>(`/v1/models/${modelId}/versions`, payload, {
      headers: {
        ...authHeaders()
      }
    }),
  updateVersionStatus: (modelId: number, versionId: number, payload: {
    status: ModelVersionStatusValue;
    notes?: string | null;
    deployment_target?: string | null;
  }) =>
    requestJson<ModelVersionSummary>(`/v1/models/${modelId}/versions/${versionId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders()
      },
      body: JSON.stringify(payload)
    }),
  exportVersion: (modelId: number, versionId: number, format: 'json' | 'markdown' = 'json') =>
    requestJson<ModelVersionExportResponse>(`/v1/models/${modelId}/versions/${versionId}:export?format=${format}`, {
      method: 'POST',
      headers: {
        ...authHeaders()
      }
    })
};

export const deploymentApi = {
  list: ({ workspaceId, projectId, status }: { workspaceId: number; projectId?: number | null; status?: DeploymentStatusValue | null }) => {
    const params = new URLSearchParams({ workspace_id: String(workspaceId) });
    if (projectId != null) params.set("project_id", String(projectId));
    if (status) params.set("status", status);
    const suffix = `?${params.toString()}`;
    return requestJson<DeploymentListPayload>(`/v1/deployments${suffix}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    });
  },
  create: (payload: {
    workspace_id: number;
    project_id?: number | null;
    model_version_id: number;
    environment: string;
    replicas: number;
    max_batch_size: number;
    max_concurrency: number;
    notes?: string | null;
  }) =>
    postJson<DeploymentSummary>("/v1/deployments", payload, {
      headers: {
        ...authHeaders()
      }
    }),
  updateTraffic: (deploymentId: number, payload: { traffic_percent: number }) =>
    requestJson<DeploymentSummary>(`/v1/deployments/${deploymentId}/traffic`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders()
      },
      body: JSON.stringify(payload)
    }),
  rollback: (deploymentId: number, payload: { reason?: string | null }) =>
    requestJson<DeploymentSummary>(`/v1/deployments/${deploymentId}/rollback`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders()
      },
      body: JSON.stringify(payload)
    })
};

export const inferenceApi = {
  invoke: (payload: {
    workspace_id: number;
    deployment_id?: number | null;
    model_version_id?: number | null;
    inputs: string[];
    parameters?: Record<string, unknown> | null;
  }) =>
    postJson<InferenceInvokeResult>("/v1/inference", payload, {
      headers: {
        ...authHeaders()
      }
    }),
  listLogs: ({ workspaceId, limit = 50 }: { workspaceId: number; limit?: number }) => {
    const params = new URLSearchParams({
      workspace_id: String(workspaceId),
      limit: String(limit)
    });
    return requestJson<InferenceLogListResponse>(`/v1/inference/logs?${params.toString()}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    });
  },
  getCall: (workspaceId: number, callId: number) =>
    requestJson<InferenceLogDetail>(`/v1/inference/calls/${callId}?workspace_id=${workspaceId}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  createApiKey: (payload: {
    workspace_id: number;
    name: string;
    rate_limit_per_minute?: number | null;
    daily_quota?: number | null;
  }) =>
    postJson<InferenceApiKeyCreationResponse>("/v1/inference/api-keys", payload, {
      headers: {
        ...authHeaders()
      }
    }),
  listApiKeys: (workspaceId: number) =>
    requestJson<InferenceApiKeyListResponse>(`/v1/inference/api-keys?workspace_id=${workspaceId}`, {
      method: "GET",
      headers: {
        ...authHeaders()
      }
    }),
  revokeApiKey: (workspaceId: number, apiKeyId: number) =>
    requestJson<InferenceApiKeyItem>(`/v1/inference/api-keys/${apiKeyId}?workspace_id=${workspaceId}`, {
      method: "DELETE",
      headers: {
        ...authHeaders()
      }
    })
};
