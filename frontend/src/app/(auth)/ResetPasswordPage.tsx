import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";

import { authApi } from "../../lib/api";

interface ResetPasswordForm {
  email: string;
  code: string;
  new_password: string;
}

export function ResetPasswordPage() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting }
  } = useForm<ResetPasswordForm>();
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    setMessage(null);
    try {
      await authApi.confirmPasswordReset(values);
      setMessage("密码已重置，请使用新密码登录。");
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("重置失败，请稍后再试。");
      }
    }
  });

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100">
      <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900/60 p-8 shadow-lg space-y-4">
        <div>
          <h1 className="text-2xl font-semibold">重置密码</h1>
          <p className="text-sm text-slate-400">输入邮箱、验证码与新密码完成重置。</p>
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
          <div>
            <label className="block text-sm font-medium text-slate-300" htmlFor="code">
              验证码
            </label>
            <input
              id="code"
              type="text"
              className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              {...register("code", { required: "请输入验证码" })}
            />
            {errors.code && <p className="mt-1 text-xs text-red-400">{errors.code.message}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300" htmlFor="new_password">
              新密码
            </label>
            <input
              id="new_password"
              type="password"
              className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              {...register("new_password", { required: "请输入新密码", minLength: { value: 8, message: "至少 8 位" } })}
            />
            {errors.new_password && <p className="mt-1 text-xs text-red-400">{errors.new_password.message}</p>}
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          {message && <p className="text-sm text-emerald-400">{message}</p>}
          <button
            className="w-full rounded-md bg-sky-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "正在重置…" : "重置密码"}
          </button>
        </form>
        <div className="flex items-center justify-between text-sm text-slate-400">
          <Link className="hover:text-sky-400" to="/forgot-password">
            没收到验证码？重新发送
          </Link>
          <Link className="hover:text-sky-400" to="/">
            返回登录
          </Link>
        </div>
      </div>
    </div>
  );
}
