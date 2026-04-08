import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { HomePage } from "./pages/HomePage";
import { QueryPage } from "./pages/QueryPage";
import { SystemStatusPage } from "./pages/SystemStatusPage";

export function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route element={<AppShell role={null} />}>
          <Route index element={<HomePage />} />
          <Route path="/query" element={<QueryPage />} />
          <Route path="/status" element={<SystemStatusPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}
