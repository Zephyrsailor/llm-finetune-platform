import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";

import { authApi } from "../../lib/api";

interface ForgotPasswordForm {
  email: string;
}

export function ForgotPasswordPage() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting }
  } = useForm<ForgotPasswordForm>();
  const [devCode, setDevCode] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    setDevCode(null);
    setMessage(null);
    try {
      const response = await authApi.requestPasswordReset({ email: values.email });
      setDevCode(response.verification_code ?? null);
      setMessage(response.message);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("请求失败，请稍后再试。");
      }
    }
  });

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100">
      <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900/60 p-8 shadow-lg space-y-4">
        <div>
          <h1 className="text-2xl font-semibold">找回密码</h1>
          <p className="text-sm text-slate-400">填写注册邮箱，我们会发送验证码。</p>
        </div>
        <form className="space-y-4" onSubmit={onSubmit}>
          <div>
            <label className="block text-sm font-medium text-slate-300" htmlFor="email">
              邮箱
            </label>
            <input
              id="email"
              type="email"
              className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              {...register("email", { required: "请输入邮箱" })}
            />
            {errors.email && <p className="mt-1 text-xs text-red-400">{errors.email.message}</p>}
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          {message && <p className="text-sm text-emerald-400">{message}</p>}
          {devCode && (
            <p className="text-xs text-slate-400">
              开发模式验证码：<span className="font-mono text-sky-400">{devCode}</span>
            </p>
          )}
          <button
            className="w-full rounded-md bg-sky-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "正在发送…" : "发送验证码"}
          </button>
        </form>
        <div className="flex items-center justify-between text-sm text-slate-400">
          <Link className="hover:text-sky-400" to="/reset-password">
            已有验证码？去重置密码
          </Link>
          <Link className="hover:text-sky-400" to="/">
            返回登录
          </Link>
        </div>
      </div>
    </div>
  );
}
