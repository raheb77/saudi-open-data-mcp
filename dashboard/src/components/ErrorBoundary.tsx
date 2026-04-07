import React from "react";
import { ar } from "../i18n/ar";

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    console.error("dashboard.render_error", error);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-ink-50">
          <main className="mx-auto max-w-3xl px-4 py-10">
            <section
              className="rounded-xl border border-rose-300 bg-rose-50 px-5 py-6 text-rose-900 shadow-sm"
              role="alert"
              data-testid="error-boundary-fallback"
            >
              <h1 className="text-base font-semibold">{ar.app.renderError.title}</h1>
              <p className="mt-2 text-sm leading-relaxed">
                {ar.app.renderError.body}
              </p>
            </section>
          </main>
        </div>
      );
    }

    return this.props.children;
  }
}
