import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ModelDeploymentPage } from "../DeploymentPage";

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

test("deploys model version and displays deployment card", async () => {
  let hasCreatedDeployment = false;

  const deploymentSummary = {
    id: 201,
    workspace_id: 1,
    project_id: null,
    model_version_id: 1001,
    environment: "production",
    status: "active",
    endpoint_url: "http://localhost:9000/production/models/1001",
    access_token: "token-abc",
    config: { replicas: 1 },
    metrics: { latency_p95_ms: 110, throughput_rps: 40 },
    traffic_percent: 100,
    notes: "首次部署",
    created_at: "2025-10-31T10:00:00Z",
    updated_at: "2025-10-31T10:05:00Z",
    events: [
      {
        id: 1,
        deployment_id: 201,
        event_type: "deployment.completed",
        level: "INFO",
        message: "部署成功",
        payload: {},
        created_at: "2025-10-31T10:05:00Z"
      }
    ]
  };

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
          projects: []
        }
      ]);
    }

    if (url.startsWith(`${API_BASE}/v1/models`) && (!init || init.method === "GET")) {
      return buildResponse([
        {
          id: 101,
          workspace_id: 1,
          project_id: null,
          name: "chat-model",
          description: "",
          base_model: "llama-3-8b",
          tags: ["deploy"],
          created_at: "2025-10-30T10:10:00Z",
          updated_at: "2025-10-30T10:20:00Z",
          versions: [
            {
              id: 1001,
              model_id: 101,
              version: 1,
              status: "production",
              artifact_path: "models/workspace-1/model-101/v1",
              metadata: {},
              training_run_id: null,
              evaluation_job_id: 501,
              evaluation_metrics: {},
              evaluation_report_path: "reports/501.md",
              deployment_target: "infra-a",
              notes: "",
              created_by: 1,
              updated_by: 1,
              promoted_by: 1,
              promoted_at: "2025-10-30T10:30:00Z",
              created_at: "2025-10-30T10:15:00Z",
              updated_at: "2025-10-30T10:30:00Z"
            }
          ]
        }
      ]);
    }

    if (url.startsWith(`${API_BASE}/v1/deployments`) && (!init || init.method === "GET")) {
      return buildResponse({ deployments: hasCreatedDeployment ? [deploymentSummary] : [] });
    }

    if (url === `${API_BASE}/v1/deployments` && init?.method === "POST") {
      hasCreatedDeployment = true;
      return buildResponse(deploymentSummary);
    }

    if (url.endsWith("/traffic") && init?.method === "POST") {
      return buildResponse(deploymentSummary);
    }

    if (url.endsWith("/rollback") && init?.method === "POST") {
      return buildResponse({ deployment_id: deploymentSummary.id });
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
      <ModelDeploymentPage />
    </QueryClientProvider>
  );

  expect(await screen.findByText("vLLM 部署流水线")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "立即部署" }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/v1/deployments`,
      expect.objectContaining({ method: "POST" })
    );
  });

  await waitFor(() => expect(screen.getByText("部署 #201")).toBeInTheDocument());
});
