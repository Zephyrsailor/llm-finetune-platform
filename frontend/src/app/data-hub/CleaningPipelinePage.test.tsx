import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { CleaningPipelinePage } from "./CleaningPipelinePage";

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

describe("CleaningPipelinePage", () => {
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
          <CleaningPipelinePage />
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  test("创建模板并绑定到数据集", async () => {
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
    fetchMock.mockResolvedValueOnce(mockJsonResponse([]));
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

    renderPage();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/workspaces",
        expect.objectContaining({ method: "GET" })
      );
    });

    await userEvent.type(screen.getByLabelText("模板名称"), "默认模板");
    await userEvent.type(screen.getByLabelText("模板说明"), "测试用模板");
    await userEvent.type(screen.getByLabelText("字段/字段列表"), "id");
    await userEvent.click(screen.getByRole("button", { name: "添加步骤" }));

    const templatePayload = {
      id: 20,
      workspace_id: 1,
      name: "默认模板",
      description: "测试用模板",
      is_active: true,
      version: 1,
      steps: [{ type: "deduplicate", fields: ["id"] }],
      created_at: now,
      updated_at: now
    };

    fetchMock.mockResolvedValueOnce(mockJsonResponse(templatePayload));
    fetchMock.mockResolvedValueOnce(mockJsonResponse([templatePayload]));

    await userEvent.click(screen.getByRole("button", { name: "创建清洗模板" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/datasets/cleaning/templates",
        expect.objectContaining({ method: "POST" })
      );
    });

    await waitFor(() => {
      expect(screen.getByText("模板创建成功")).toBeInTheDocument();
    });

    const datasetSelect = screen.getByLabelText("数据集");

    fetchMock.mockResolvedValueOnce(mockJsonResponse(null));
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

    await userEvent.selectOptions(datasetSelect, "10");

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/datasets/10/cleaning/assignment",
        expect.objectContaining({ method: "GET" })
      );
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/datasets/10/versions",
        expect.objectContaining({ method: "GET" })
      );
    });

    fetchMock.mockResolvedValueOnce(mockJsonResponse({
      dataset_id: 10,
      template_id: 20,
      enabled: true,
      assigned_at: now
    }));
    fetchMock.mockResolvedValueOnce(mockJsonResponse({
      dataset_id: 10,
      template_id: 20,
      enabled: true,
      assigned_at: now
    }));

    await userEvent.selectOptions(screen.getByLabelText("绑定模板"), "20");

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/datasets/10/cleaning/assignment",
        expect.objectContaining({ method: "POST" })
      );
    });

    await waitFor(() => {
      expect(screen.getByText("模板绑定已更新。")).toBeInTheDocument();
    });
  });

  test("查看清洗统计并导出文件", async () => {
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
          id: 30,
          workspace_id: 1,
          name: "模板A",
          description: null,
          is_active: true,
          version: 1,
          steps: [],
          created_at: now,
          updated_at: now
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

    renderPage();

    const datasetSelect = await screen.findByLabelText("数据集");

    fetchMock.mockResolvedValueOnce(mockJsonResponse({
      dataset_id: 10,
      template_id: 30,
      enabled: true,
      assigned_at: now
    }));
    fetchMock.mockResolvedValueOnce(
      mockJsonResponse([
        {
          id: 100,
          dataset_id: 10,
          version: 2,
          status: "completed",
          location_uri: "workspaces/1/datasets/10/v2",
          stats_json: null,
          created_by: 1,
          created_at: now,
          updated_at: now
        }
      ])
    );

    await userEvent.selectOptions(datasetSelect, "10");

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/datasets/10/versions",
        expect.objectContaining({ method: "GET" })
      );
    });

    const versionSelect = await screen.findByLabelText("数据集版本");
    await userEvent.selectOptions(versionSelect, "100");

    fetchMock.mockResolvedValueOnce(
      mockJsonResponse({
        dataset_id: 10,
        dataset_version_id: 100,
        status: "completed",
        stats: {
          total_rows: 10,
          rows_after_cleaning: 8
        },
        template: { id: 30 },
        export_manifest: {
          jsonl: "workspaces/1/datasets/10/v2/clean/cleaned.jsonl",
          csv: "workspaces/1/datasets/10/v2/clean/cleaned.csv"
        }
      })
    );

    await userEvent.click(screen.getByRole("button", { name: "加载清洗统计" }));

    await waitFor(() => {
      expect(screen.getByText("total_rows")).toBeInTheDocument();
    });

    fetchMock.mockResolvedValueOnce(mockBlobResponse("{}"));

    await userEvent.click(screen.getByRole("button", { name: "下载 JSONL" }));

    await waitFor(() => {
      expect(screen.getByText("已开始下载 jsonl 文件。")).toBeInTheDocument();
    });
  });
});

