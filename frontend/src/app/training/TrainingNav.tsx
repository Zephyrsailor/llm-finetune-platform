import { NavLink } from "react-router-dom";

const LINKS: Array<{ to: string; label: string; exact?: boolean }> = [
  { to: "/training/templates", label: "模板库", exact: true },
  { to: "/training/wizard", label: "向导编排" },
  { to: "/training/monitor", label: "实时监控" },
  { to: "/training/snapshots", label: "快照管理" },
  { to: "/training/experiments", label: "实验对比" }
];

function linkClass(isActive: boolean) {
  const base =
    "inline-flex items-center rounded-lg border px-4 py-2 text-sm font-medium transition-colors";
  if (isActive) {
    return `${base} border-purple-500 bg-purple-50 text-purple-600`;
  }
  return `${base} border-transparent bg-white text-slate-500 hover:border-slate-200 hover:bg-slate-100 hover:text-slate-700`;
}

export function TrainingNav() {
  return (
    <nav aria-label="训练模块导航" className="flex flex-wrap gap-2 rounded-xl border border-slate-200 bg-slate-50/80 p-3">
      {LINKS.map((link) => (
        <NavLink key={link.to} to={link.to} end={link.exact === true} className={({ isActive }) => linkClass(isActive)}>
          {link.label}
        </NavLink>
      ))}
    </nav>
  );
}
