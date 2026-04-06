import { ar } from "../i18n/ar";

// Shared "state" blocks: distinct rendering for empty / limited / stale /
// failed / missing / unauthorized. Per the Phase 5 rules, these must
// never collapse into a single generic "something went wrong" panel.

interface BaseStateProps {
  title: string;
  body: string;
  children?: React.ReactNode;
  tone?: "neutral" | "warn" | "bad";
  testId?: string;
}

const TONE_CLASSES: Record<NonNullable<BaseStateProps["tone"]>, string> = {
  neutral: "border-ink-300 bg-ink-50 text-ink-700",
  warn: "border-amber-300 bg-amber-50 text-amber-900",
  bad: "border-rose-300 bg-rose-50 text-rose-900",
};

function StateBlock({
  title,
  body,
  children,
  tone = "neutral",
  testId,
}: BaseStateProps) {
  return (
    <section
      data-testid={testId}
      className={`rounded-lg border px-4 py-4 ${TONE_CLASSES[tone]}`}
      role="status"
    >
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="mt-1 text-sm leading-relaxed">{body}</p>
      {children && <div className="mt-3 text-sm">{children}</div>}
    </section>
  );
}

export function EmptyState() {
  return (
    <StateBlock
      title={ar.empty.title}
      body={ar.empty.body}
      tone="neutral"
      testId="state-empty"
    />
  );
}

export function LoadingState() {
  return (
    <StateBlock
      title={ar.state.loading}
      body=""
      tone="neutral"
      testId="state-loading"
    />
  );
}

export function MissingState() {
  return (
    <StateBlock
      title={ar.missing.title}
      body={ar.missing.body}
      tone="neutral"
      testId="state-missing"
    />
  );
}

export function SnapshotMissingState() {
  return (
    <StateBlock
      title={ar.snapshotMissing.title}
      body={ar.snapshotMissing.body}
      tone="neutral"
      testId="state-snapshot-missing"
    />
  );
}

export function LimitedState({ limitations }: { limitations: string[] }) {
  return (
    <StateBlock
      title={ar.limited.title}
      body={ar.limited.body}
      tone="warn"
      testId="state-limited"
    >
      {limitations.length > 0 && (
        <>
          <p className="text-xs font-medium text-amber-900">
            {ar.limited.limitationsLabel}
          </p>
          <ul className="mt-1 list-disc space-y-1 ps-5">
            {limitations.map((entry) => (
              <li key={entry} className="id-mono text-amber-900">
                {entry}
              </li>
            ))}
          </ul>
        </>
      )}
    </StateBlock>
  );
}

export function StaleState() {
  return (
    <StateBlock
      title={ar.stale.title}
      body={ar.stale.body}
      tone="warn"
      testId="state-stale"
    />
  );
}

export function UnauthorizedState() {
  return (
    <StateBlock
      title={ar.unauthorized.title}
      body={ar.unauthorized.body}
      tone="bad"
      testId="state-unauthorized"
    />
  );
}

export function ErrorState({
  stage,
  errorType,
  message,
}: {
  stage?: string | null;
  errorType?: string | null;
  message?: string | null;
}) {
  return (
    <StateBlock
      title={ar.error.title}
      body={ar.error.body}
      tone="bad"
      testId="state-failed"
    >
      <dl className="space-y-1 text-xs">
        {stage && (
          <div className="flex gap-2">
            <dt className="font-semibold">{ar.error.stageLabel}:</dt>
            <dd className="id-mono">{stage}</dd>
          </div>
        )}
        {errorType && (
          <div className="flex gap-2">
            <dt className="font-semibold">{ar.error.typeLabel}:</dt>
            <dd className="id-mono">{errorType}</dd>
          </div>
        )}
        {message && <p className="mt-1 text-rose-900">{message}</p>}
      </dl>
    </StateBlock>
  );
}
