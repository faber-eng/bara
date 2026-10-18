import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { brigadeInboxQuery, casesQuery, OPS_REFRESH_MS } from "./queries";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient();
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("ops list refresh", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("refetches the cases list every OPS_REFRESH_MS while visible", async () => {
    const queryFn = vi.fn().mockResolvedValue([]);
    renderHook(() => useQuery({ ...casesQuery("riau"), queryFn }), { wrapper });
    await advance(0);
    expect(queryFn).toHaveBeenCalledTimes(1);

    await advance(OPS_REFRESH_MS - 1);
    expect(queryFn).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(queryFn).toHaveBeenCalledTimes(2);
    await advance(OPS_REFRESH_MS);
    expect(queryFn).toHaveBeenCalledTimes(3);
  });

  it("does not poll the cases list in a hidden tab", () => {
    expect(casesQuery("riau").refetchIntervalInBackground).toBe(false);
  });

  it("refetches the brigade inbox every OPS_REFRESH_MS", async () => {
    const queryFn = vi.fn().mockResolvedValue([]);
    renderHook(() => useQuery({ ...brigadeInboxQuery("contact-1"), queryFn }), { wrapper });
    await advance(0);
    expect(queryFn).toHaveBeenCalledTimes(1);

    await advance(OPS_REFRESH_MS);
    expect(queryFn).toHaveBeenCalledTimes(2);
    expect(brigadeInboxQuery("contact-1").refetchIntervalInBackground).toBe(false);
  });

  it("does not poll the brigade inbox before a contact exists", async () => {
    const queryFn = vi.fn().mockResolvedValue([]);
    renderHook(() => useQuery({ ...brigadeInboxQuery(undefined), queryFn }), { wrapper });
    await advance(OPS_REFRESH_MS * 3);
    expect(queryFn).not.toHaveBeenCalled();
  });
});
