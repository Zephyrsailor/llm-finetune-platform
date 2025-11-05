import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { FormatStandardPage } from "./FormatStandardPage";

function mockJsonResponse<T>(data: T, ok = true): Response {
  return {
    ok,
    json: async () => data
  } as unknown as Response;
}

describe("FormatStandardPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("触发格式转换并回滚为指定版本", async () => {
    const now = new Date().toISOString();
    localStorage.setItem("access_token", "token");

    const workspacePayload = [
      {
        id: 1,
        name: "Demo Workspace",
        description: null,
        plan: "standard",
        status: "active",
        created_at: now,
        updated_at: now,
        members: [],
        projects: []
      }
    ];

    const datasetPayload = [
      {
        id: 10,
        workspace_id: 1,
        name: "customer-support",
        description: null,
        source_type: "upload",
        storage_path: "workspaces/1/datasets/10/v0/raw/data.jsonl",
        data_type: "jsonl",
        mime_type: "application/json",
        file_size_bytes: 512,
        checksum_sha256: "abc",
        tags: ["support"],
        notes: null,
        status: "active",
        created_by: 1,
        created_at: now,
        updated_at: now
      }
    ];

    const versionPayload = [
      {
        id: 21,
        dataset_id: 10,
        version: 1,
        status: "completed",
        location_uri: "workspaces/1/datasets/10/v1",
        stats_json: { quality: { score: 0.98 } },
        created_by: 1,
        created_at: now,
        updated_at: now
      }
    ];

    const initialFormats: unknown[] = [];

    const runResult = [
      {
        id: 100,
        dataset_version_id: 21,
        format: "jsonl",
        status: "completed",
        path: "workspaces/1/datasets/10/v1/standard/jsonl/data.jsonl",
        logs_path: "workspaces/1/datasets/10/v1/logs/format-100.log",
        checksum_sha256: "checksum-jsonl",
        file_size_bytes: 1536,
        is_active: true,
        created_at: now,
        updated_at: now,
        started_at: now,
        finished_at: now,
        error_message: null
      },
      {
        id: 101,
        dataset_version_id: 21,
        format: "sft",
        status: "completed",
        path: "workspaces/1/datasets/10/v1/standard/sft/sft.jsonl",
        logs_path: "workspaces/1/datasets/10/v1/logs/format-101.log",
        checksum_sha256: "checksum-sft",
        file_size_bytes: 2048,
        is_active: false,
        created_at: now,
        updated_at: now,
        started_at: now,
        finished_at: now,
        error_message: null
      }
    ];

    const formatsAfterActivate = [
      {
        ...runResult[0],
        is_active: false,
        updated_at: new Date(Date.now() + 10_000).toISOString()
      },
      {
        ...runResult[1],
        is_active: true,
        updated_at: new Date(Date.now() + 10_000).toISOString()
      }
    ];

    const fetchMock = vi.spyOn(global, "fetch");
    fetchMock
      .mockResolvedValueOnce(mockJsonResponse(workspacePayload))
      .mockResolvedValueOnce(mockJsonResponse(datasetPayload))
      .mockResolvedValueOnce(mockJsonResponse(versionPayload))
      .mockResolvedValueOnce(mockJsonResponse(initialFormats))
      .mockResolvedValueOnce(mockJsonResponse(runResult))
      .mockResolvedValueOnce(mockJsonResponse(runResult))
      .mockResolvedValueOnce(mockJsonResponse(runResult[1]))
      .mockResolvedValueOnce(mockJsonResponse(formatsAfterActivate));

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false
        }
      }
    });
    const user = userEvent.setup();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <FormatStandardPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/workspaces",
        expect.objectContaining({
          method: "GET",
          headers: expect.objectContaining({ Authorization: "Bearer token" })
        })
      );
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/datasets?workspace_id=1",
        expect.objectContaining({
          method: "GET",
          headers: expect.objectContaining({ Authorization: "Bearer token" })
        })
      );
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/datasets/10/versions",
        expect.objectContaining({
          method: "GET",
          headers: expect.objectContaining({ Authorization: "Bearer token" })
        })
      );
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/datasets/10/versions/21/formats",
        expect.objectContaining({
          method: "GET",
          headers: expect.objectContaining({ Authorization: "Bearer token" })
        })
      );
    });

    await user.click(screen.getByRole("button", { name: "触发格式转换" }));

    await waitFor(() => {
      const runCall = fetchMock.mock.calls.find(([url]) =>
        url === "http://localhost:8000/api/v1/datasets/10/versions/21/formats/run"
      );
      expect(runCall).toBeDefined();
      expect(runCall?.[1]).toMatchObject({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer token",
          "Content-Type": "application/json"
        }),
        body: JSON.stringify({ formats: ["jsonl", "sft", "parquet"] })
      });
    });

    expect(await screen.findByText(/格式转换任务已触发/)).toBeInTheDocument();
    const jsonlTexts = await screen.findAllByText("JSONL");
    expect(jsonlTexts.length).toBeGreaterThan(0);
    expect(screen.getAllByText("SFT").length).toBeGreaterThan(0);

    const rows = screen.getAllByRole("row");
    const sftRow = rows.find((row) => within(row).queryByText("SFT"));
    expect(sftRow).toBeTruthy();

    await user.click(within(sftRow as HTMLElement).getByRole("button", { name: "设为当前" }));

    await waitFor(() => {
      const activateCall = fetchMock.mock.calls.find(([url]) =>
        url === "http://localhost:8000/api/v1/datasets/10/versions/21/formats/101/activate"
      );
      expect(activateCall).toBeDefined();
      expect(activateCall?.[1]).toMatchObject({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer token",
          "Content-Type": "application/json"
        })
      });
    });

    expect(await screen.findByText(/SFT 已设为当前可用版本/)).toBeInTheDocument();
    const activeBadges = screen.getAllByText("当前启用");
    expect(activeBadges).toHaveLength(1);
    expect(within(activeBadges[0].closest("tr") as HTMLElement).getByText("SFT")).toBeInTheDocument();
  });
});
