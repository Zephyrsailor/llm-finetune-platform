import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  dataHubApi,
  Dataset,
  DatasetFormatType,
  DatasetFormatVersion,
  DatasetVersion,
  formatApi,
  workspaceApi,
  WorkspaceDetail
} from "../../lib/api";
import { DataHubNav } from "./DataHubNav";
import { AppShell } from "../layout/AppShell";

type Feedback = { type: "success" | "error"; text: string } | null;

type NavTab = "options" | "history";

const FORMAT_OPTIONS: Array<{ value: DatasetFormatType; label: string; description: string }> = [
  { value: "jsonl", label: "JSONL", description: "行级 JSON 结构，适用于绝大多数训练流水线" },
  { value: "sft", label: "SFT", description: "prompt/completion 对齐格式" },
  { value: "parquet", label: "Parquet", description: "列式存储，便于批量分析与向量化" }
];

const STATUS_META: Record<DatasetFormatVersion["status"], { label: string; tone: string }> = {
  pending: { label: "待处理", tone: "bg-amber-100 text-amber-700" },
  running: { label: "处理中", tone: "bg-blue-100 text-blue-700" },
  completed: { label: "已完成", tone: "bg-emerald-100 text-emerald-700" },
  failed: { label: "失败", tone: "bg-rose-100 text-rose-700" }
};

