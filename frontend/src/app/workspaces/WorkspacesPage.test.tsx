import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { WorkspacesPage } from "./WorkspacesPage";
import { WorkspaceDetail } from "../../lib/api";

function mockResponse<T>(data: T, ok = true): Response {
  return {
    ok,
    json: async () => data
  } as unknown as Response;
}

describe("WorkspacesPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("加载并创建工作空间", async () => {
    localStorage.setItem("access_token", "token");
    const now = new Date().toISOString();
    const listData: WorkspaceDetail[] = [
      {
        id: 1,
        name: "Demo Workspace",
        description: null,
        plan: "standard",
        status: "active",
        created_at: now,
        updated_at: now,
        members: [{ user_id: 1, email: "owner@example.com", role: "owner" }],
        projects: []
      }
    ];

    const fetchMock = vi.spyOn(global, "fetch");
    fetchMock.mockResolvedValueOnce(mockResponse(listData));
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        roles: [],
        assignments: [],
        operations: []
      })
    );

    render(
      <MemoryRouter initialEntries={["/workspaces"]}>
        <WorkspacesPage />
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

    expect(
      await screen.findByRole("button", {
        name: /Demo Workspace/
      })
    ).toBeInTheDocument();

    const createdWorkspace: WorkspaceDetail = {
      id: 2,
      name: "New Workspace",
      description: "for testing",
      plan: "enterprise",
      status: "active",
      created_at: now,
      updated_at: now,
      members: [{ user_id: 1, email: "owner@example.com", role: "owner" }],
      projects: []
    };

    fetchMock.mockResolvedValueOnce(mockResponse(createdWorkspace));
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        roles: [],
        assignments: [],
        operations: []
      })
    );

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("名称"), "New Workspace");
    await user.type(screen.getByLabelText("套餐/计划"), "enterprise");
    await user.click(screen.getByRole("button", { name: "创建工作空间" }));

    expect(await screen.findByText("工作空间创建成功")).toBeInTheDocument();

    expect(fetchMock).toHaveBeenCalledTimes(4);
    const [, , createCall] = fetchMock.mock.calls;
    expect(createCall[0]).toBe("http://localhost:8000/api/v1/workspaces");
    expect(createCall[1]).toMatchObject({ method: "POST" });
    expect((createCall[1] as RequestInit).headers).toMatchObject({ Authorization: "Bearer token" });
  });
});
