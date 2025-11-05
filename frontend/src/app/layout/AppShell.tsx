import type { ReactNode } from "react";
import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  Activity,
  Database,
  Gauge,
  LayoutDashboard,
  LucideIcon,
  Server,
  Wand2,
  Workflow
} from "lucide-react";

type PrimaryAction =
  | {
      label: string;
      to: string;
      onClick?: undefined;
    }
  | {
      label: string;
      onClick: () => void;
      to?: undefined;
    };

interface AppShellProps {
  title: string;
  subtitle?: string;
  searchPlaceholder?: string;
  primaryAction?: PrimaryAction;
  toolbar?: ReactNode;
  children: ReactNode;
}

interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
}

const NAV_ITEMS: NavItem[] = [
  { label: "总览看板", to: "/dashboard", icon: LayoutDashboard },
  { label: "数据处理", to: "/data-hub/upload", icon: Database },
  { label: "模型微调", to: "/training/monitor", icon: Wand2 },
  { label: "模型评测", to: "/evaluation/suite", icon: Gauge },
  { label: "模型部署", to: "/deployment", icon: Server },
  { label: "实时观测", to: "/inference", icon: Activity },
  { label: "工作空间", to: "/workspaces", icon: Workflow }
];

function PrimaryActionButton({ action }: { action: PrimaryAction }) {
  const base =
    "inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:ring-offset-2";

  if ("to" in action) {
    return (
      <NavLink to={action.to as string} className={base}>
        {action.label}
      </NavLink>
    );
  }

  return (
    <button type="button" onClick={action.onClick} className={base}>
      {action.label}
    </button>
  );
}

export function AppShell({ title, subtitle, searchPlaceholder, primaryAction, toolbar, children }: AppShellProps) {
  const [searchValue, setSearchValue] = useState("");

  return (
    <div className="flex min-h-screen bg-[#F5F7FB] text-slate-900">
      <aside className="hidden w-72 flex-col bg-[#111936] text-white shadow-2xl lg:flex">
        <div className="px-8 pb-6 pt-10">
          <div className="text-sm font-semibold text-slate-300">Flow Dashboard</div>
          <div className="mt-2 text-2xl font-bold">LLM 微调平台</div>
        </div>
        <nav className="flex-1 space-y-1 px-4">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  [
                    "group flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition",
                    isActive ? "bg-[#2A3B8C] text-white" : "text-slate-300 hover:bg-white/10 hover:text-white"
                  ].join(" ")
                }
              >
                <Icon className="h-4 w-4" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
        <div className="px-6 pb-10">
          <div className="rounded-2xl border border-white/10 bg-white/10 p-5">
            <div className="text-xs uppercase tracking-wide text-slate-300">系统健康度</div>
            <div className="mt-3 text-3xl font-semibold text-emerald-300">99.9%</div>
            <p className="mt-2 text-xs text-slate-200">全链路服务稳定运行中</p>
          </div>
        </div>
      </aside>

      <div className="flex min-h-screen flex-1 flex-col">
        <header className="bg-white/80 backdrop-blur">
          <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-10 py-8 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-[#1F2949]">{title}</h1>
              {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              {searchPlaceholder && (
                <div className="relative">
                  <input
                    type="search"
                    value={searchValue}
                    onChange={(event) => setSearchValue(event.target.value)}
                    placeholder={searchPlaceholder}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-5 py-2 text-sm text-slate-600 shadow-sm outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-200 sm:min-w-[320px]"
                  />
                </div>
              )}
              {primaryAction && <PrimaryActionButton action={primaryAction} />}
            </div>
          </div>
          {toolbar && <div className="border-t border-slate-200 bg-[#EEF2FB]">{toolbar}</div>}
        </header>

        <main className="flex-1">
          <div className="mx-auto w-full max-w-7xl px-10 py-10">
            <div className="space-y-8">{children}</div>
          </div>
        </main>
      </div>
    </div>
  );
}
