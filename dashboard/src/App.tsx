import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { HomePage } from "./pages/HomePage";
import { QueryPage } from "./pages/QueryPage";
import { SystemStatusPage } from "./pages/SystemStatusPage";

// The v1 prototype has a single hardcoded role. Role-aware rendering is
// scaffolded so the UI can reflect a capability denial honestly, but the
// dashboard does not invent its own RBAC.
const CURRENT_ROLE = "operator" as const;

export function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route element={<AppShell role={CURRENT_ROLE} />}>
          <Route index element={<HomePage />} />
          <Route path="/query" element={<QueryPage role={CURRENT_ROLE} />} />
          <Route path="/status" element={<SystemStatusPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}
