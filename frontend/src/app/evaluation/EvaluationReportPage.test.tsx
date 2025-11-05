import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { EvaluationReportPage } from "./EvaluationReportPage";

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

describe("EvaluationReportPage", () => {
  let queryClient: QueryClient;
  let clipboardSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false
        }
      }
    });
    clipboardSpy = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText: clipboardSpy }
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    queryClient.clear();
  });

  test("渲染报告并生成分享链接", async () => {
    const now = new Date().toISOString();
    const reportPayload = {
      job: {
        id: 301,
        trigger_mode: "manual",
        training_run_id: 201
      },
      metrics: {
        bleu: 0.45,
        thresholds: {
          bleu: { threshold: 0.3, triggered: false }
        }
      },
      cases: {
        improved: [{ reference: "hello", prediction: "hello", score: 1 }],
        regressed: []
      },
      artifacts: {
        markdown: "/api/v1/evaluations/jobs/301/export?format=markdown",
        json: "/api/v1/evaluations/jobs/301/export?format=json",
        pdf: "/api/v1/evaluations/jobs/301/export?format=pdf"
      },
      training: {
        run: {
          id: 201,
          status: "completed",
          started_at: now,
          finished_at: now
        },
        job: {
          id: 101,
          base_model: "llama",
          adapter_type: "lora"
        },
        project: {
          id: 55,
          name: "商用机器人"
        }
      },
      dataset: {
        dataset: {
          id: 88,
          name: "EvalSet"
        },
        dataset_version: {
          id: 99,
          version: 3
        },
        location_uri: "datasets/88/v3"
      },
      report_markdown: "",
      report_html: "<p>Summary</p>"
    };

    const sharePayload = {
      token: "token-value",
      share_path: "/api/v1/evaluations/reports/shared/token-value",
      expires_at: now
    };

    const fetchMock = vi.spyOn(global, "fetch").mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = resolveRequestUrl(input);
      if (url.endsWith("/api/v1/evaluations/reports/301") && (!init || init.method === "GET")) {
        return mockJsonResponse(reportPayload);
      }
      if (url.endsWith("/api/v1/evaluations/jobs/301/feedback") && (!init || init.method === "GET")) {
        return mockJsonResponse([]);
      }
      if (url.endsWith("/api/v1/evaluations/reports/301/share") && init?.method === "POST") {
        return mockJsonResponse(sharePayload);
      }
      return mockJsonResponse({}, false);
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/evaluation/reports/301"]}>
          <Routes>
            <Route path="/evaluation/reports/:jobId" element={<EvaluationReportPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/evaluations/reports/301",
        expect.anything()
      );
    });

    await screen.findByText(/核心指标/);
    expect(screen.getByText(/BLEU/)).toBeInTheDocument();
    expect(screen.getByText(/运行编号/)).toBeInTheDocument();
    expect(screen.getByText(/数据集：EvalSet/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "生成分享链接" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/evaluations/reports/301/share",
        expect.anything()
      );
      expect(screen.getByText(/分享链接已生成/)).toBeInTheDocument();
    });

    expect(clipboardSpy).toHaveBeenCalledWith(`${window.location.origin}${sharePayload.share_path}`);
  });
});
