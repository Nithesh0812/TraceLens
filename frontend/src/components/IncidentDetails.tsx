
import { useEffect, useState } from "react";

import AIInvestigation from "./AI_Investigation";
import AIFixProposal from "./AI_FixProposal";

import {
  api,
  type IncidentDetails as IncidentDetailsType,
} from "../services/api";

interface IncidentDetailsProps {
  incidentId: string;
  onClose: () => void;
}

function formatDate(value: string | null) {
  if (!value) return "N/A";

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? "Invalid timestamp"
    : date.toLocaleString();
}

function formatMetric(value: number, type: string) {
  if (type === "high_error_rate") {
    return `${(value * 100).toFixed(2)}%`;
  }

  if (type === "high_latency") {
    return `${value.toFixed(2)} ms`;
  }

  return value.toString();
}

export default function IncidentDetails(props: IncidentDetailsProps) {
  return <IncidentDetailsContent key={props.incidentId} {...props} />;
}

function IncidentDetailsContent({
  incidentId,
  onClose,
}: IncidentDetailsProps) {
  // Incident state
  const [incident, setIncident] =
    useState<IncidentDetailsType | null>(null);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  // Evidence navigation
  const [highlightedEvidenceId, setHighlightedEvidenceId] =
    useState<number | null>(null);

  // Investigation and proposal synchronization
  const [investigationRunning, setInvestigationRunning] =
    useState(false);

  const [proposalRevision, setProposalRevision] =
    useState(0);

  useEffect(() => {
    let cancelled = false;

    async function loadIncident() {
      setLoading(true);
      setError(null);
      setIncident(null);

      try {
        const data = await api.getIncident(incidentId);

        if (!cancelled) {
          setIncident(data);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load incident"
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadIncident();

    return () => {
      cancelled = true;
    };
  }, [incidentId]);

  function handleEvidenceSelect(evidenceId: number) {
    const element = document.getElementById(
      `evidence-${incidentId}-${evidenceId}`
    );

    if (!element) return;

    setHighlightedEvidenceId(evidenceId);

    element.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }

  function handleInvestigationStarted() {
    // Hide the previous fix proposal immediately.
    setInvestigationRunning(true);
  }

  function handleInvestigationFinished() {
    // Allow the proposal panel to reload its saved state.
    setInvestigationRunning(false);

    // Incrementing the revision remounts AIFixProposal.
    setProposalRevision((revision) => revision + 1);
  }

  return (
    <section
      aria-label="Incident details"
      className="rounded-xl border border-slate-700 bg-slate-900 p-6"
    >
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-xl font-semibold">
          Incident Details
        </h2>

        <button
          type="button"
          onClick={onClose}
          className="rounded-lg border border-slate-700 px-4 py-2 text-sm hover:bg-slate-800"
        >
          Close
        </button>
      </div>

      {loading && (
        <p role="status" className="text-slate-400">
          Loading incident details...
        </p>
      )}

      {error && (
        <p role="alert" className="text-red-400">
          {error}
        </p>
      )}

      {incident && (
        <div className="space-y-6">
          {/* Incident overview */}
          <div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-lg font-semibold capitalize">
                {incident.incident_type.replaceAll("_", " ")}
              </h3>

              <span
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  incident.status === "active"
                    ? "bg-red-500/10 text-red-400"
                    : "bg-emerald-500/10 text-emerald-400"
                }`}
              >
                {incident.status}
              </span>
            </div>

            <p className="mt-3 text-sm text-slate-300">
              {incident.message}
            </p>

            <p className="mt-3 break-all font-mono text-xs text-slate-500">
              Incident ID: {incident.id}
            </p>
          </div>

          {/* Incident metrics */}
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <InfoCard
              label="Severity"
              value={incident.severity.toUpperCase()}
            />

            <InfoCard
              label="Metric Value"
              value={formatMetric(
                incident.metric_value,
                incident.incident_type
              )}
            />

            <InfoCard
              label="Occurrences"
              value={incident.occurrences.toString()}
            />

            <InfoCard
              label="Status"
              value={incident.status}
            />
          </div>

          {/* Incident timestamps */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <InfoCard
              label="Detected At"
              value={formatDate(incident.created_at)}
            />

            <InfoCard
              label="Last Updated"
              value={formatDate(incident.updated_at)}
            />

            <InfoCard
              label="Resolved At"
              value={formatDate(incident.resolved_at)}
            />
          </div>

          {/* Correlated log evidence */}
          <div>
            <h3 className="mb-4 text-lg font-semibold">
              Correlated Log Evidence

              <span className="ml-2 text-sm font-normal text-slate-400">
                ({incident.correlated_log_count})
              </span>
            </h3>

            {incident.correlated_logs.length === 0 ? (
              <div className="rounded-lg border border-slate-800 bg-slate-950 p-5">
                <p className="text-sm text-slate-400">
                  No correlated log evidence is available
                  for this incident.
                </p>

                <p className="mt-2 text-xs text-slate-500">
                  This does not mean that no application
                  errors occurred.
                </p>
              </div>
            ) : (
              <div className="max-h-96 space-y-3 overflow-y-auto">
                {incident.correlated_logs.map((log) => (
                  <div
                    key={log.id}
                    id={`evidence-${incidentId}-${log.id}`}
                    className={`scroll-mt-8 rounded-lg border bg-slate-950 p-4 transition-colors ${
                      highlightedEvidenceId === log.id
                        ? "border-blue-500 bg-blue-950/30"
                        : "border-slate-800"
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <span
                        className={`rounded px-2 py-1 text-xs font-semibold ${
                          log.level.toUpperCase() === "ERROR"
                            ? "bg-red-500/10 text-red-400"
                            : log.level.toUpperCase() === "WARNING"
                              ? "bg-amber-500/10 text-amber-400"
                              : "bg-slate-800 text-slate-300"
                        }`}
                      >
                        {log.level}
                      </span>

                      <span className="text-xs text-slate-500">
                        {formatDate(log.timestamp)}
                      </span>
                    </div>

                    <p className="mt-3 whitespace-pre-wrap break-words font-mono text-sm text-slate-300">
                      {log.message}
                    </p>

                    <p className="mt-3 text-xs text-slate-500">
                      Time offset from incident:{" "}
                      {log.seconds_from_incident.toFixed(2)}s
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* AI Investigation */}
          <AIInvestigation
            key={incidentId}
            incidentId={incidentId}
            onEvidenceSelect={handleEvidenceSelect}
            onInvestigationStarted={handleInvestigationStarted}
            onInvestigationFinished={handleInvestigationFinished}
          />

          {/* AI Fix Proposal */}
          {investigationRunning ? (
            <div
              role="status"
              className="rounded-xl border border-amber-800 bg-amber-950/20 p-5"
            >
              <p className="text-sm font-semibold text-amber-400">
                AI Investigation in Progress
              </p>

              <p className="mt-2 text-sm text-slate-300">
                Fix proposals are temporarily hidden while
                the incident is being re-investigated.
              </p>
            </div>
          ) : (
            <AIFixProposal
              key={`${incidentId}-${proposalRevision}`}
              incidentId={incidentId}
              onEvidenceSelect={handleEvidenceSelect}
            />
          )}
        </div>
      )}
    </section>
  );
}

function InfoCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
      <p className="text-xs text-slate-500">
        {label}
      </p>

      <p className="mt-2 break-words text-sm font-semibold text-white">
        {value}
      </p>
    </div>
  );
}
