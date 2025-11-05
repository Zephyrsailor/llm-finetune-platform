import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { TrainingExperimentsPage } from "./TrainingExperimentsPage";

function mockJsonResponse<T>(data: T, ok = true): Response {
  return {
    ok,
    json: async () => data
  } as unknown as Response;
}

function resolveRequestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") {
    return input;
  }
  if (input instanceof URL) {
    return input.toString();
  }
  return (input as Request).url;
}

describe("TrainingExperimentsPage", () => {
  let queryClient: QueryClient;

  const now = new Date().toISOString();

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
          <TrainingExperimentsPage />
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  test("展示实验列表、支持详情对比与导出", async () => {
    const workspaces = [
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
    ];

    const experiments = [
      {
        run_id: 201,
        job_id: 301,
        workspace_id: 1,
        status: "completed",
        started_at: now,
        finished_at: now,
        base_model: "meta-llama/Llama-3-8b",
        adapter_type: "lora",
        dataset: { dataset_name: "dataset-a", version: 1 },
        metrics: { final_loss: 0.42 },
        resource: { duration_seconds: 1200, cost_estimate_usd: 2.4 }
      },
      {
        run_id: 202,
        job_id: 302,
        workspace_id: 1,
        status: "completed",
        started_at: now,
        finished_at: now,
        base_model: "meta-llama/Llama-3-8b",
        adapter_type: "lora",
        dataset: { dataset_name: "dataset-b", version: 2 },
        metrics: { final_loss: 0.35 },
        resource: { duration_seconds: 900, cost_estimate_usd: 1.8 }
      }
    ];

    const detail = {
      run_id: 201,
      job_id: 301,
      workspace_id: 1,
      status: "completed",
      started_at: now,
      finished_at: now,
      base_model: "meta-llama/Llama-3-8b",
      adapter_type: "lora",
      dataset: { dataset_name: "dataset-a", version: 1 },
      metrics: { final_loss: 0.42 },
      resource: { duration_seconds: 1200, cost_estimate_usd: 2.4 },
      artifact_uri: "/var/lib/llmft/training/1/301/artifacts",
      exit_code: 0,
      metadata: {
        dataset: { dataset_name: "dataset-a", version: 1 },
        metrics: { final: { final_loss: 0.42, accuracy: 0.91 } },
        snapshots: [{ snapshot_id: 501, trigger_type: "scheduled" }],
        alerts: [{ alert_id: 701, status: "triggered" }]
      }
    };

    const comparison = {
      run_a: experiments[0],
      run_b: experiments[1],
      diff: {
        parameters: [{ key: "dataset.dataset_name", left: "dataset-a", right: "dataset-b" }],
        final_metrics: [{ key: "final_loss", left: 0.42, right: 0.35, delta: -0.07 }],
        resource: [],
        dataset: [{ key: "version", left: 1, right: 2 }]
      },
      snapshots: { run_a: [{ snapshot_id: 501 }], run_b: [{ snapshot_id: 502 }] },
      alerts: { run_a: [{ alert_id: 701, status: "triggered" }], run_b: [] }
    };

    const exportResult = {
      workspace_id: 1,
      format: "json",
      path: "/storage/training/1/experiments/exports/experiments.json",
      generated_at: now,
      size_bytes: 1024
    };

    const fetchMock = vi.spyOn(global, "fetch").mockImplementation(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = resolveRequestUrl(input);
        const method = init?.method ?? "GET";

        if (url === "http://localhost:8000/api/v1/workspaces" && method === "GET") {
          return mockJsonResponse(workspaces);
        }
        if (url === "http://localhost:8000/api/v1/training/experiments?workspace_id=1" && method === "GET") {
          return mockJsonResponse(experiments);
        }
        if (url === "http://localhost:8000/api/v1/training/experiments/201" && method === "GET") {
          return mockJsonResponse(detail);
        }
        if (url === "http://localhost:8000/api/v1/training/experiments/compare" && method === "POST") {
          return mockJsonResponse(comparison);
        }
        if (url === "http://localhost:8000/api/v1/training/experiments/export" && method === "POST") {
          return mockJsonResponse(exportResult);
        }

        return mockJsonResponse([]);
      }
    );

    renderPage();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/v1/workspaces", expect.anything());
    });

    await screen.findByText(/运行 #201/);
    expect(screen.getByText(/dataset-a/)).toBeInTheDocument();

    const detailButtons = await screen.findAllByRole("button", { name: "查看详情" });
    await userEvent.click(detailButtons[0]);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/training/experiments/201",
        expect.anything()
      );
    });
    await screen.findByText(/Artefact：\/var\/lib\/llmft\/training/);
    await screen.findByText(/alert_id/);

    const checkboxes = await screen.findAllByRole("checkbox");
    await userEvent.click(checkboxes[0]);
    await userEvent.click(checkboxes[1]);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/training/experiments/compare",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ run_a_id: 201, run_b_id: 202 })
        })
      );
    });
    await screen.findByText(/final_loss/);
    await screen.findByText(/snapshot_id/);

    const exportButton = screen.getByRole("button", { name: "导出报告" });
    await userEvent.click(exportButton);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/training/experiments/export",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ workspace_id: 1, run_ids: [201, 202], format: "json" })
        })
      );
    });
    await screen.findByText(/导出成功/);
  });
});
