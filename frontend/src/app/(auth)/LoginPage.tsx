import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";

import { authApi } from "../../lib/api";

interface LoginForm {
  email: string;
  password: string;
}

export function LoginPage() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting }
  } = useForm<LoginForm>();
  const [authError, setAuthError] = useState<string | null>(null);

  const onSubmit = handleSubmit(async (values) => {
    setAuthError(null);
    try {
      const tokens = await authApi.login(values);
      localStorage.setItem("access_token", tokens.access_token);
      localStorage.setItem("refresh_token", tokens.refresh_token);
      window.location.assign("/dashboard");
    } catch (error) {
      if (error instanceof Error) {
        setAuthError(error.message);
      } else {
        setAuthError("登录失败，请稍后再试。");
      }
    }
  });

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100">
      <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900/60 p-8 shadow-lg space-y-4">
        <div>
          <h1 className="text-2xl font-semibold">登录 LLM Finetune Platform</h1>
          <p className="text-sm text-slate-400">使用注册邮箱与密码登录。</p>
        </div>
        <form className="space-y-4" onSubmit={onSubmit}>
          <div>
            <label className="block text-sm font-medium text-slate-300" htmlFor="email">
              邮箱
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/40"
              {...register("email", { required: "请输入邮箱" })}
            />
            {errors.email && (
              <p className="mt-1 text-xs text-red-400">{errors.email.message}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300" htmlFor="password">
              密码
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/40"
              {...register("password", { required: "请输入密码" })}
            />
            {errors.password && (
              <p className="mt-1 text-xs text-red-400">{errors.password.message}</p>
            )}
          </div>
          {authError && <p className="text-sm text-red-400">{authError}</p>}
          <button
            className="w-full rounded-md bg-sky-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "正在登录…" : "登录"}
          </button>
        </form>
        <div className="flex items-center justify-between text-sm text-slate-400">
          <Link className="hover:text-sky-400" to="/register">
            没有账号？立即注册
          </Link>
          <Link className="hover:text-sky-400" to="/forgot-password">
            忘记密码？
          </Link>
        </div>
      </div>
    </div>
  );
}
