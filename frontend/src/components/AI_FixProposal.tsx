
import { useEffect, useRef, useState } from "react";

import {
  api,
  ApiError,
  type FixProposalResult,
} from "../services/api";

interface AIFixProposalProps {
  incidentId: string;
  onEvidenceSelect?: (evidenceId: number) => void;
}

const confidenceColors = {
  low: "text-red-400",
  medium: "text-amber-400",
  high: "text-emerald-400",
};

const riskColors = {
  low: "text-emerald-400",
  medium: "text-amber-400",
  high: "text-red-400",
};

export default function AIFixProposal({
  incidentId,
  onEvidenceSelect,
}: AIFixProposalProps) {
  const [result, setResult] =
    useState<FixProposalResult | null>(null);

  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generateController = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    api
      .getFixProposal(incidentId, controller.signal)
      .then((savedResult) => {
        if (active && !controller.signal.aborted) {
          setResult(savedResult);
        }
      })
      .catch((err: unknown) => {
        if (!active || controller.signal.aborted) return;

        setError(
          err instanceof Error
            ? err.message
            : "Unable to load saved proposal"
        );
      })
      .finally(() => {
        if (active && !controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
      controller.abort();
      generateController.current?.abort();
    };
  }, [incidentId]);

  async function handleGenerate() {
    if (generating || loading) return;

    generateController.current?.abort();

    const controller = new AbortController();
    generateController.current = controller;

    setGenerating(true);
    setError(null);
    setResult(null);

    try {
      const generated = await api.generateFixProposal(
        incidentId,
        controller.signal
      );

      if (!controller.signal.aborted) {
        setResult(generated);
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;

      if (err instanceof ApiError) {
        if (err.status === 409) {
          setError(
            "The investigation is missing or outdated. " +
            "Run the AI investigation before generating a fix."
          );
        } else if (err.status === 503) {
          setError(
            "The AI provider is not configured or is unavailable."
          );
        } else if (err.status === 502) {
          setError(
            "Fix proposal generation failed. " +
            "Check backend logs and try again."
          );
        } else if (err.status === 404) {
          setError("This incident could not be found.");
        } else {
          setError(err.message);
        }
      } else {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to generate fix proposal"
        );
      }
    } finally {
      if (!controller.signal.aborted) {
        setGenerating(false);
      }

      if (generateController.current === controller) {
        generateController.current = null;
      }
    }
  }

  const proposal = result?.proposal;

  return (
    <section
      aria-label="AI fix proposal"
      className="rounded-xl border border-slate-700 bg-slate-950 p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">
            AI Fix Proposal
          </h3>

          <p className="mt-1 text-xs text-slate-500">
            Evidence-grounded remediation recommendations
          </p>
        </div>

        <button
          type="button"
          onClick={() => void handleGenerate()}
          disabled={loading || generating}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {generating
            ? "Generating..."
            : proposal
              ? "Regenerate Proposal"
              : "Generate Fix Proposal"}
        </button>
      </div>

      {loading && (
        <p role="status" className="mt-5 text-sm text-slate-400">
          Checking for saved fix proposals...
        </p>
      )}

      {generating && (
        <p role="status" className="mt-5 text-sm text-blue-400">
          Analyzing verified findings and validating remediation safety...
        </p>
      )}

      {error && (
        <div
          role="alert"
          className="mt-5 rounded-lg border border-red-900 bg-red-950/30 p-4 text-sm text-red-400"
        >
          {error}
        </div>
      )}

      {!loading && !result && !error && (
        <div className="mt-5 rounded-lg border border-slate-800 p-5">
          <p className="text-sm text-slate-400">
            No saved fix proposal is available.
          </p>

          <p className="mt-2 text-xs text-slate-500">
            Run an AI investigation first, then generate
            an evidence-grounded remediation proposal.
          </p>
        </div>
      )}

      {result?.status === "needs_more_evidence" && (
        <div className="mt-5 rounded-lg border border-amber-800 bg-amber-950/20 p-4">
          <h4 className="font-semibold text-amber-400">
            Insufficient Evidence
          </h4>

          <p className="mt-2 text-sm text-slate-300">
            TraceLens cannot recommend a specific fix
            from the available verified evidence.
          </p>
        </div>
      )}

      {result?.status === "proposed" && proposal && (
        <div className="mt-6 space-y-5">
          <div className="rounded-lg border border-amber-800 bg-amber-950/20 p-4">
            <p className="text-sm font-semibold text-amber-400">
              Human Review Required
            </p>

            <p className="mt-1 text-xs text-slate-300">
              This recommendation is advisory only.
              No changes have been executed.
            </p>
          </div>

          <div>
            <h4 className="text-lg font-semibold text-white">
              {proposal.title}
            </h4>

            <p className="mt-3 whitespace-pre-wrap text-sm text-slate-300">
              {proposal.description}
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <InfoBox
              title="Confidence"
              value={proposal.confidence.toUpperCase()}
              valueColor={confidenceColors[proposal.confidence]}
            />

            <InfoBox
              title="Risk Level"
              value={proposal.risk_level.toUpperCase()}
              valueColor={riskColors[proposal.risk_level]}
            />
          </div>

          <div className="rounded-lg border border-slate-800 p-4">
            <h4 className="text-sm font-semibold text-slate-300">
              Why This Fix Is Proposed
            </h4>

            <p className="mt-2 whitespace-pre-wrap text-sm text-slate-400">
              {proposal.rationale}
            </p>
          </div>

          <StepList
            title="Proposed Remediation Steps"
            steps={proposal.proposed_steps}
          />

          <StepList
            title="Validation Steps"
            steps={proposal.validation_steps}
          />

          <StepList
            title="Rollback Guidance"
            steps={proposal.rollback_steps}
          />

          <div>
            <h4 className="mb-3 text-sm font-semibold text-slate-300">
              Supporting Evidence
            </h4>

            <div className="flex flex-wrap gap-2">
              {proposal.evidence_ids.map((id) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => onEvidenceSelect?.(id)}
                  disabled={!onEvidenceSelect}
                  className="rounded-md border border-slate-700 px-3 py-1 font-mono text-xs text-blue-400 transition hover:border-blue-500 hover:bg-blue-950/30 disabled:cursor-default disabled:text-slate-400"
                  title={`View supporting log evidence ${id}`}
                >
                  Evidence #{id}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {result && result.warnings.length > 0 && (
        <div className="mt-5 rounded-lg border border-amber-900 p-4">
          <h4 className="font-semibold text-amber-400">
            Verification Warnings
          </h4>

          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-300">
            {result.warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function StepList({
  title,
  steps,
}: {
  title: string;
  steps: string[];
}) {
  return (
    <div>
      <h4 className="mb-3 text-sm font-semibold text-slate-300">
        {title}
      </h4>

      <ol className="list-decimal space-y-2 pl-5 text-sm text-slate-300">
        {steps.map((step, index) => (
          <li key={index}>{step}</li>
        ))}
      </ol>
    </div>
  );
}

function InfoBox({
  title,
  value,
  valueColor,
}: {
  title: string;
  value: string;
  valueColor: string;
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <p className="text-xs text-slate-500">
        {title}
      </p>

      <p className={`mt-2 font-semibold ${valueColor}`}>
        {value}
      </p>
    </div>
  );
}
