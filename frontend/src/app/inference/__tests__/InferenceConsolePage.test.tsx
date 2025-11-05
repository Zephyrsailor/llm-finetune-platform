import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { InferenceConsolePage } from "../InferenceConsolePage";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";

function jsonResponse(payload: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init
  });
}

beforeEach(() => {
  localStorage.setItem("access_token", "token");
});

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

test("渲染控制台并支持创建密钥及触发推理", async () => {
  const now = new Date().toISOString();
  const apiKeys = [
    {
      id: 1,
      name: "default-key",
      is_active: true,
      rate_limit_per_minute: 120,
      daily_quota: 1000,
      created_at: now,
      revoked_at: null,
      last_used_at: null
    }
  ];
  const logs = [
    {
      id: 10,
      deployment_id: 201,
      model_version_id: 1001,
      status: "success",
      latency_ms: 15.2,
      input_tokens: 42,
      output_tokens: 64,
      created_at: now
    }
  ];

  const fetchMock = vi.spyOn(global, "fetch").mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = init?.method ?? "GET";

    if (url === `${API_BASE}/v1/workspaces` && method === "GET") {
      return jsonResponse([
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
      ]);
    }

    if (url.startsWith(`${API_BASE}/v1/inference/api-keys`) && method === "GET") {
      return jsonResponse({ items: apiKeys });
    }

    if (url.startsWith(`${API_BASE}/v1/inference/logs`) && method === "GET") {
      return jsonResponse({ logs });
    }

    if (url === `${API_BASE}/v1/inference/api-keys` && method === "POST") {
      const createdAt = new Date().toISOString();
      const newKey = {
        id: apiKeys.length + 1,
        name: "integration",
        is_active: true,
        rate_limit_per_minute: 0,
        daily_quota: 0,
        created_at: createdAt,
        revoked_at: null,
        last_used_at: null
      };
      apiKeys.unshift(newKey);
      return jsonResponse({ api_key: newKey, secret: "secret-xyz" }, { status: 201 });
    }

    if (url === `${API_BASE}/v1/inference` && method === "POST") {
      const createdAt = new Date().toISOString();
      logs.unshift({
        id: logs.length + 10,
        deployment_id: 201,
        model_version_id: 1001,
        status: "success",
        latency_ms: 18.4,
        input_tokens: 60,
        output_tokens: 72,
        created_at: createdAt
      });
      return jsonResponse({
        call_id: logs[0].id,
        deployment_id: 201,
        model_version_id: 1001,
        outputs: [{ output: "响应示例" }],
        latency_ms: 18.4,
        input_tokens: 60,
        output_tokens: 72
      });
    }

    return jsonResponse({}, { status: 404 });
  });

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      }
    }
  });

  render(
    <QueryClientProvider client={queryClient}>
      <InferenceConsolePage />
    </QueryClientProvider>
  );

  expect(await screen.findByText("推理 API 控制台")).toBeInTheDocument();
  expect(await screen.findByText("default-key")).toBeInTheDocument();
  expect(screen.getByText("近 50 次总调用")).toBeInTheDocument();
  expect(screen.getByText("成功次数")).toBeInTheDocument();

  await userEvent.type(screen.getByLabelText("名称"), "integration");
  await userEvent.click(screen.getByText("创建 API Key"));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/v1/inference/api-keys`,
      expect.objectContaining({ method: "POST" })
    );
  });
  expect(await screen.findByText(/API Key 创建成功/)).toBeInTheDocument();
  expect(screen.getByText(/一次性明文 API Key/)).toBeInTheDocument();

  await userEvent.clear(screen.getByLabelText("部署 ID"));
  await userEvent.type(screen.getByLabelText("部署 ID"), "201");
  await userEvent.click(screen.getByText("发送推理请求"));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/v1/inference`,
      expect.objectContaining({ method: "POST" })
    );
  });

  expect(await screen.findByText(/推理成功/)).toBeInTheDocument();
  expect(screen.getByText("响应示例")).toBeInTheDocument();

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/v1/inference/logs?workspace_id=1&limit=50`,
      expect.objectContaining({ method: "GET" })
    );
  });
});
