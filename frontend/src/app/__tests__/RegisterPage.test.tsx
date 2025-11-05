import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { RegisterPage } from "../(auth)/RegisterPage";

describe("RegisterPage", () => {
  const originalLocation = window.location;
  let assignMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.resetAllMocks();
    assignMock = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: {
        ...originalLocation,
        assign: assignMock
      }
    });
    localStorage.clear();
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation
    });
  });

  test("未填写邮箱时无法请求验证码", async () => {
    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "获取验证码" }));

    expect(screen.getByText("请先填写邮箱以获取验证码。")).toBeInTheDocument();
  });

  test("完成注册后保存令牌并跳转", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => ({ access_token: "access", refresh_token: "refresh", token_type: "bearer" })
    } as Response);

    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    );

    await user.type(screen.getByLabelText("邮箱"), "user@example.com");
    await user.type(screen.getByLabelText("验证码"), "123456");
    await user.type(screen.getByLabelText("密码"), "Password123");
    await user.click(screen.getByRole("button", { name: "完成注册" }));

    await waitFor(() => {
      expect(localStorage.getItem("access_token")).toBe("access");
    });
    expect(localStorage.getItem("refresh_token")).toBe("refresh");
    expect(assignMock).toHaveBeenCalledWith("/dashboard");
  });
});
