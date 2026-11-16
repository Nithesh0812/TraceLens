import {render,screen,fireEvent,waitFor,} from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AIInvestigation from "./AI_Investigation";
import { api, type VerificationResult } from "../services/api";


vi.mock("../services/api", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("../services/api")>();

  return {
    ...actual,
    api: {
      ...actual.api,
      getInvestigation: vi.fn(),
      runInvestigation: vi.fn(),
    },
  };
});


const sampleReport: VerificationResult = {
  report: {
    summary: "Database timeouts coincide with HTTP errors.",
    possible_cause: "Database connection exhaustion may be contributing.",
    confidence: "medium",
    evidence_ids: [1, 2, 3],
    next_steps: ["Inspect database connection pool usage."],
    insufficient_evidence: false,
  },
  citation_ids_valid: true,
  verified_evidence_ids: [1, 2, 3],
  warnings: ["Causality is not independently verified."],
  requires_human_review: true,
};

describe("AI Investigation", () => {
  it("shows the empty state when no saved report exists", async () => {
    vi.mocked(api.getInvestigation).mockResolvedValue(null);

    render(<AIInvestigation incidentId="incident-1" />);

    expect(
      await screen.findByText("No saved investigation is available.")
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: "Run Investigation" })
    ).toBeEnabled();
  });

  it("displays a previously saved investigation", async () => {
    vi.mocked(api.getInvestigation).mockResolvedValue(sampleReport);

    render(<AIInvestigation incidentId="incident-1" />);

    expect(
      await screen.findByText(
        "Database timeouts coincide with HTTP errors."
      )
    ).toBeInTheDocument();

    expect(screen.getByText("Human Review Required"))
      .toBeInTheDocument();

    expect(screen.getByText("MEDIUM"))
      .toBeInTheDocument();

    expect(screen.getByText("Evidence #1"))
      .toBeInTheDocument();

    expect(screen.getByText("Evidence #2"))
      .toBeInTheDocument();

    expect(screen.getByText("Evidence #3"))
      .toBeInTheDocument();

    expect(api.runInvestigation).not.toHaveBeenCalled();
  });

  it("runs an investigation when the button is clicked", async () => {
    vi.mocked(api.getInvestigation).mockResolvedValue(null);
    vi.mocked(api.runInvestigation).mockResolvedValue(sampleReport);

    render(<AIInvestigation incidentId="incident-1" />);

    const button = await screen.findByRole("button", {
      name: "Run Investigation",
    });

    fireEvent.click(button);

    expect(api.runInvestigation).toHaveBeenCalledWith("incident-1",expect.any(AbortSignal));

    expect(
      await screen.findByText(
        "Database timeouts coincide with HTTP errors."
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: "Run Again" })
    ).toBeEnabled();
  });

it("ignores an old investigation after switching incidents", async () => {
  vi.mocked(api.getInvestigation).mockResolvedValue(null);

  let resolveOldRequest!: (value: VerificationResult) => void;

  const oldRequest = new Promise<VerificationResult>((resolve) => {
    resolveOldRequest = resolve;
  });

  vi.mocked(api.runInvestigation).mockReturnValue(oldRequest);

  const { rerender } = render(
    <AIInvestigation
      key="incident-A"
      incidentId="incident-A"
    />
  );

  const button = await screen.findByRole("button", {
    name: "Run Investigation",
  });

  fireEvent.click(button);

  await waitFor(() => {
    expect(api.runInvestigation).toHaveBeenCalledWith(
      "incident-A",
      expect.any(AbortSignal)
    );
  });

  // Changing the key forces React to mount a fresh component.
  rerender(
    <AIInvestigation
      key="incident-B"
      incidentId="incident-B"
    />
  );

  // The old request completes after switching incidents.
  resolveOldRequest(sampleReport);

  // The new incident should display its own initial state.
  await screen.findByText(
    "No saved investigation is available."
  );

  await waitFor(() => {
    expect(
      screen.getByRole("button", {
        name: "Run Investigation",
      })
    ).toBeEnabled();
  });

  // The old investigation must never appear.
  expect(
    screen.queryByText(
      "Database timeouts coincide with HTTP errors."
    )
  ).not.toBeInTheDocument();
});


  it("navigates to selected evidence", async () => {
    const onEvidenceSelect = vi.fn();

    vi.mocked(api.getInvestigation).mockResolvedValue(
    sampleReport
    );

    render(
    <AIInvestigation
      incidentId="incident-1"
      onEvidenceSelect={onEvidenceSelect}
    />
    );

  const evidenceButton = await screen.findByRole(
    "button",
    { name: "Evidence #2" }
  );

  fireEvent.click(evidenceButton);

  expect(onEvidenceSelect).toHaveBeenCalledExactlyOnceWith(2);
  });


  it("notifies the parent when an investigation reruns", async () => {
    const onStarted = vi.fn();
    const onFinished = vi.fn();

    vi.mocked(api.getInvestigation).mockResolvedValue(sampleReport);
    vi.mocked(api.runInvestigation).mockResolvedValue(sampleReport);

    render(
      <AIInvestigation
        incidentId="incident-1"
        onInvestigationStarted={onStarted}
        onInvestigationFinished={onFinished}
      />
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Run Again" })
    );

    expect(onStarted).toHaveBeenCalledOnce();
    await waitFor(() => expect(onFinished).toHaveBeenCalledOnce());
  });

  it("notifies the parent on investigation failure", async () => {
    const onStarted = vi.fn();
    const onFinished = vi.fn();

    vi.mocked(api.getInvestigation).mockResolvedValue(null);
    vi.mocked(api.runInvestigation).mockRejectedValue(
      new Error("Backend failed")
    );

    render(
      <AIInvestigation
        incidentId="incident-1"
        onInvestigationStarted={onStarted}
        onInvestigationFinished={onFinished}
      />
    );

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Run Investigation",
      })
    );

    expect(onStarted).toHaveBeenCalledOnce();
    await waitFor(() => expect(onFinished).toHaveBeenCalledOnce());
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Backend failed"
    );
  });

});