import { ar } from "../i18n/ar";
import { getLimitedPracticalMeaning } from "../lib/statePresentation";

// Shared "state" blocks: distinct rendering for empty / limited / stale /
// failed / missing / unauthorized. Per the Phase 5 rules, these must
// never collapse into a single generic "something went wrong" panel.

interface BaseStateProps {
  title: string;
  body: string;
  children?: React.ReactNode;
  tone?: "neutral" | "warn" | "bad";
  testId?: string;
  liveRole?: "status" | "alert";
  ariaLive?: "polite" | "assertive";
}

const TONE_CLASSES: Record<NonNullable<BaseStateProps["tone"]>, string> = {
  neutral: "state-tone-neutral",
  warn: "state-tone-warn",
  bad: "state-tone-bad",
};

function StateBlock({
  title,
  body,
  children,
  tone = "neutral",
  testId,
  liveRole = "status",
  ariaLive = liveRole === "alert" ? "assertive" : "polite",
}: BaseStateProps) {
  return (
    <section
      data-testid={testId}
      className={`rounded-lg border px-4 py-4 ${TONE_CLASSES[tone]}`}
      role={liveRole}
      aria-live={ariaLive}
      aria-atomic="true"
    >
      <h3 className="text-sm font-semibold">{title}</h3>
      {body && <p className="mt-1 text-sm leading-relaxed">{body}</p>}
      {children && <div className="mt-3 text-sm">{children}</div>}
    </section>
  );
}

export function EmptyState() {
  return (
    <section
      data-testid="state-empty"
      className="flex flex-col items-center justify-center rounded-lg border border-ink-300 bg-ink-50 px-6 py-12 text-center"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <span className="text-4xl" aria-hidden="true">🔍</span>
      <h3 className="mt-4 text-base font-semibold text-ink-900">
        {ar.empty.title}
      </h3>
      <p className="mt-2 max-w-xs text-sm leading-relaxed text-ink-600">
        {ar.empty.body}
      </p>
    </section>
  );
}

export function LoadingState() {
  return (
    <section
      data-testid="state-loading"
      className="flex flex-col items-center justify-center rounded-lg border border-ink-300 bg-ink-50 px-6 py-12 text-center"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <span className="text-2xl animate-pulse" aria-hidden="true">◠ ◡ ◠</span>
      <h3 className="mt-4 text-sm font-semibold text-ink-700">
        {ar.state.loading}
      </h3>
    </section>
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
      <div className="state-tone-warn rounded-md border bg-white/70 px-3 py-2">
        <p className="text-xs font-semibold">{ar.limited.practicalMeaningLabel}</p>
        <p className="mt-1 text-sm leading-relaxed">
          {getLimitedPracticalMeaning(limitations)}
        </p>
      </div>
      {limitations.length > 0 && (
        <>
          <p className="text-tone-warn text-xs font-medium">
            {ar.limited.limitationsLabel}
          </p>
          <ul className="mt-1 list-disc space-y-1 ps-5">
            {limitations.map((entry) => (
              <li key={entry} className="id-mono text-tone-warn">
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
      liveRole="alert"
    />
  );
}

function FailureDetails({
  stage,
  errorType,
  message,
}: {
  stage?: string | null;
  errorType?: string | null;
  message?: string | null;
}) {
  if (!stage && !errorType && !message) {
    return null;
  }

  return (
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
      {message && <p className="mt-1">{message}</p>}
    </dl>
  );
}

export function DegradedState({
  title,
  body,
  stage,
  errorType,
  message,
  children,
  testId = "state-degraded",
}: {
  title: string;
  body: string;
  stage?: string | null;
  errorType?: string | null;
  message?: string | null;
  children?: React.ReactNode;
  testId?: string;
}) {
  return (
    <StateBlock
      title={title}
      body={body}
      tone="warn"
      testId={testId}
      liveRole="alert"
    >
      <FailureDetails stage={stage} errorType={errorType} message={message} />
      {children}
    </StateBlock>
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
    <section
      data-testid="state-failed"
      className="state-tone-bad flex flex-col items-center justify-center rounded-lg border px-6 py-12 text-center"
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
    >
      <span className="text-4xl" aria-hidden="true">⚠️</span>
      <h3 className="mt-4 text-base font-semibold">{ar.error.title}</h3>
      <p className="mt-2 max-w-sm text-sm leading-relaxed">{ar.error.body}</p>
      {(stage || errorType || message) && (
        <div className="mt-4 w-full max-w-sm text-start text-sm">
          <FailureDetails stage={stage} errorType={errorType} message={message} />
        </div>
      )}
    </section>
  );
}
