import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { TrainingWizardPage } from "./TrainingWizardPage";

const now = new Date().toISOString();

function mockJsonResponse<T>(data: T, ok = true): Response {
  return {
    ok,
    json: async () => data
  } as unknown as Response;
}

describe("TrainingWizardPage", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false
        }
      }
    });
    vi.restoreAllMocks();
    localStorage.clear();
    localStorage.setItem("access_token", "token");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    queryClient.clear();
  });

  function renderPage() {
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <TrainingWizardPage />
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  test("保存草稿、校验并提交训练", async () => {
    const builtinTemplates = [
      {
        id: 10,
        workspace_id: 1,
        name: "LoRA 默认模板",
        description: "系统模板",
        base_model: "meta-llama/Llama-3-8b-instruct",
        adapter_type: "lora",
        params: {
          learning_rate: 5e-4,
          lora_rank: 16,
          num_epochs: 3
        },
        is_builtin: true,
        created_by: null,
        created_at: now,
        updated_at: now
      }
    ];

    const jobResponse = {
      id: 301,
      workspace_id: 1,
      project_id: null,
      dataset_version_id: 77,
      dataset_format_version_id: 88,
      training_template_id: 10,
      base_model: "meta-llama/Llama-3-8b-instruct",
      adapter_type: "lora",
      status: "completed",
      params: { num_epochs: 3 },
      notes: "",
      scheduled_by: 1,
      scheduled_at: now,
      started_at: now,
      finished_at: now,
      error_message: null,
      requested_gpus: 2,
      queue_name: "high-memory",
      latest_run: {
        id: 401,
        job_id: 301,
        status: "completed",
        started_at: now,
        finished_at: now,
        metrics: { final_loss: 1.2 },
        artifact_uri: "/var/lib/llmft/training/1/301/artifacts",
        exit_code: 0
      }
    };

    let draftState = { workspace_id: 1, payload: null as Record<string, unknown> | null, updated_at: null as string | null };

    const fetchMock = vi.spyOn(global, "fetch");
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const method = (init?.method ?? "GET").toUpperCase();

      if (url.endsWith("/api/v1/workspaces") && method === "GET") {
        return mockJsonResponse([
          {
            id: 1,
            name: "Workspace A",
            description: null,
            plan: null,
            status: "active",
            created_at: now,
            updated_at: now,
            members: [],
            projects: []
          }
        ]);
      }

      if (url.includes("/api/v1/training/templates") && method === "GET") {
        return mockJsonResponse(builtinTemplates);
      }

      if (url.includes("/api/v1/training/wizard/draft") && method === "GET") {
        return mockJsonResponse(draftState);
      }

      if (url.includes("/api/v1/training/wizard/draft") && method === "POST") {
        const body = JSON.parse(init?.body as string);
        draftState = {
          workspace_id: body.workspace_id,
          payload: body.payload,
          updated_at: now
        };
        return mockJsonResponse(draftState);
      }

      if (url.includes("/api/v1/training/wizard/validate") && method === "POST") {
        const body = JSON.parse(init?.body as string);
        return mockJsonResponse({
          workspace_id: body.workspace_id,
          project_id: body.project_id ?? null,
          dataset_version_id: body.dataset_version_id,
          dataset_format_version_id: body.dataset_format_version_id ?? null,
          training_template_id: body.training_template_id ?? null,
          base_model: body.base_model ?? builtinTemplates[0].base_model,
          adapter_type: body.adapter_type ?? builtinTemplates[0].adapter_type,
          params: body.params ?? {},
          requested_gpus: body.requested_gpus ?? 1,
          queue_name: body.queue_name ?? "default"
        });
      }

      if (url.endsWith("/api/v1/training/jobs") && method === "POST") {
        const body = JSON.parse(init?.body as string);
        return mockJsonResponse({
          ...jobResponse,
          dataset_version_id: body.dataset_version_id,
          dataset_format_version_id: body.dataset_format_version_id ?? null,
          training_template_id: body.training_template_id ?? null,
          base_model: body.base_model ?? jobResponse.base_model,
          adapter_type: body.adapter_type ?? jobResponse.adapter_type,
          params: body.params ?? {},
          requested_gpus: body.requested_gpus ?? jobResponse.requested_gpus,
          queue_name: body.queue_name ?? jobResponse.queue_name
        });
      }

      if (url.includes("/api/v1/training/feedback-summaries") && method === "GET") {
        return mockJsonResponse({ workspace_id: 1, project_id: null, items: [] });
      }

      throw new Error(`Unhandled request ${method} ${url}`);
    });

    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/training/templates?workspace_id=1",
        expect.any(Object)
      );
    });

    const templateCard = await screen.findByText("LoRA 默认模板");
    await user.click(templateCard);

    await user.click(screen.getByRole("button", { name: "下一步" }));

    const datasetVersionInput = await screen.findByLabelText("数据集版本 ID");
    await user.clear(datasetVersionInput);
    await user.type(datasetVersionInput, "77");

    const formatInput = screen.getByLabelText("标准化格式 ID（可选）");
    await user.clear(formatInput);
    await user.type(formatInput, "88");

    await user.click(screen.getByRole("button", { name: "下一步" }));

    const gpuInput = await screen.findByLabelText("GPU 数量");
    await user.clear(gpuInput);
    await user.type(gpuInput, "2");

    const queueSelect = screen.getByLabelText("训练队列");
    await user.selectOptions(queueSelect, "high-memory");

    await user.click(screen.getByRole("button", { name: "保存草稿" }));
    await waitFor(() => {
      expect(screen.getByText(/草稿已保存/)).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "预校验配置" }));
    await waitFor(() => {
      expect(screen.getByText(/配置校验通过/)).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "下一步" }));

    await userEvent.click(screen.getByRole("button", { name: "发起训练" }));
    await waitFor(() => {
      expect(screen.getByText(/训练任务已创建/)).toBeInTheDocument();
    });

    const lastJobHeading = screen.getByText("最新训练任务");
    const lastJobSection = lastJobHeading.closest("section");
    expect(lastJobSection).not.toBeNull();
    const scoped = within(lastJobSection as HTMLElement);
    expect(scoped.getByText("任务 ID").nextElementSibling).toHaveTextContent("301");
    expect(scoped.getByText("训练队列").nextElementSibling).toHaveTextContent("high-memory");
    expect(scoped.getByText("GPU 数量").nextElementSibling).toHaveTextContent("2");
  });
});
