
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
});
