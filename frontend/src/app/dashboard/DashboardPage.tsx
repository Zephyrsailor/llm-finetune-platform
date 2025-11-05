import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  dashboardApi,
  DashboardSummary,
  DashboardWorkspaceSummary,
  StageStatusSummary,
  StageStatusValue,
  workspaceApi,
  WorkspaceDetail
} from "../../lib/api";
import { AppShell } from "../layout/AppShell";

const STAGE_INFO: Record<string, { title: string; description: string }> = {
  data_ingestion: { title: "数据导入", description: "聚合数据集创建与流水线任务状态" },
  training: { title: "训练", description: "跟踪模型训练项目与流水线运行情况" },
  evaluation: { title: "评估", description: "展示评估流水线最新执行结果" },
  deployment: { title: "部署", description: "关注上线任务与资源健康度" }
};

const STATUS_META: Record<StageStatusValue, { label: string; badgeClass: string }> = {
  not_started: { label: "未启动", badgeClass: "bg-slate-200 text-slate-600" },
  in_progress: { label: "进行中", badgeClass: "bg-blue-100 text-blue-600" },
  completed: { label: "已完成", badgeClass: "bg-emerald-100 text-emerald-600" },
  unknown: { label: "待确认", badgeClass: "bg-amber-100 text-amber-600" }
};

function formatDateTime(value?: string | null): string {
  if (!value) {
    return "--";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function StageCard({ stage }: { stage: StageStatusSummary }) {
  const info = STAGE_INFO[stage.stage] ?? { title: stage.stage, description: "" };
  const meta = STATUS_META[stage.status] ?? STATUS_META.unknown;
  return (
    <div className="rounded-3xl border border-slate-200 bg-white px-6 py-7 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">{info.title}</h3>
          {info.description && <p className="mt-1 text-sm text-slate-500">{info.description}</p>}
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${meta.badgeClass}`}>{meta.label}</span>
      </div>

      {stage.notes && <p className="mt-6 text-sm leading-relaxed text-slate-600">{stage.notes}</p>}

      <dl className="mt-6 space-y-3 text-sm text-slate-500">
        {stage.responsible && (
          <div className="flex items-center justify-between">
            <dt>负责人</dt>
            <dd className="font-medium text-slate-800">{stage.responsible}</dd>
          </div>
        )}
        {stage.updated_at && (
          <div className="flex items-center justify-between">
            <dt>更新时间</dt>
            <dd className="font-medium text-slate-800">{formatDateTime(stage.updated_at)}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}

function MetricCard({ metric }: { metric: DashboardWorkspaceSummary["metrics"][number] }) {
  return (
    <div className="rounded-3xl border border-slate-200 bg-white px-6 py-7 shadow-sm">
      <h4 className="text-sm font-semibold text-slate-900">{metric.label}</h4>
      <p className="mt-1 text-xs text-slate-500">{metric.description}</p>
      <p className="mt-6 text-2xl font-semibold text-slate-900">
        {metric.value != null ? metric.value : "待接入"}
        {metric.unit ? <span className="ml-2 text-sm font-medium text-slate-500">{metric.unit}</span> : null}
      </p>
    </div>
  );
}

function PlaceholderGrid() {
  const CARDS = [
    { title: "模块待定", desc: "这里暂时留空，用于未来的模块/图表占位。" },
    { title: "模块占位", desc: "可放置首要数字、任务、资源等内容。" },
    { title: "模块占位", desc: "预留用于实时观测或辅助信息。" },
    { title: "下一步占位", desc: "在此记录下一步行动或高优先级事项。" }
  ];
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {CARDS.map((card) => (
        <div
          key={card.title}
          className="rounded-3xl border border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center shadow-sm"
        >
          <h4 className="text-base font-semibold text-slate-600">{card.title}</h4>
          <p className="mt-3 text-sm text-slate-500">{card.desc}</p>
        </div>
      ))}
    </div>
  );
}

function WorkspaceSummarySection({ summary, generatedAt }: { summary: DashboardWorkspaceSummary; generatedAt: string }) {
  const heroStats = summary.stages.map((stage) => {
    const info = STAGE_INFO[stage.stage] ?? { title: stage.stage, description: "" };
    return {
      key: stage.stage,
      title: info.title,
      status: STATUS_META[stage.status]?.label ?? STATUS_META.unknown.label,
      badgeClass: STATUS_META[stage.status]?.badgeClass ?? STATUS_META.unknown.badgeClass,
      description: info.description,
      notes: stage.notes
    };
  });

  return (
    <section className="space-y-8">
      <div className="flex flex-col gap-2 md:flex-row md:items-baseline md:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">{summary.workspace_name}</h2>
          <p className="text-sm text-slate-500">仪表盘生成时间：{formatDateTime(generatedAt)}</p>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-4 md:grid-cols-2 sm:grid-cols-2">
        {heroStats.map((stat) => (
          <div
            key={stat.key}
            className="rounded-3xl border border-slate-200 bg-gradient-to-br from-blue-50 via-white to-white px-6 py-6 shadow-sm"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-slate-500">{stat.title}</span>
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stat.badgeClass}`}>{stat.status}</span>
            </div>
            <p className="mt-4 text-xs text-slate-500">{stat.description}</p>
            {stat.notes && <p className="mt-4 text-sm text-slate-600">{stat.notes}</p>}
          </div>
        ))}
      </div>

      {summary.metrics.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-slate-900">关键指标</h3>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {summary.metrics.map((metric) => (
              <MetricCard key={metric.key} metric={metric} />
            ))}
          </div>
        </div>
      )}

      <PlaceholderGrid />
    </section>
  );
}

