import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ModelRegistryPage } from "../ModelRegistryPage";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";

function buildResponse(payload: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init
  });
}

beforeEach(() => {
  localStorage.setItem("access_token", "test-token");
});

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

test("renders model registry and updates status", async () => {
  const fetchMock = vi.spyOn(global, "fetch").mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();

    if (url === `${API_BASE}/v1/workspaces` && (!init || init.method === "GET")) {
      return buildResponse([
        {
          id: 1,
          name: "Workspace A",
          description: "",
          plan: null,
          status: "active",
          created_at: "2025-10-30T10:00:00Z",
          updated_at: "2025-10-30T10:00:00Z",
          members: [],
          projects: [
            {
              id: 10,
              name: "Alpha",
              description: "",
              status: "active",
              created_at: "2025-10-30T10:00:00Z",
              updated_at: "2025-10-30T10:00:00Z"
            }
          ]
        }
      ]);
    }

    if (url.startsWith(`${API_BASE}/v1/models`) && (!init || init.method === "GET")) {
      return buildResponse([
        {
          id: 101,
          workspace_id: 1,
          project_id: 10,
          name: "chat-model",
          description: "对话模型",
          base_model: "llama-3-8b",
          tags: ["chat"],
          created_at: "2025-10-30T10:10:00Z",
          updated_at: "2025-10-30T10:20:00Z",
          versions: [
            {
              id: 1001,
              model_id: 101,
              version: 1,
              status: "candidate",
              artifact_path: "models/workspace-1/project-10/model-101/v1",
              metadata: {},
              training_run_id: null,
              evaluation_job_id: 501,
              evaluation_metrics: { thresholds: { overall: { triggered: false } } },
              evaluation_report_path: "reports/501.md",
              deployment_target: null,
              notes: "第一版",
              created_by: 1,
              updated_by: 1,
              promoted_by: null,
              promoted_at: null,
              created_at: "2025-10-30T10:15:00Z",
              updated_at: "2025-10-30T10:15:00Z"
            }
          ]
        }
      ]);
    }

    if (url === `${API_BASE}/v1/models/101/versions/1001` && init?.method === "PATCH") {
      return buildResponse({
        id: 1001,
        model_id: 101,
        version: 1,
        status: "production",
        artifact_path: "models/workspace-1/project-10/model-101/v1",
        metadata: {},
        training_run_id: null,
        evaluation_job_id: 501,
        evaluation_metrics: { thresholds: { overall: { triggered: false } } },
        evaluation_report_path: "reports/501.md",
        deployment_target: null,
        notes: "第一版",
        created_by: 1,
        updated_by: 1,
        promoted_by: 1,
        promoted_at: "2025-10-30T11:00:00Z",
        created_at: "2025-10-30T10:15:00Z",
        updated_at: "2025-10-30T11:00:00Z"
      });
    }

    if (url.startsWith(`${API_BASE}/v1/models/101/versions/1001:export`) && init?.method === "POST") {
      return buildResponse({ path: "models/workspace-1/project-10/model-101/exports/test.json", format: "json" });
    }

    return buildResponse({}, { status: 404 });
  });

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      }
    }
  });

  render(
    <QueryClientProvider client={queryClient}>
      <ModelRegistryPage />
    </QueryClientProvider>
  );

  expect(await screen.findByText("模型注册与版本管理")).toBeInTheDocument();
  expect(await screen.findByText("chat-model")).toBeInTheDocument();
  await screen.findByText("版本 v1");

  await userEvent.click(screen.getByRole("button", { name: "标记为生产" }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/v1/models/101/versions/1001`,
      expect.objectContaining({
        method: "PATCH"
      })
    );
  });

  await userEvent.click(screen.getByRole("button", { name: "导出 JSON" }));
  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/v1/models/101/versions/1001:export?format=json`,
      expect.objectContaining({
        method: "POST"
      })
    );
  });
});
