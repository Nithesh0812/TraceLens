
import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import { api, ApiError } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("API error handling", () => {
  it("uses the backend error detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: "LLM provider is not configured",
          }),
          {
            status: 503,
            headers: {
              "Content-Type": "application/json",
            },
          }
        )
      )
    );

    await expect(
      api.runInvestigation("incident-1")
    ).rejects.toMatchObject({
      status: 503,
      message: "LLM provider is not configured",
    });
  });

  it("handles a non-JSON server error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("Bad Gateway", { status: 502 })
      )
    );

    await expect(
      api.runInvestigation("incident-1")
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("returns null for a missing saved report", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: "No investigation found for this incident",
          }),
          { status: 404 }
        )
      )
    );

    await expect(
      api.getInvestigation("incident-1")
    ).resolves.toBeNull();
  });

  it("retrieves a saved fix proposal", async () => {
    const savedProposal = {
      incident_id: "incident-1",
      status: "proposed",
      proposal: {
        title: "Investigate database connectivity",
        description: "Review database connection failures.",
        rationale: "Connection failures may contribute to errors.",
        confidence: "medium",
        risk_level: "low",
        evidence_ids: [1],
        proposed_steps: ["Inspect connection pool metrics"],
        validation_steps: ["Check HTTP error rates"],
        rollback_steps: ["Restore previous settings"],
      },
      warnings: ["Human review required"],
      requires_human_review: true,
    };

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(savedProposal), {
          status: 200,
          headers: {
            "Content-Type": "application/json",
          },
        })
      )
    );

    const result = await api.getFixProposal("incident-1");

    expect(result).toEqual(savedProposal);
  });

  it("returns null when no fix proposal exists", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: "No fix proposal found",
          }),
          { status: 404 }
        )
      )
    );

    await expect(
      api.getFixProposal("incident-1")
    ).resolves.toBeNull();
  });

  it("generates a fix proposal using POST", async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          incident_id: "incident-1",
          status: "needs_more_evidence",
          proposal: null,
          warnings: [],
          requires_human_review: true,
        }),
        { status: 200 }
      )
    );

    vi.stubGlobal("fetch", mockFetch);

    const result = await api.generateFixProposal("incident-1");

    expect(result.status).toBe("needs_more_evidence");

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/incidents/incident-1/propose-fix",
      expect.objectContaining({
        method: "POST",
      })
    );
  });

  it("handles a missing investigation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: "Incident must be investigated first",
          }),
          { status: 409 }
        )
      )
    );

    await expect(
      api.generateFixProposal("incident-1")
    ).rejects.toMatchObject({
      status: 409,
      message: "Incident must be investigated first",
    });
  });

});
