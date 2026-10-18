import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HealthFooter } from "./HealthFooter";

const validBody = {
  status: "ok",
  models: { reasoning: "gemini-3.8-flash", fast: "gemini-3.5-flash" },
  fallback_used: false,
  git_sha: "0123456789abcdef",
};

function renderFooter() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retryDelay: 0 } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <HealthFooter />
    </QueryClientProvider>,
  );
}

describe("HealthFooter", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows a checking chip while the request is in flight", () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})));
    renderFooter();

    expect(screen.getByText("Checking API")).toBeInTheDocument();
  });

  it("shows the status, both model IDs and the short git sha", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(validBody)));
    renderFooter();

    expect(await screen.findByText("API ok")).toBeInTheDocument();
    expect(screen.getByText("gemini-3.8-flash")).toBeInTheDocument();
    expect(screen.getByText("gemini-3.5-flash")).toBeInTheDocument();
    expect(screen.getByText("0123456")).toBeInTheDocument();
    expect(screen.queryByText("fallback in use")).not.toBeInTheDocument();
  });

  it("shows a fallback chip when the API fell back to another model", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({ ...validBody, fallback_used: true })),
    );
    renderFooter();

    expect(await screen.findByText("fallback in use")).toBeInTheDocument();
  });

  it("shows unreachable when the request fails, and recovers on Check again", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("network"))
      .mockRejectedValueOnce(new TypeError("network"))
      .mockResolvedValue(Response.json(validBody));
    vi.stubGlobal("fetch", fetchMock);
    renderFooter();

    expect(await screen.findByText("API unreachable")).toBeInTheDocument();
    expect(screen.getByText("GET /api/health did not answer.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Check again" }));

    expect(await screen.findByText("API ok")).toBeInTheDocument();
  });

  it("shows unreachable on a 500", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("down", { status: 500 })));
    renderFooter();

    expect(await screen.findByText("API unreachable")).toBeInTheDocument();
  });

  it("shows unreachable when the body is not a health response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ status: "ok" })));
    renderFooter();

    expect(await screen.findByText("API unreachable")).toBeInTheDocument();
  });
});
