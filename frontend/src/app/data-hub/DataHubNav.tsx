import { NavLink } from "react-router-dom";

const LINKS = [
  { to: "/data-hub/upload", label: "数据导入" },
  { to: "/data-hub/cleaning", label: "清洗与模板" },
  { to: "/data-hub/quality", label: "质量评估" },
  { to: "/data-hub/formats", label: "格式标准化" }
];

function linkClassName(isActive: boolean) {
  const base =
    "inline-flex items-center rounded-lg border px-4 py-2 text-sm font-medium transition-colors";
  if (isActive) {
    return `${base} border-blue-500 bg-blue-50 text-blue-600`;
  }
  return `${base} border-transparent bg-white text-slate-500 hover:border-slate-200 hover:bg-slate-100 hover:text-slate-700`;
}

export function DataHubNav() {
  return (
    <nav
      aria-label="数据工作台导航"
      className="flex flex-wrap gap-2 rounded-xl border border-slate-200 bg-slate-50/80 p-3"
    >
      {LINKS.map((link) => (
        <NavLink
          key={link.to}
          to={link.to}
          className={({ isActive }) => linkClassName(isActive)}
          end={link.to === "/data-hub/upload"}
        >
          {link.label}
        </NavLink>
      ))}
    </nav>
  );
}
