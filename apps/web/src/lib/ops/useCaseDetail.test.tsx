import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as caseDetail from "../api/caseDetail";
import * as caseStream from "../api/caseStream";
import { OPS_REFRESH_MS } from "../api/queries";
import { useCaseDetail } from "./useCaseDetail";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient();
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

const never = () => new Promise<void>(() => {});

describe("useCaseDetail", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubEnv("VITE_SOURCE_CASEDETAIL", "live");
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("does not poll while the stream is live", async () => {
    const fetchDetail = vi.spyOn(caseDetail, "fetchCaseDetail").mockResolvedValue({} as never);
    vi.spyOn(caseStream, "streamCase").mockImplementation(never);
    renderHook(() => useCaseDetail("case-1"), { wrapper });
    await advance(0);
    expect(fetchDetail).toHaveBeenCalledTimes(1);

    await advance(OPS_REFRESH_MS * 3);
    expect(fetchDetail).toHaveBeenCalledTimes(1);
  });

  it("polls every OPS_REFRESH_MS once the stream has ended", async () => {
    const fetchDetail = vi
      .spyOn(caseDetail, "fetchCaseDetail")
      .mockResolvedValue({ agent_runs: [{ status: "done" }] } as never);
    vi.spyOn(caseStream, "streamCase").mockResolvedValue(undefined);
    renderHook(() => useCaseDetail("case-1"), { wrapper });
    await advance(0);
    const before = fetchDetail.mock.calls.length;

    await advance(OPS_REFRESH_MS);
    expect(fetchDetail.mock.calls.length).toBe(before + 1);
    await advance(OPS_REFRESH_MS);
    expect(fetchDetail.mock.calls.length).toBe(before + 2);
  });
});
