import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";

import { authApi } from "../../lib/api";

interface RegisterForm {
  email: string;
  password: string;
  code: string;
}

export function RegisterPage() {
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting }
  } = useForm<RegisterForm>();
  const emailValue = watch("email");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const requestCode = async () => {
    setError(null);
    if (!emailValue) {
      setError("请先填写邮箱以获取验证码。");
      return;
    }
    try {
      const response = await authApi.requestRegistration({ email: emailValue });
      setDevCode(response.verification_code ?? null);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("验证码发送失败，请稍后再试。");
      }
    }
  };

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    try {
      const tokens = await authApi.confirmRegistration({
        email: values.email,
        password: values.password,
        code: values.code
      });
      localStorage.setItem("access_token", tokens.access_token);
      localStorage.setItem("refresh_token", tokens.refresh_token);
      window.location.assign("/dashboard");
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("注册失败，请稍后再试。");
      }
    }
  });

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100">
      <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900/60 p-8 shadow-lg space-y-4">
        <div>
          <h1 className="text-2xl font-semibold">注册账号</h1>
          <p className="text-sm text-slate-400">邮箱会收到验证码，输入后完成注册。</p>
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
          <button
            className="w-full rounded-md border border-sky-500 bg-transparent px-3 py-2 text-sm font-semibold text-sky-400 hover:bg-sky-500/20"
            type="button"
            onClick={requestCode}
          >
            获取验证码
          </button>
          {devCode && (
            <p className="text-xs text-slate-400">
              开发模式验证码：<span className="font-mono text-sky-400">{devCode}</span>
            </p>
          )}
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
            <label className="block text-sm font-medium text-slate-300" htmlFor="password">
              密码
            </label>
            <input
              id="password"
              type="password"
              className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              {...register("password", { required: "请输入密码", minLength: { value: 8, message: "至少 8 位" } })}
            />
            {errors.password && <p className="mt-1 text-xs text-red-400">{errors.password.message}</p>}
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            className="w-full rounded-md bg-sky-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "正在注册…" : "完成注册"}
          </button>
        </form>
        <div className="text-sm text-slate-400">
          已有账号？<Link className="text-sky-400 hover:text-sky-300" to="/">返回登录</Link>
        </div>
      </div>
    </div>
  );
}
