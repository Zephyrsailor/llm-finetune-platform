import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { DashboardPage } from "../dashboard/DashboardPage";

function mockResponse<T>(data: T, ok = true): Response {
  return {
    ok,
    json: async () => data
  } as unknown as Response;
}

describe("DashboardPage", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false
        }
      }
    });
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
          <DashboardPage />
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  test("渲染仪表盘并支持切换工作空间", async () => {
    const now = new Date().toISOString();
    const fetchMock = vi.spyOn(global, "fetch");
    fetchMock.mockResolvedValueOnce(
      mockResponse([
        {
          id: 1,
          name: "Alpha Workspace",
          description: null,
          plan: null,
          status: "active",
          created_at: now,
          updated_at: now,
          members: [],
          projects: []
        },
        {
          id: 2,
          name: "Beta Workspace",
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
      mockResponse({
        generated_at: now,
        workspaces: [
          {
            workspace_id: 1,
            workspace_name: "Alpha Workspace",
            stages: [
              {
                stage: "data_ingestion",
                status: "completed",
                responsible: "owner@example.com",
                updated_at: now,
                notes: "最近完成的版本：v1"
              },
              {
                stage: "training",
                status: "in_progress",
                responsible: "owner@example.com",
                updated_at: now,
                notes: "训练任务正在排队"
              },
              {
                stage: "evaluation",
                status: "completed",
                responsible: "qa@example.com",
                updated_at: now,
                notes: "评估得分 0.82"
              },
              {
                stage: "deployment",
                status: "unknown",
                responsible: null,
                updated_at: null,
                notes: "部署节点离线"
              }
            ],
            metrics: [
              {
                key: "planned_data_volume",
                label: "数据量（条）",
                description: "待集成：数据导入完成后展示最近一次导入的记录数。",
                value: null,
                unit: "rows"
              }
            ]
          }
        ]
      })
    );
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        generated_at: now,
        workspaces: [
          {
            workspace_id: 2,
            workspace_name: "Beta Workspace",
            stages: [
              {
                stage: "data_ingestion",
                status: "in_progress",
                responsible: "beta@example.com",
                updated_at: now,
                notes: "清洗任务正在运行"
              },
              {
                stage: "training",
                status: "not_started",
                responsible: null,
                updated_at: null,
                notes: "尚未创建训练项目"
              },
              {
                stage: "evaluation",
                status: "not_started",
                responsible: null,
                updated_at: null,
                notes: "尚未接入评估流水线事件"
              },
              {
                stage: "deployment",
                status: "not_started",
                responsible: null,
                updated_at: null,
                notes: "尚未接入部署流水线事件"
              }
            ],
            metrics: [
              {
                key: "planned_data_volume",
                label: "数据量（条）",
                description: "待集成：数据导入完成后展示最近一次导入的记录数。",
                value: null,
                unit: "rows"
              }
            ]
          }
        ]
      })
    );

    renderPage();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/workspaces",
        expect.objectContaining({ method: "GET" })
      );
    });

    expect(await screen.findByText("Alpha Workspace")).toBeInTheDocument();
    expect(await screen.findByText("数据导入")).toBeInTheDocument();
    expect(await screen.findByText("训练任务正在排队")).toBeInTheDocument();

    const selector = screen.getByLabelText("工作空间") as HTMLSelectElement;
    await userEvent.selectOptions(selector, ["2"]);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/dashboard/summary?workspace_id=2",
        expect.objectContaining({ method: "GET" })
      );
    });

    expect(await screen.findAllByText("Beta Workspace")).toHaveLength(2);
    expect(await screen.findByText("清洗任务正在运行")).toBeInTheDocument();
  });

  test("无工作空间时提示空状态", async () => {
    const fetchMock = vi.spyOn(global, "fetch");
    fetchMock.mockResolvedValueOnce(mockResponse([]));

    renderPage();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/workspaces",
        expect.objectContaining({ method: "GET" })
      );
    });

    expect(
      await screen.findByText("尚未加入任何工作空间，请先在“工作空间管理”页面创建或加入一个工作空间。")
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
