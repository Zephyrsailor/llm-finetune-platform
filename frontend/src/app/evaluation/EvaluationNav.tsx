import { NavLink, useLocation } from "react-router-dom";

const BASE_LINKS = [{ to: "/evaluation/suite", label: "标准化评估套件", exact: true }];

function linkClassName(isActive: boolean) {
  const base =
    "inline-flex items-center rounded-md px-3 py-2 text-sm transition-colors border";
  if (isActive) {
    return `${base} border-cyan-500 bg-cyan-500/20 text-cyan-200`;
  }
  return `${base} border-slate-800 bg-slate-900/60 text-slate-300 hover:border-slate-700 hover:text-slate-100`;
}

export function EvaluationNav() {
  const location = useLocation();
  const links = [...BASE_LINKS];
  if (location.pathname.startsWith("/evaluation/reports")) {
    links.push({ to: location.pathname, label: "评估报告", exact: true });
  }
  return (
    <nav
      aria-label="评估模块导航"
      className="flex flex-wrap gap-2 rounded-xl border border-slate-800 bg-slate-950/60 p-3"
    >
      {links.map((link) => (
        <NavLink
          key={link.to}
          to={link.to}
          end={link.exact === true}
          className={({ isActive }) => linkClassName(isActive)}
        >
          {link.label}
        </NavLink>
      ))}
    </nav>
  );
}
