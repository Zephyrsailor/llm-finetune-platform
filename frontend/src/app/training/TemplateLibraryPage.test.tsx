import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { TemplateLibraryPage } from "./TemplateLibraryPage";

const now = new Date().toISOString();

function mockJsonResponse<T>(data: T, ok = true): Response {
  return {
    ok,
    json: async () => data
  } as unknown as Response;
}

describe("TemplateLibraryPage", () => {
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
          <TemplateLibraryPage />
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  test("创建模板并触发训练任务", async () => {
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
          num_epochs: 3,
          per_device_train_batch_size: 4
        },
        is_builtin: true,
        created_by: null,
        created_at: now,
        updated_at: now
      }
    ];

    const fetchMock = vi.spyOn(global, "fetch");
    fetchMock
      .mockResolvedValueOnce(
        mockJsonResponse([
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
        ])
      )
      .mockResolvedValueOnce(mockJsonResponse(builtinTemplates));

    renderPage();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/training/templates?workspace_id=1",
        expect.any(Object)
      );
    });
    const builtinEntries = await screen.findAllByText("LoRA 默认模板");
    expect(builtinEntries.length).toBeGreaterThan(0);

    const createdTemplate = {
      id: 20,
      workspace_id: 1,
      name: "客服场景 LoRA",
      description: "针对客服对话的快速调参模板",
      base_model: "meta-llama/Llama-3-8b-instruct",
      adapter_type: "lora",
      params: {
        learning_rate: 0.0003,
        lora_rank: 12,
        num_epochs: 2,
        per_device_train_batch_size: 4
      },
      is_builtin: false,
      created_by: 2,
      created_at: now,
      updated_at: now
    };

    fetchMock
      .mockResolvedValueOnce(mockJsonResponse(createdTemplate))
      .mockResolvedValueOnce(mockJsonResponse([...builtinTemplates, createdTemplate]));

    const getNumericInput = (labelText: string) => {
      const labelNode = screen.getByText(labelText);
      const labelElement = labelNode.closest("label");
      if (!labelElement) {
        throw new Error(`未找到匹配的 label：${labelText}`);
      }
      const input = labelElement.querySelector("input");
      if (!input) {
        throw new Error(`label ${labelText} 内未找到输入框`);
      }
      return input as HTMLInputElement;
    };

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("模板名称"), "客服场景 LoRA");
    await user.clear(getNumericInput("Learning Rate"));
    await user.type(getNumericInput("Learning Rate"), "0.0003");
    await user.clear(getNumericInput("LoRA Rank"));
    await user.type(getNumericInput("LoRA Rank"), "12");
    await user.clear(getNumericInput("训练 Epoch"));
    await user.type(getNumericInput("训练 Epoch"), "2");
    await user.type(screen.getByLabelText("描述（可选）"), "针对客服对话的快速调参模板");
    await user.click(screen.getByRole("button", { name: "创建模板" }));

    await waitFor(() => {
      expect(screen.getByText("模板创建成功。")).toBeInTheDocument();
    });

    const createTemplateCall = fetchMock.mock.calls.find(([url]) =>
      url === "http://localhost:8000/api/v1/training/templates"
    );
    expect(createTemplateCall).toBeTruthy();
    expect(createTemplateCall?.[1]).toMatchObject({
      method: "POST",
      headers: expect.objectContaining({ Authorization: "Bearer token" })
    });
    expect(JSON.parse(createTemplateCall?.[1]?.body as string)).toEqual({
      workspace_id: 1,
      name: "客服场景 LoRA",
      base_model: "meta-llama/Llama-3-8b-instruct",
      adapter_type: "lora",
      description: "针对客服对话的快速调参模板",
      params: {
        learning_rate: 0.0003,
        lora_rank: 12,
        num_epochs: 2,
        per_device_train_batch_size: 4
      }
    });

    const jobResponse = {
      id: 301,
      workspace_id: 1,
      project_id: null,
      dataset_version_id: 77,
      dataset_format_version_id: 88,
      training_template_id: 20,
      base_model: "meta-llama/Llama-3-8b-instruct",
      adapter_type: "lora",
      status: "completed",
      params: {
        num_epochs: 2
      },
      notes: "自动调参测试",
      scheduled_by: 2,
      scheduled_at: now,
      started_at: now,
      finished_at: now,
      error_message: null,
      latest_run: {
        id: 401,
        job_id: 301,
        status: "completed",
        started_at: now,
        finished_at: now,
        metrics: { final_loss: 1.23 },
        artifact_uri: "/var/lib/llmft/training/1/301/artifacts",
        exit_code: 0
      }
    };

    fetchMock.mockResolvedValueOnce(mockJsonResponse(jobResponse));

    await user.selectOptions(screen.getByLabelText("训练模板"), "20");
    await user.type(screen.getByLabelText("数据集版本 ID"), "77");
    await user.type(screen.getByLabelText("标准化格式 ID（可选）"), "88");
    await user.type(screen.getByLabelText("备注（可选）"), "自动调参测试");
    const overrideInput = screen.getByLabelText("覆盖参数（JSON，可选）");
    fireEvent.change(overrideInput, { target: { value: '{"num_epochs": 2}' } });
    await user.click(screen.getByRole("button", { name: "创建训练任务" }));

    await waitFor(() => {
      expect(screen.getByText(/训练任务已创建/)).toBeInTheDocument();
    });

    const createJobCall = fetchMock.mock.calls.find(([url]) =>
      url === "http://localhost:8000/api/v1/training/jobs"
    );
    expect(createJobCall).toBeTruthy();
    expect(JSON.parse(createJobCall?.[1]?.body as string)).toEqual({
      workspace_id: 1,
      training_template_id: 20,
      dataset_version_id: 77,
      dataset_format_version_id: 88,
      params: { num_epochs: 2 },
      notes: "自动调参测试"
    });

    expect(screen.getByText("任务 ID：301")).toBeInTheDocument();
  });
});
