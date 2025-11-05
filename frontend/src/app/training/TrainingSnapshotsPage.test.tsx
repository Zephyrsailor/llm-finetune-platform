import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { TrainingSnapshotsPage } from "./TrainingSnapshotsPage";
import { TrainingSnapshot } from "../../lib/api";

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

describe("TrainingSnapshotsPage", () => {
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
          <TrainingSnapshotsPage />
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  test("展示快照并支持续训与回滚操作", async () => {
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

    const snapshots: TrainingSnapshot[] = [
      {
        id: 10,
        workspace_id: 1,
        job_id: 88,
        run_id: 77,
        path: "/var/lib/llmft/training/1/88/runs/77/snapshots/20250101000000",
        trigger_type: "scheduled",
        created_by: null,
        created_at: now,
        metrics: { final_loss: 0.52, accuracy: 0.91 },
        notes: "自动保存",
        restored_at: null,
        restored_by: null,
        step: 1200,
        epoch: 2
      }
    ];

    const resumedRun = {
      id: 302,
      job_id: 88,
      status: "queued",
      started_at: now,
      finished_at: null,
      metrics: null,
      artifact_uri: null,
      exit_code: null,
      resumed_from_snapshot_id: 10
    };

    const fetchMock = vi.spyOn(global, "fetch").mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = resolveRequestUrl(input);
      if (url.endsWith("/api/v1/workspaces")) {
        return mockJsonResponse(workspaceList);
      }
      if (url.includes("/api/v1/training/snapshots/10:resume")) {
        return mockJsonResponse(resumedRun);
      }
      if (url.includes("/api/v1/training/snapshots/10:rollback")) {
        snapshots[0] = { ...snapshots[0], restored_at: now, restored_by: 5 };
        return mockJsonResponse({ ...snapshots[0] });
      }
      if (url.includes("/api/v1/training/snapshots")) {
        return mockJsonResponse(snapshots);
      }
      return mockJsonResponse([]);
    });

    renderPage();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/v1/workspaces", expect.anything());
    });

    await screen.findByText(/快照 #10/);

    const resumeButton = await screen.findByRole("button", { name: "从快照断点续训" });
    await userEvent.click(resumeButton);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/training/snapshots/10:resume",
        expect.objectContaining({ method: "POST" })
      );
      expect(screen.getByText(/已触发断点续训/)).toBeInTheDocument();
    });

    const notesField = screen.getByLabelText("操作备注（可选）");
    await userEvent.clear(notesField);
    await userEvent.type(notesField, "需要回滚确认质量");

    const rollbackButton = screen.getByRole("button", { name: "回滚至该快照" });
    await userEvent.click(rollbackButton);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/training/snapshots/10:rollback",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ reason: "需要回滚确认质量" })
        })
      );
      expect(screen.getByText(/已回滚到快照/)).toBeInTheDocument();
    });
  });
});
