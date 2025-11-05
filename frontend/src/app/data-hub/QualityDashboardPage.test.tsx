import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { QualityDashboardPage } from "./QualityDashboardPage";

function mockJsonResponse<T>(data: T, ok = true): Response {
  return {
    ok,
    json: async () => data
  } as unknown as Response;
}

function mockBlobResponse(content: string, contentType = "application/json"): Response {
  return {
    ok: true,
    blob: async () => new Blob([content], { type: contentType })
  } as unknown as Response;
}

describe("QualityDashboardPage", () => {
  let queryClient: QueryClient;
  const originalCreateObjectURL = global.URL.createObjectURL;
  const originalRevokeObjectURL = global.URL.revokeObjectURL;

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
    global.URL.createObjectURL = vi.fn(() => "blob:mock");
    global.URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    queryClient.clear();
    global.URL.createObjectURL = originalCreateObjectURL;
    global.URL.revokeObjectURL = originalRevokeObjectURL;
  });

  function renderPage() {
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <QualityDashboardPage />
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  test("展示质量指标并支持重新评估与导出", async () => {
    const now = new Date().toISOString();
    const fetchMock = vi.spyOn(global, "fetch");
    fetchMock.mockResolvedValueOnce(
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
    );
    fetchMock.mockResolvedValueOnce(
      mockJsonResponse([
        {
          id: 10,
          workspace_id: 1,
          name: "Dataset One",
          description: null,
          source_type: "upload",
          source_uri: null,
          storage_path: "workspaces/1/datasets/10/source.jsonl",
          data_type: "jsonl",
          mime_type: "application/json",
          file_size_bytes: 100,
          checksum_sha256: "abc",
          tags: [],
          notes: null,
          status: "active",
          reference_dataset_id: null,
          created_by: 1,
          created_at: now,
          updated_at: now
        }
      ])
    );
    fetchMock.mockResolvedValueOnce(
      mockJsonResponse([
        {
          id: 100,
          dataset_id: 10,
          version: 1,
          status: "completed",
          location_uri: "workspaces/1/datasets/10/v1",
          stats_json: null,
          created_by: 1,
          created_at: now,
          updated_at: now
        }
      ])
    );
    fetchMock.mockResolvedValueOnce(
      mockJsonResponse({
        dataset_id: 10,
        dataset_version_id: 100,
        status: "completed",
        stats: {
          total_rows: 10,
          duplicate_rows: 2,
          quality_score: 0.8,
          average_length: 12,
          anomaly_count: 1,
          top_anomalies: [
            {
              index: 0,
              reasons: ["duplicate"],
              record: { id: 1, text: "重复样本" }
            }
          ]
        },
        report_manifest: {
          json: "workspaces/1/datasets/10/v1/quality/summary.json",
          csv: "workspaces/1/datasets/10/v1/quality/anomalies.csv"
        }
      })
    );

    renderPage();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/workspaces",
        expect.objectContaining({ method: "GET" })
      );
    });

    expect(await screen.findByText("总样本")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("0.8")).toBeInTheDocument();
    expect(screen.getByText("重复样本")).toBeInTheDocument();

    fetchMock.mockResolvedValueOnce(
      mockJsonResponse({
        id: 200,
        dataset_version_id: 100,
        status: "pending",
        logs_path: null,
        summary_path: null,
        export_manifest: null,
        error_message: null,
        created_at: now,
        updated_at: now,
        started_at: null,
        finished_at: null
      })
    );

    fetchMock.mockResolvedValueOnce(
      mockJsonResponse({
        dataset_id: 10,
        dataset_version_id: 100,
        status: "running",
        stats: {
          total_rows: 10,
          duplicate_rows: 2,
          quality_score: 0.8,
          average_length: 12,
          anomaly_count: 1,
          top_anomalies: []
        },
        report_manifest: {
          json: "workspaces/1/datasets/10/v1/quality/summary.json",
          csv: "workspaces/1/datasets/10/v1/quality/anomalies.csv"
        }
      })
    );

    await userEvent.click(screen.getByRole("button", { name: "重新评估" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/datasets/10/versions/100/quality/run",
        expect.objectContaining({ method: "POST" })
      );
    });

    fetchMock.mockResolvedValueOnce(mockBlobResponse("{}"));

    await userEvent.click(screen.getByRole("button", { name: "下载 JSON 报告" }));

    await waitFor(() => {
      expect(global.URL.createObjectURL).toHaveBeenCalled();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/datasets/10/versions/100/quality/export?format=json",
      expect.objectContaining({ method: "GET" })
    );
  });
});

