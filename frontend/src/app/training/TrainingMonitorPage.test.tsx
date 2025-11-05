import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { TrainingMonitorPage } from "./TrainingMonitorPage";

const now = new Date().toISOString();

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

describe("TrainingMonitorPage", () => {
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
          <TrainingMonitorPage />
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  test("展示训练运行与告警列表", async () => {
    const workspaceList = [
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

    const later = new Date(Date.now() + 1_000).toISOString();
    const runs = [
      {
        run_id: 201,
        job_id: 301,
        workspace_id: 1,
        project_id: null,
        status: "completed",
        started_at: now,
        finished_at: now,
        latest_metrics: [
          { run_id: 201, metric: "loss", value: 0.42, recorded_at: now }
        ],
        alerts: [
          {
            id: 401,
            rule_id: 501,
            run_id: 201,
            value: 0.7,
            status: "triggered",
            triggered_at: now,
            acknowledged_at: null,
            resolved_at: null,
            notes: null
          }
        ],
        latest_evaluation: {
          job_id: 901,
          metrics: {
            bleu: 0.28,
            rouge_l: 0.32,
            thresholds: {
              bleu: { threshold: 0.3, triggered: true },
              rouge_l: { threshold: 0.3, triggered: false }
            },
            baseline: { bleu: 0.35 },
            delta: { bleu: -0.07 }
          },
          updated_at: now
        }
      }
    ];

    const metricSeries = [
      { run_id: 201, metric: "loss", value: 0.9, recorded_at: now },
      { run_id: 201, metric: "loss", value: 0.42, recorded_at: later }
    ];

    const alertRules = [
      {
        id: 501,
        workspace_id: 1,
        name: "loss-high",
        metric: "loss",
        operator: "gt",
        threshold: 0.5,
        cooldown_seconds: 60,
        is_active: true,
        channels: null,
        created_at: now,
        updated_at: now
      }
    ];

    const alerts = [
      {
        id: 401,
        rule_id: 501,
        run_id: 201,
        value: 0.7,
        status: "triggered",
        triggered_at: now,
        acknowledged_at: null,
        resolved_at: null,
        notes: null
      }
    ];

    const fetchMock = vi.spyOn(global, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
      const url = resolveRequestUrl(input);
      if (url.endsWith("/api/v1/workspaces")) {
        return mockJsonResponse(workspaceList);
      }
      if (url.includes("/api/v1/training/monitor/runs?")) {
        return mockJsonResponse(runs);
      }
      if (url.includes("/api/v1/training/monitor/runs/201/metrics")) {
        return mockJsonResponse(metricSeries);
      }
      if (url.includes("/api/v1/training/monitor/alert-rules?")) {
        return mockJsonResponse(alertRules);
      }
      if (url.includes("/api/v1/training/monitor/alerts?")) {
        return mockJsonResponse(alerts);
      }
      if (url.includes("/api/v1/training/monitor/alerts/401/status")) {
        return mockJsonResponse(alerts[0]);
      }
      return mockJsonResponse([]);
    });

    renderPage();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/v1/workspaces", expect.anything());
    });

    const runItem = await screen.findByText(/运行 #201/);
    await userEvent.click(runItem);
    const runCardElement = runItem.closest("li");
    if (!runCardElement) {
      throw new Error("未找到运行卡片元素");
    }

    await waitFor(() => {
      expect(screen.getByText(/告警 #401/)).toBeInTheDocument();
      expect(within(runCardElement).getByText(/Loss: 0.420/)).toBeInTheDocument();
      expect(within(runCardElement).getByText(/BLEU:/)).toBeInTheDocument();
      expect(within(runCardElement).getByText(/检测到以下指标触发阈值/)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "查看评估报告" })).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "标记处理中" }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/training/monitor/alerts/401/status",
        expect.any(Object)
      );
    });
  });
});
