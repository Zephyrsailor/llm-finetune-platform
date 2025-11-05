import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { DatasetUploadPage } from "./DatasetUploadPage";

function mockResponse<T>(data: T, ok = true): Response {
  return {
    ok,
    json: async () => data
  } as unknown as Response;
}

describe("DatasetUploadPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("上传数据集并触发清洗流程", async () => {
    localStorage.setItem("access_token", "token");
    const now = new Date().toISOString();
    const fetchMock = vi.spyOn(global, "fetch");
    fetchMock.mockResolvedValueOnce(
      mockResponse([
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
      ])
    );

    const datasetPayload = {
      id: 10,
      workspace_id: 1,
      name: "support-faq",
      source_type: "upload",
      file_size_bytes: 20,
      mime_type: "application/json",
      tags: ["support"],
      status: "active",
      created_by: 1,
      created_at: now,
      updated_at: now
    };
    fetchMock.mockResolvedValueOnce(mockResponse(datasetPayload));

    const versionPayload = {
      version: {
        id: 21,
        dataset_id: 10,
        version: 1,
        status: "completed",
        created_by: 1,
        created_at: now,
        updated_at: now
      },
      job: {
        id: 31,
        dataset_version_id: 21,
        status: "completed",
        logs_path: "workspaces/1/datasets/10/v1/logs/job-31.log",
        created_at: now,
        updated_at: now
      }
    };
    fetchMock.mockResolvedValueOnce(mockResponse(versionPayload));

    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <DatasetUploadPage />
      </MemoryRouter>
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

    await user.type(screen.getByLabelText("数据集名称"), "support-faq");
    await user.type(screen.getByLabelText("数据类型"), "jsonl");
    await user.type(screen.getByLabelText("标签（逗号分隔）"), "support");
    await user.type(screen.getByLabelText("备注（将同步用于初次清洗说明）"), "需要去重");

    const file = new File([JSON.stringify({ question: "hi" })], "faq.jsonl", { type: "application/json" });
    await user.upload(screen.getByLabelText("上传文件"), file);

    await user.click(screen.getByRole("button", { name: "创建数据集" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });

    const createCall = fetchMock.mock.calls[1];
    expect(createCall[0]).toBe("http://localhost:8000/api/v1/datasets");
    expect((createCall[1] as RequestInit).headers).toMatchObject({ Authorization: "Bearer token" });

    expect(await screen.findByText("数据集创建成功，可继续触发清洗流水线。")).toBeInTheDocument();
    expect(screen.getByText("support-faq")).toBeInTheDocument();

    await user.type(screen.getByLabelText("清洗备注"), "初始清洗");
    await user.click(screen.getByRole("button", { name: "触发清洗任务" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(3);
    });
    const versionCall = fetchMock.mock.calls[2];
    expect(versionCall[0]).toBe("http://localhost:8000/api/v1/datasets/10/versions");
    expect(versionCall[1]).toMatchObject({
      method: "POST",
      headers: expect.objectContaining({ Authorization: "Bearer token" })
    });

    expect(await screen.findByText(/清洗任务已启动/)).toBeInTheDocument();
    expect(screen.getByText(/已完成（占位流程）/)).toBeInTheDocument();
    expect(screen.getByText("workspaces/1/datasets/10/v1/logs/job-31.log")).toBeInTheDocument();
  });
});