function formatBytes(bytes?: number | null): string {
  if (bytes == null) {
    return "—";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function StatusBadge({ status }: { status: DatasetFormatVersion["status"] }) {
  const meta = STATUS_META[status];
  return <span className={`rounded-full px-2 py-1 text-xs font-medium ${meta.tone}`}>{meta.label}</span>;
}

function HeroStat({ title, value, description }: { title: string; value: string; description?: string }) {
  return (
    <div className="rounded-3xl bg-gradient-to-br from-sky-50 via-white to-white px-6 py-6 shadow-sm">
      <div className="text-sm font-semibold text-slate-500">{title}</div>
      <div className="mt-4 text-3xl font-semibold text-slate-900">{value}</div>
      {description ? <div className="mt-2 text-xs text-slate-500">{description}</div> : null}
    </div>
  );
}

function FormatOptionCard({
  option,
  checked,
  disabled,
  toggle
}: {
  option: (typeof FORMAT_OPTIONS)[number];
  checked: boolean;
  disabled: boolean;
  toggle: (value: DatasetFormatType) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => {
        if (!disabled) {
          toggle(option.value);
        }
      }}
      className={`flex flex-col gap-2 rounded-2xl border px-4 py-4 text-left transition ${
        disabled
          ? "cursor-not-allowed border-slate-200 bg-slate-50 text-slate-400"
          : checked
            ? "border-sky-300 bg-sky-50 shadow-sm text-slate-900"
            : "border-slate-200 bg-white text-slate-700 hover:border-sky-200"
      }`}
      disabled={disabled}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">{option.label}</span>
        <span
          className={`inline-flex h-5 w-5 items-center justify-center rounded-full border ${
            disabled
              ? "border-slate-300 text-slate-300"
              : checked
                ? "border-sky-400 bg-sky-500 text-white"
                : "border-slate-300 text-slate-400"
          }`}
        >
          {checked ? "✓" : ""}
        </span>
      </div>
      <p className="text-xs text-slate-500">{option.description}</p>
      {disabled && <p className="text-[11px] text-emerald-500">已生成并启用</p>}
    </button>
  );
}

function FormatTable({
  items,
  onDownload,
  onActivate
}: {
  items: DatasetFormatVersion[];
  onDownload: (record: DatasetFormatVersion) => void;
  onActivate: (record: DatasetFormatVersion) => void;
}) {
  if (!items.length) {
    return <p className="rounded-3xl border border-slate-200 bg-white px-6 py-6 text-sm text-slate-500">暂无格式版本记录。</p>;
  }

  return (
    <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200 text-left text-sm text-slate-600">
        <thead className="bg-slate-50 text-xs font-semibold text-slate-500">
          <tr>
            <th className="px-5 py-3">格式</th>
            <th className="px-5 py-3">状态</th>
            <th className="px-5 py-3">文件大小</th>
            <th className="px-5 py-3">最新时间</th>
            <th className="px-5 py-3">日志</th>
            <th className="px-5 py-3 text-right">操作</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200">
          {items.map((record) => (
            <tr key={record.id} className="hover:bg-slate-50">
              <td className="px-5 py-4 font-semibold text-slate-800">{record.format.toUpperCase()}</td>
              <td className="px-5 py-4">
                <div className="flex items-center gap-2">
                  <StatusBadge status={record.status} />
                  {record.is_active ? (
                    <span className="text-xs font-medium text-emerald-600">当前启用</span>
                  ) : null}
                </div>
              </td>
              <td className="px-5 py-4 text-slate-500">{formatBytes(record.file_size_bytes)}</td>
              <td className="px-5 py-4 text-slate-500">{record.updated_at ?? "—"}</td>
              <td className="px-5 py-4 text-xs text-slate-400">{record.logs_path ?? "—"}</td>
              <td className="px-5 py-4">
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => onDownload(record)}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 hover:border-slate-300"
                  >
                    下载
                  </button>
                  <button
                    type="button"
                    onClick={() => onActivate(record)}
                    className="rounded-xl border border-sky-200 bg-sky-500/10 px-3 py-1 text-xs font-medium text-sky-600 hover:border-sky-300"
                    disabled={record.is_active}
                  >
                    设为当前
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function FormatStandardPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<NavTab>("options");
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [selectedDatasetId, setSelectedDatasetId] = useState<number | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [selectedFormats, setSelectedFormats] = useState<DatasetFormatType[]>([]);
  const [feedback, setFeedback] = useState<Feedback>(null);

  const workspaceQuery = useQuery<WorkspaceDetail[]>({
    queryKey: ["workspaces"],
    queryFn: () => workspaceApi.list(),
    refetchOnWindowFocus: false
  });

  const datasetsQuery = useQuery<Dataset[]>({
    queryKey: ["datasets", selectedWorkspaceId],
    enabled: selectedWorkspaceId != null,
    queryFn: () => dataHubApi.listDatasets(selectedWorkspaceId ?? 0)
  });

  const versionsQuery = useQuery<DatasetVersion[]>({
    queryKey: ["dataset-versions", selectedDatasetId],
    enabled: selectedDatasetId != null,
    queryFn: () => dataHubApi.listVersions(selectedDatasetId ?? 0)
  });

  const formatsQuery = useQuery<DatasetFormatVersion[]>({
    queryKey: ["dataset-format-versions", selectedDatasetId, selectedVersionId],
    enabled: selectedDatasetId != null && selectedVersionId != null,
    queryFn: () => formatApi.listFormats(selectedDatasetId ?? 0, selectedVersionId ?? 0),
    refetchInterval: (data) =>
      Array.isArray(data) && data.some((record) => record.status === "pending" || record.status === "running")
        ? 4000
        : false
  });

  useEffect(() => {
    if (workspaceQuery.data?.length && selectedWorkspaceId == null) {
      setSelectedWorkspaceId(workspaceQuery.data[0].id);
    }
  }, [workspaceQuery.data, selectedWorkspaceId]);

  useEffect(() => {
    const datasets = datasetsQuery.data ?? [];
    if (!datasets.length) {
      setSelectedDatasetId(null);
      return;
    }
    if (!datasets.some((item) => item.id === selectedDatasetId)) {
      setSelectedDatasetId(datasets[0].id);
    }
  }, [datasetsQuery.data, selectedDatasetId]);

  useEffect(() => {
    const versions = versionsQuery.data ?? [];
    if (!versions.length) {
      setSelectedVersionId(null);
      return;
    }
    if (!versions.some((item) => item.id === selectedVersionId)) {
      setSelectedVersionId(versions[0].id);
    }
  }, [versionsQuery.data, selectedVersionId]);

  useEffect(() => {
    setSelectedFormats([]);
  }, [selectedDatasetId, selectedVersionId]);

  const runMutation = useMutation({
    mutationFn: (formats: DatasetFormatType[] | undefined) => {
      if (selectedDatasetId == null || selectedVersionId == null) {
        throw new Error("请选择数据集与版本后再触发转换。");
      }
      return formatApi.runConversion(selectedDatasetId, selectedVersionId, formats);
    },
    onSuccess: (records, variables) => {
      const formatNames = (variables && variables.length > 0 ? variables : selectedFormats)
        .map((value) => value.toUpperCase())
        .join(" / ");
      setFeedback({ type: "success", text: `格式转换任务已触发：${formatNames}` });
      queryClient.invalidateQueries({
        queryKey: ["dataset-format-versions", selectedDatasetId, selectedVersionId]
      });
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "格式转换触发失败";
      setFeedback({ type: "error", text: message });
    }
  });

  const activateMutation = useMutation({
    mutationFn: (formatId: number) => {
      if (selectedDatasetId == null || selectedVersionId == null) {
        throw new Error("缺少数据集或版本上下文，无法设置当前格式。");
      }
      return formatApi.activateFormat(selectedDatasetId, selectedVersionId, formatId);
    },
    onSuccess: (record) => {
      setFeedback({ type: "success", text: `${record.format.toUpperCase()} 已设为当前可用版本。` });
      queryClient.invalidateQueries({
        queryKey: ["dataset-format-versions", selectedDatasetId, selectedVersionId]
      });
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "设置失败";
      setFeedback({ type: "error", text: message });
    }
  });

  async function handleDownload(record: DatasetFormatVersion) {
    if (selectedDatasetId == null || selectedVersionId == null) {
      setFeedback({ type: "error", text: "请先选择数据集版本。" });
      return;
    }
    try {
      const blob = await formatApi.downloadExport(selectedDatasetId, selectedVersionId, record.format);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${selectedDatasetId}-v${selectedVersionId}-${record.format}.${
        record.format === "parquet" ? "parquet" : "jsonl"
      }`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setFeedback({ type: "success", text: `已开始下载 ${record.format.toUpperCase()} 格式文件。` });
    } catch (error) {
      const message = error instanceof Error ? error.message : "下载失败";
      setFeedback({ type: "error", text: message });
    }
  }

  const datasetOptions = datasetsQuery.data ?? [];
  const versionOptions = versionsQuery.data ?? [];
  const selectedVersion = useMemo(
    () => versionOptions.find((item) => item.id === selectedVersionId) ?? null,
    [versionOptions, selectedVersionId]
  );
  const formatRecords = formatsQuery.data ?? [];
  const completedFormats = useMemo(
    () => new Set(formatRecords.filter((item) => item.status === "completed").map((item) => item.format)),
    [formatRecords]
  );

  const toggleFormat = (value: DatasetFormatType) => {
    if (completedFormats.has(value)) {
      return;
    }
    setSelectedFormats((prev) => (prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value]));
  };

  const toolbar = (
    <div className="mx-auto w-full max-w-7xl px-10 py-4">
      <DataHubNav />
    </div>
  );

  return (
    <AppShell
      title="格式标准化"
      subtitle="配置数据集导出的标准格式，确保训练与评估流程一致"
      searchPlaceholder="搜索数据集或格式版本"
      primaryAction={{ label: "回到数据导入", to: "/data-hub/upload" }}
      toolbar={toolbar}
    >
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <HeroStat title="已接入数据集" value={String(datasetOptions.length)} />
        <HeroStat title="已启用格式" value={String(formatRecords.filter((item) => item.is_active).length)} />
        <HeroStat title="最近版本" value={selectedVersion ? `v${selectedVersion.version}` : "待选择"} />
        <HeroStat title="待处理任务" value={String(formatRecords.filter((item) => item.status === "running").length)} />
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white px-6 py-6 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">数据集</span>
            <select
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
              value={selectedDatasetId ?? ""}
              onChange={(event) => {
                const datasetId = Number(event.target.value);
                setSelectedDatasetId(Number.isNaN(datasetId) ? null : datasetId);
                setSelectedVersionId(null);
              }}
            >
              <option value="">请选择数据集</option>
              {datasetOptions.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>
                  {dataset.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">数据集版本</span>
            <select
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
              value={selectedVersionId ?? ""}
              onChange={(event) => {
                const versionId = Number(event.target.value);
                setSelectedVersionId(Number.isNaN(versionId) ? null : versionId);
              }}
              disabled={versionOptions.length === 0}
            >
              <option value="">请选择版本</option>
              {versionOptions.map((version) => (
                <option key={version.id} value={version.id}>
                  v{version.version}
                </option>
              ))}
            </select>
          </div>
        </div>
        {!datasetOptions.length && (
          <p className="mt-3 text-xs text-amber-600">暂未接入数据集，请先完成数据导入。</p>
        )}
        {selectedDatasetId && selectedVersionId && (
          <p className="mt-3 text-xs text-slate-400">
            仅对所选数据集版本执行格式转换，已生成的格式会标记为“已生成并启用”。
          </p>
        )}
      </section>

      <section className="space-y-6 rounded-3xl border border-slate-200 bg-white px-6 py-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setActiveTab("options")}
              className={`rounded-2xl px-4 py-2 text-sm font-medium transition ${
                activeTab === "options" ? "bg-sky-500/10 text-sky-600" : "bg-slate-100 text-slate-500"
              }`}
            >
              触发格式转换
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("history")}
              className={`rounded-2xl px-4 py-2 text-sm font-medium transition ${
                activeTab === "history" ? "bg-sky-500/10 text-sky-600" : "bg-slate-100 text-slate-500"
              }`}
            >
              格式版本列表
            </button>
          </div>
          <div className="text-xs text-slate-400">选择数据集后可触发转换并管理格式版本。</div>
        </div>

        {feedback && (
          <div
            className={`rounded-2xl border px-4 py-3 text-sm ${
              feedback.type === "success"
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-rose-200 bg-rose-50 text-rose-700"
            }`}
          >
            {feedback.text}
          </div>
        )}

        {activeTab === "options" ? (
          <div className="space-y-5">
            <div className="grid gap-3 md:grid-cols-3">
              {FORMAT_OPTIONS.map((option) => (
                <FormatOptionCard
                  key={option.value}
                  option={option}
                  checked={selectedFormats.includes(option.value)}
                  disabled={completedFormats.has(option.value)}
                  toggle={toggleFormat}
                />
              ))}
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => {
                  const actionableFormats = selectedFormats.filter((format) => !completedFormats.has(format));
                  if (!selectedDatasetId || !selectedVersionId) {
                    setFeedback({ type: "error", text: "请先选择数据集与版本。" });
                    return;
                  }
                  if (actionableFormats.length === 0) {
                    setFeedback({ type: "error", text: "请选择需要转换的格式，或当前格式已经最新。" });
                    return;
                  }
                  runMutation.mutate(actionableFormats);
                }}
                className="rounded-xl bg-sky-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-500"
                disabled={
                  !selectedDatasetId || !selectedVersionId || runMutation.isPending || selectedFormats.length === 0
                }
              >
                {runMutation.isPending ? "触发中..." : "触发格式转换"}
              </button>
              <button
                type="button"
                onClick={() =>
                  setSelectedFormats(
                    FORMAT_OPTIONS.filter((item) => !completedFormats.has(item.value)).map((item) => item.value)
                  )
                }
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 hover:border-slate-300"
              >
                全选
              </button>
              <button
                type="button"
                onClick={() => setSelectedFormats([])}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 hover:border-slate-300"
              >
                清空
              </button>
            </div>
          </div>
        ) : (
          <FormatTable
            items={formatRecords}
            onDownload={handleDownload}
            onActivate={(record) => activateMutation.mutate(record.id)}
          />
        )}
      </section>
    </AppShell>
  );
}
