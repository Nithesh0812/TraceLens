
import {
  render,
  screen,
  fireEvent,
  waitFor,
} from "@testing-library/react";

import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import AIFixProposal from "./AI_FixProposal";

import {
  api,
  ApiError,
  type FixProposalResult,
} from "../services/api";

vi.mock("../services/api", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("../services/api")>();

  return {
    ...actual,
    api: {
      ...actual.api,
      getFixProposal: vi.fn(),
      generateFixProposal: vi.fn(),
    },
  };
});

const sampleResult: FixProposalResult = {
  incident_id: "incident-1",
  status: "proposed",
  proposal: {
    title: "Investigate database connectivity",
    description: "Inspect database connection failures.",
    rationale: "Connection errors coincide with HTTP errors.",
    confidence: "medium",
    risk_level: "medium",
    evidence_ids: [1, 2],
    proposed_steps: [
      "Inspect database connection pool utilization",
    ],
    validation_steps: [
      "Verify that HTTP error rates decrease",
    ],
    rollback_steps: [
      "Restore previous settings if modified",
    ],
  },
  warnings: [
    "Causality and remediation effectiveness are not verified.",
  ],
  requires_human_review: true,
};

beforeEach(() => {
  vi.resetAllMocks();
});

describe("AI Fix Proposal", () => {
  it("shows the empty state", async () => {
    vi.mocked(api.getFixProposal).mockResolvedValue(null);

    render(<AIFixProposal incidentId="incident-1" />);

    expect(
      await screen.findByText(
        "No saved fix proposal is available."
      )
    ).toBeInTheDocument();
  });

  it("displays a saved proposal", async () => {
    vi.mocked(api.getFixProposal).mockResolvedValue(
      sampleResult
    );

    render(<AIFixProposal incidentId="incident-1" />);

    expect(
      await screen.findByText(
        "Investigate database connectivity"
      )
    ).toBeInTheDocument();

    expect(
      screen.getByText("Human Review Required")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Proposed Remediation Steps")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Validation Steps")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Rollback Guidance")
    ).toBeInTheDocument();

    expect(api.generateFixProposal).not.toHaveBeenCalled();
  });

  it("generates a proposal", async () => {
    vi.mocked(api.getFixProposal).mockResolvedValue(null);

    vi.mocked(api.generateFixProposal).mockResolvedValue(
      sampleResult
    );

    render(<AIFixProposal incidentId="incident-1" />);

    const button = await screen.findByRole(
      "button",
      { name: "Generate Fix Proposal" }
    );

    fireEvent.click(button);

    expect(
      await screen.findByText(
        "Investigate database connectivity"
      )
    ).toBeInTheDocument();

    expect(api.generateFixProposal).toHaveBeenCalledWith(
      "incident-1",
      expect.any(AbortSignal)
    );
  });

  it("shows insufficient evidence", async () => {
    vi.mocked(api.getFixProposal).mockResolvedValue(null);

    vi.mocked(api.generateFixProposal).mockResolvedValue({
      incident_id: "incident-1",
      status: "needs_more_evidence",
      proposal: null,
      warnings: ["Evidence does not support a specific fix."],
      requires_human_review: true,
    });

    render(<AIFixProposal incidentId="incident-1" />);

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Generate Fix Proposal",
      })
    );

    expect(
      await screen.findByText("Insufficient Evidence")
    ).toBeInTheDocument();

    expect(
      screen.queryByText("Proposed Remediation Steps")
    ).not.toBeInTheDocument();
  });

  it("handles a missing investigation", async () => {
    vi.mocked(api.getFixProposal).mockResolvedValue(null);

    vi.mocked(api.generateFixProposal).mockRejectedValue(
      new ApiError(409, "Investigation missing")
    );

    render(<AIFixProposal incidentId="incident-1" />);

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Generate Fix Proposal",
      })
    );

    expect(
      await screen.findByRole("alert")
    ).toHaveTextContent(
      "Run the AI investigation before generating a fix."
    );
  });

  it("navigates to supporting evidence", async () => {
    const onEvidenceSelect = vi.fn();

    vi.mocked(api.getFixProposal).mockResolvedValue(
      sampleResult
    );

    render(
      <AIFixProposal
        incidentId="incident-1"
        onEvidenceSelect={onEvidenceSelect}
      />
    );

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Evidence #2",
      })
    );

    expect(onEvidenceSelect).toHaveBeenCalledWith(2);
  });

  it("ignores old results after switching incidents", async () => {
    let resolveOld!: (value: FixProposalResult) => void;

    const oldRequest = new Promise<FixProposalResult>(
      (resolve) => {
        resolveOld = resolve;
      }
    );

    vi.mocked(api.getFixProposal)
      .mockReturnValueOnce(oldRequest)
      .mockResolvedValueOnce(null);

    const { rerender } = render(
      <AIFixProposal
        key="incident-1"
        incidentId="incident-1"
      />
    );

    rerender(
      <AIFixProposal
        key="incident-2"
        incidentId="incident-2"
      />
    );

    resolveOld(sampleResult);

    await screen.findByText(
      "No saved fix proposal is available."
    );

    await waitFor(() => {
      expect(
        screen.queryByText("Investigate database connectivity")
      ).not.toBeInTheDocument();
    });
  });

  it("hides the old proposal while regenerating", async () => {
    vi.mocked(api.getFixProposal).mockResolvedValue(sampleResult);
    let finish!: (value: FixProposalResult) => void;
    vi.mocked(api.generateFixProposal).mockReturnValue(
      new Promise<FixProposalResult>((resolve) => {
        finish = resolve;
      })
    );

    render(<AIFixProposal incidentId="incident-1" />);
    await screen.findByText("Investigate database connectivity");
    fireEvent.click(
      screen.getByRole("button", { name: "Regenerate Proposal" })
    );

    expect(screen.queryByText("Investigate database connectivity"))
      .not.toBeInTheDocument();
    expect(screen.getByText(/Analyzing verified findings/))
      .toBeInTheDocument();
    finish(sampleResult);
    expect(await screen.findByText("Investigate database connectivity"))
      .toBeInTheDocument();
  });

  it("shows a provider failure without an outdated proposal", async () => {
    vi.mocked(api.getFixProposal).mockResolvedValue(sampleResult);
    vi.mocked(api.generateFixProposal).mockRejectedValue(
      new ApiError(502, "Bad gateway")
    );

    render(<AIFixProposal incidentId="incident-1" />);
    await screen.findByText("Investigate database connectivity");
    fireEvent.click(
      screen.getByRole("button", { name: "Regenerate Proposal" })
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Fix proposal generation failed"
    );
    expect(screen.queryByText("Investigate database connectivity"))
      .not.toBeInTheDocument();
  });

});
