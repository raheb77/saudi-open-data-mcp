import { Outlet } from "react-router-dom";
import { Header } from "./Header";

interface AppShellProps {
  role: "viewer" | "operator" | "admin";
}

export function AppShell({ role }: AppShellProps) {
  return (
    <div className="min-h-screen bg-ink-50">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:right-2 focus:top-2 focus:z-50 focus:rounded focus:bg-ink-900 focus:px-3 focus:py-1 focus:text-white"
      >
        تخطّى إلى المحتوى
      </a>
      <Header role={role} />
      <main id="main" className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
