import { describe, expect, it, vi } from "vitest";
import type { AgentRunStatus, CaseDetail } from "../contracts";
import { followCase, MAX_POLLS, POLL_INTERVAL_MS } from "./followCase";

function detailWith(status: AgentRunStatus | null): CaseDetail {
  const runs = status === null ? [] : [{ status }];
  return { agent_runs: runs } as unknown as CaseDetail;
}

function deps(overrides: Partial<Parameters<typeof followCase>[0]>) {
  return {
    stream: vi.fn().mockResolvedValue(undefined),
    refresh: vi.fn().mockResolvedValue(detailWith("running")),
    signal: new AbortController().signal,
    sleep: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

describe("followCase", () => {
  it("refreshes the case on each tool and final event and never polls", async () => {
    const options = deps({
      stream: vi.fn().mockImplementation(async (onEvent) => {
        onEvent({ name: "open", data: "{}" });
        onEvent({ name: "tool", data: "{}" });
        onEvent({ name: "keepalive", data: "{}" });
        onEvent({ name: "final", data: "{}" });
      }),
    });

    await followCase(options);

    expect(options.refresh).toHaveBeenCalledTimes(2);
    expect(options.sleep).not.toHaveBeenCalled();
  });

  it("polls every 3 s when the stream fails and stops on a final status", async () => {
    const refresh = vi
      .fn()
      .mockResolvedValueOnce(detailWith("running"))
      .mockResolvedValueOnce(detailWith(null))
      .mockResolvedValueOnce(detailWith("done"))
      .mockResolvedValue(detailWith("done"));
    const options = deps({ stream: vi.fn().mockRejectedValue(new TypeError("CORS")), refresh });

    await followCase(options);

    expect(refresh).toHaveBeenCalledTimes(3);
    expect(options.sleep).toHaveBeenCalledTimes(3);
    expect(options.sleep).toHaveBeenCalledWith(POLL_INTERVAL_MS);
  });

  it("is bounded when the run never ends, and survives a failed refresh", async () => {
    const refresh = vi.fn().mockRejectedValue(new Error("down"));
    const options = deps({ stream: vi.fn().mockRejectedValue(new Error("x")), refresh });

    await followCase(options);

    expect(refresh).toHaveBeenCalledTimes(MAX_POLLS);
  });

  it("does not poll after an abort", async () => {
    const controller = new AbortController();
    controller.abort();
    const options = deps({
      stream: vi.fn().mockRejectedValue(new DOMException("aborted", "AbortError")),
      signal: controller.signal,
    });

    await followCase(options);

    expect(options.sleep).not.toHaveBeenCalled();
  });
});
