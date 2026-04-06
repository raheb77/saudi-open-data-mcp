import { NavLink } from "react-router-dom";
import { ar } from "../i18n/ar";

const NAV_LINKS: ReadonlyArray<{ to: string; label: string }> = [
  { to: "/", label: ar.app.nav.home },
  { to: "/query", label: ar.app.nav.query },
  { to: "/status", label: ar.app.nav.systemStatus },
];

interface HeaderProps {
  role: "viewer" | "operator" | "admin";
}

const ROLE_LABEL: Record<HeaderProps["role"], string> = {
  viewer: ar.app.role.viewer,
  operator: ar.app.role.operator,
  admin: ar.app.role.admin,
};

export function Header({ role }: HeaderProps) {
  return (
    <header className="border-b border-ink-300 bg-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div className="flex flex-col">
          <h1 className="text-base font-semibold text-ink-900">
            {ar.app.title}
          </h1>
          <p className="text-xs text-ink-500">{ar.app.subtitle}</p>
        </div>

        <nav aria-label={ar.app.title}>
          <ul className="flex items-center gap-2">
            {NAV_LINKS.map((link) => (
              <li key={link.to}>
                <NavLink
                  to={link.to}
                  end={link.to === "/"}
                  className={({ isActive }) =>
                    `rounded-md px-3 py-1.5 text-sm font-medium transition ${
                      isActive
                        ? "bg-ink-900 text-white"
                        : "text-ink-700 hover:bg-ink-100"
                    }`
                  }
                >
                  {link.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-ink-500">{ar.app.role.label}:</span>
          <span className="rounded-full bg-ink-100 px-2 py-0.5 font-medium text-ink-900">
            {ROLE_LABEL[role]}
          </span>
          <span className="id-mono text-ink-500">{role}</span>
        </div>
      </div>
    </header>
  );
}
