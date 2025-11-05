import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { EvaluationSuitePage } from "./EvaluationSuitePage";

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

describe("EvaluationSuitePage", () => {
  let queryClient: QueryClient;
  const urlMap: Record<string, Response | (() => Response)> = {};

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
    Object.keys(urlMap).forEach((key) => delete urlMap[key]);
  });

  afterEach(() => {
    queryClient.clear();
    vi.restoreAllMocks();
  });

  function renderPage() {
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <EvaluationSuitePage />
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  test("展示评估模板、创建任务并导出结果", async () => {
    const now = new Date().toISOString();
    let jobRefreshCount = 0;

    vi.spyOn(global, "fetch").mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = resolveRequestUrl(input);
      const method = init?.method ?? "GET";

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
            projects: [
              {
                id: 10,
                name: "Project X",
                description: null,
                status: "active",
                created_at: now,
                updated_at: now
              }
            ]
          }
        ]);
      }

      if (url.includes("/api/v1/evaluations/templates") && method === "GET") {
        return mockJsonResponse([
          {
            id: 101,
            key: "qa-default",
            name: "问答模板",
            description: "QA",
            task_type: "question_answering",
            metrics: ["bleu"],
            config: {},
            is_builtin: true,
            workspace_id: null,
            created_at: now,
            updated_at: now
          }
        ]);
      }

      if (url.includes("/api/v1/evaluations/jobs") && method === "GET") {
        jobRefreshCount += 1;
        if (jobRefreshCount > 1) {
          return mockJsonResponse([
            {
              id: 301,
              workspace_id: 1,
              project_id: 10,
              training_run_id: 501,
              evaluation_template_id: 101,
              dataset_version_id: 201,
              dataset_path: "1/general/evaluations/301/input/custom.jsonl",
              artifact_path: "1/general/evaluations/301",
              report_path: "1/general/evaluations/301/report.md",
              status: "completed",
              metrics: {
                example_count: 2,
                bleu: 0.45,
                rouge_l: 0.42,
                thresholds: {
                  bleu: { threshold: 0.3, triggered: false }
                },
                baseline: { bleu: 0.40 },
                delta: { bleu: 0.05 }
              },
              error_message: null,
              created_by: 1,
              created_at: now,
              updated_at: now,
              started_at: now,
              finished_at: now,
              trigger_mode: "automatic"
            }
          ]);
        }

        return mockJsonResponse([]);
      }

      if (url.includes("/api/v1/datasets?") && method === "GET") {
        return mockJsonResponse([
          {
            id: 200,
            workspace_id: 1,
            name: "Eval Dataset",
            description: null,
            source_type: "upload",
            source_uri: null,
            storage_path: "1/datasets/200/data.jsonl",
            data_type: "jsonl",
            mime_type: "application/json",
            file_size_bytes: 20,
            checksum_sha256: null,
            tags: [],
            notes: null,
            status: "active",
            reference_dataset_id: null,
            created_by: 1,
            created_at: now,
            updated_at: now
          }
        ]);
      }

      if (url.includes("/api/v1/datasets/200/versions") && method === "GET") {
        return mockJsonResponse([
          {
            id: 201,
            dataset_id: 200,
            version: 1,
            status: "completed",
            location_uri: "1/datasets/200/v1",
            stats_json: null,
            quality_summary_path: null,
            quality_report_manifest: null,
            created_by: 1,
            created_at: now,
            updated_at: now
          }
        ]);
      }

      if (url.includes("/api/v1/training/monitor/runs") && method === "GET") {
        return mockJsonResponse([
          {
            run_id: 501,
            job_id: 401,
            workspace_id: 1,
            status: "completed",
            started_at: now,
            metrics: {},
            alerts: []
          }
        ]);
      }

      if (url.endsWith("/api/v1/evaluations/jobs") && method === "POST") {
        return mockJsonResponse(
          {
            id: 301,
            workspace_id: 1,
            project_id: 10,
            training_run_id: 501,
            evaluation_template_id: 101,
            dataset_version_id: 201,
            dataset_path: "1/general/evaluations/301/input/custom.jsonl",
              artifact_path: "1/general/evaluations/301",
              report_path: null,
              status: "pending",
              metrics: null,
              error_message: null,
              created_by: 1,
              created_at: now,
              updated_at: now,
              started_at: null,
              finished_at: null,
              trigger_mode: "manual"
          },
          true
        );
      }

      if (url.includes("/api/v1/evaluations/jobs/") && url.endsWith("export?format=markdown")) {
        return mockJsonResponse(new Blob(["# report"], { type: "text/markdown" }), true);
      }

      if (url.includes("/api/v1/evaluations/jobs/") && url.endsWith("export?format=json")) {
        return mockJsonResponse(new Blob(['{"bleu":0.45}'], { type: "application/json" }), true);
      }

      return mockJsonResponse({}, true);
    });

    const createObjectURLSpy = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:url");
    const revokeSpy = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const clickSpy = vi.spyOn(document, "createElement");

    renderPage();

    const navigation = await screen.findByLabelText("评估模块导航");
    expect(navigation).toBeInTheDocument();

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith("http://localhost:8000/api/v1/workspaces", expect.anything());
    });

    await screen.findByText(/标准化评估套件/);
    await screen.findByText(/问答模板/);

    const createButton = await screen.findByRole("button", { name: "创建评估任务" });
    await userEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByText(/评估任务创建成功/)).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText(/任务 #301/)).toBeInTheDocument();
      expect(screen.getByText(/BLEU:/)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "查看报告" })).toBeInTheDocument();
    });

    const downloadReport = await screen.findByRole("button", { name: "下载报告 (MD)" });
    await userEvent.click(downloadReport);
    expect(createObjectURLSpy).toHaveBeenCalled();
    expect(revokeSpy).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();

    const downloadJson = await screen.findByRole("button", { name: "下载指标 (JSON)" });
    await userEvent.click(downloadJson);
  });
});
