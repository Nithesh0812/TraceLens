
import { useEffect, useState } from "react";

import {
  api,
  type VerificationResult,
} from "../services/api";

interface AIInvestigationProps {
  incidentId: string;
}

export default function AIInvestigation({
  incidentId,
}: AIInvestigationProps) {
  const [investigation, setInvestigation] =
    useState<VerificationResult | null>(null);

  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    setInvestigation(null);
    setLoading(true);
    setError(null);

    api.getInvestigation(incidentId)
      .then((result) => {
        if (!cancelled) {
          setInvestigation(result);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load investigation"
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [incidentId]);

  async function handleInvestigate() {
    if (running) return;

    setRunning(true);
    setError(null);

    try {
      const result = await api.runInvestigation(incidentId);
      setInvestigation(result);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Investigation failed"
      );
    } finally {
      setRunning(false);
    }
  }

  const report = investigation?.report;

  const confidenceColors = {
    low: "text-red-400",
    medium: "text-amber-400",
    high: "text-emerald-400",
  };

  return (
    <section className="rounded-xl border border-slate-700 bg-slate-950 p-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">
            AI Investigation
          </h3>
          <p className="mt-1 text-xs text-slate-500">
            Evidence-aware incident analysis
          </p>
        </div>

        <button
          type="button"
          onClick={() => void handleInvestigate()}
          disabled={running || loading}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {running
            ? "Investigating..."
            : investigation
              ? "Run Again"
              : "Run Investigation"}
        </button>
      </div>

      {loading && (
        <p role="status" className="mt-5 text-sm text-slate-400">
          Checking for saved investigations...
        </p>
      )}

      {running && (
        <p role="status" className="mt-5 text-sm text-blue-400">
          Analyzing incident evidence and verifying the report...
        </p>
      )}

      {error && (
        <div
          role="alert"
          className="mt-5 rounded-lg border border-red-900 bg-red-950/30 p-4 text-sm text-red-400"
        >
          {error}
          <p className="mt-2 text-xs">
            Verify backend connectivity and LLM configuration.
          </p>
        </div>
      )}

      {!loading && !investigation && !error && (
        <div className="mt-5 rounded-lg border border-slate-800 p-5">
          <p className="text-sm text-slate-400">
            No saved investigation is available.
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Select Run Investigation to analyze this incident.
          </p>
        </div>
      )}

      {investigation && report && (
        <div className="mt-6 space-y-5">
          {investigation.requires_human_review && (
            <div className="rounded-lg border border-amber-800 bg-amber-950/20 p-4">
              <p className="text-sm font-semibold text-amber-400">
                Human Review Required
              </p>
              <p className="mt-1 text-xs text-slate-300">
                AI-generated findings are hypotheses and
                should be reviewed before remediation.
              </p>
            </div>
          )}

          {report.insufficient_evidence && (
            <div className="rounded-lg border border-amber-800 bg-amber-950/20 p-4">
              <p className="font-semibold text-amber-400">
                Insufficient Evidence
              </p>
              <p className="mt-2 text-sm text-slate-300">
                Available evidence does not establish a
                reliable root cause.
              </p>
            </div>
          )}

          <div>
            <h4 className="text-sm font-semibold text-slate-400">
              Investigation Summary
            </h4>
            <p className="mt-2 whitespace-pre-wrap text-sm text-slate-200">
              {report.summary}
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <InfoBox
              title="Confidence"
              value={report.confidence.toUpperCase()}
              valueColor={confidenceColors[report.confidence]}
            />

            <InfoBox
              title="Verified Citations"
              value={investigation.verified_evidence_ids.length.toString()}
            />

            <InfoBox
              title="Citation IDs Valid"
              value={
                investigation.citation_ids_valid
                  ? "YES"
                  : "NO"
              }
            />
          </div>

          <div className="rounded-lg border border-slate-800 p-4">
            <h4 className="text-sm font-semibold text-slate-300">
              Possible Root Cause
            </h4>

            <p className="mt-2 text-sm text-slate-400">
              {report.possible_cause ??
                "No supported root-cause hypothesis available."}
            </p>
          </div>

          <div>
            <h4 className="mb-3 text-sm font-semibold text-slate-300">
              Recommended Next Steps
            </h4>

            {report.next_steps.length === 0 ? (
              <p className="text-sm text-slate-500">
                No recommendations available.
              </p>
            ) : (
              <ol className="list-decimal space-y-2 pl-5 text-sm text-slate-300">
                {report.next_steps.map((step, index) => (
                  <li key={index}>{step}</li>
                ))}
              </ol>
            )}
          </div>

          <div>
            <h4 className="mb-2 text-sm font-semibold text-slate-300">
              Cited Evidence IDs
            </h4>

            {investigation.verified_evidence_ids.length === 0 ? (
              <p className="text-sm text-slate-500">
                No verified evidence citations.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {investigation.verified_evidence_ids.map(
                  (id) => (
                    <span
                      key={id}
                      className="rounded-md border border-slate-700 px-3 py-1 font-mono text-xs text-slate-300"
                    >
                      Evidence #{id}
                    </span>
                  )
                )}
              </div>
            )}
          </div>

          {investigation.warnings.length > 0 && (
            <div className="rounded-lg border border-amber-900 p-4">
              <h4 className="font-semibold text-amber-400">
                Verification Warnings
              </h4>

              <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-300">
                {investigation.warnings.map((warning, index) => (
                  <li key={index}>{warning}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function InfoBox({
  title,
  value,
  valueColor = "text-white",
}: {
  title: string;
  value: string;
  valueColor?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <p className="text-xs text-slate-500">{title}</p>
      <p className={`mt-2 font-semibold ${valueColor}`}>
        {value}
      </p>
    </div>
  );
}