export function DashboardPage() {
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);

  const workspacesQuery = useQuery<WorkspaceDetail[]>({
    queryKey: ["workspaces"],
    queryFn: () => workspaceApi.list(),
    staleTime: 60_000
  });

  useEffect(() => {
    if (workspacesQuery.data && workspacesQuery.data.length > 0 && selectedWorkspaceId === null) {
      setSelectedWorkspaceId(workspacesQuery.data[0].id);
    }
  }, [workspacesQuery.data, selectedWorkspaceId]);

  const summaryQuery = useQuery<DashboardSummary>({
    queryKey: ["dashboard-summary", selectedWorkspaceId],
    queryFn: () => dashboardApi.summary({ workspaceId: selectedWorkspaceId ?? undefined }),
    enabled: Boolean(workspacesQuery.data && workspacesQuery.data.length > 0 && selectedWorkspaceId !== null),
    staleTime: 30_000
  });

  const workspaces = workspacesQuery.data ?? [];
  const isWorkspaceLoading = workspacesQuery.isLoading;
  const workspaceError = workspacesQuery.error as Error | null;

  const summary = summaryQuery.data;
  const summaryError = summaryQuery.error as Error | null;

  const selectedSummary = useMemo(() => {
    if (!summary) {
      return [];
    }
    return summary.workspaces;
  }, [summary]);

  const toolbar = (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-8 py-4 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:gap-4">
        <div className="flex flex-col gap-2">
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor="workspace-select">
            工作空间
          </label>
          <select
            id="workspace-select"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-200"
            value={selectedWorkspaceId ?? ""}
            onChange={(event) => setSelectedWorkspaceId(Number(event.target.value))}
            disabled={isWorkspaceLoading || workspaces.length === 0}
          >
            {workspaces.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.name}
              </option>
            ))}
          </select>
        </div>
        <div className="text-xs text-slate-500">
          {summaryQuery.isFetching ? "正在刷新数据..." : "数据每 30 秒自动刷新一次"}
        </div>
      </div>
      {workspaceError && <p className="text-sm text-rose-500">加载工作空间失败：{workspaceError.message}</p>}
      {!isWorkspaceLoading && !workspaceError && workspaces.length === 0 && (
        <p className="text-sm text-slate-500">尚未加入任何工作空间，请先创建或加入工作空间。</p>
      )}
    </div>
  );

  return (
    <AppShell
      title="运营总览仪表板"
      subtitle="跨数据、训练、评估、部署阶段的统一视图"
      searchPlaceholder="搜索流程、运行或告警"
      primaryAction={{ label: "新建运行", to: "/training/wizard" }}
      toolbar={toolbar}
    >
      {summaryError && (
        <section className="rounded-3xl border border-rose-200 bg-rose-50 px-6 py-6 text-sm text-rose-600">
          仪表盘数据加载失败：{summaryError.message}
        </section>
      )}

      {summaryQuery.isLoading && !summaryError && workspaces.length > 0 && (
        <section className="rounded-3xl border border-slate-200 bg-white px-6 py-6 text-sm text-slate-500">
          正在加载仪表盘数据...
        </section>
      )}

      {!summaryQuery.isLoading && !summaryError && summary && selectedSummary.length === 0 && (
        <section className="rounded-3xl border border-amber-200 bg-amber-50 px-6 py-6 text-sm text-amber-700">
          当前工作空间暂无可展示的数据，请先完成数据导入或训练流程。
        </section>
      )}

      {selectedSummary.map((workspaceSummary) => (
        <section
          key={workspaceSummary.workspace_id}
          className="rounded-3xl border border-slate-200 bg-white/80 px-6 py-8 shadow-sm backdrop-blur-sm"
        >
          <WorkspaceSummarySection summary={workspaceSummary} generatedAt={summary?.generated_at ?? ""} />
        </section>
      ))}
    </AppShell>
  );
}
