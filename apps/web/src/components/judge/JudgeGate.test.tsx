import { screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setJudgeMode } from "../../lib/judge/store";
import { callsTo, renderApp, stubApi } from "../../test-utils";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const clockOff = { now: "2026-07-20T08:00:00+07:00", offset_seconds: 0, judge_mode: false };

function deferred() {
  let resolve: (response: Response) => void = () => {};
  const promise = new Promise<Response>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

describe("judge gate", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_SOURCE_CLOCK", "live");
    setJudgeMode(false);
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("keeps the main area and the footer rendered while the clock is pending", async () => {
    const pending = deferred();
    const fetchMock = stubApi({ "GET /api/clock": () => pending.promise });
    const { container } = renderApp("/public");

    await waitFor(() => expect(callsTo(fetchMock, "GET /api/clock")).toHaveLength(1));
    expect(container.querySelector("main.shell-main")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Memuat Bara…");
    expect(await screen.findByText("API ok")).toBeInTheDocument();
    expect(container.querySelector(".shell")?.lastElementChild).toHaveClass("shell-foot");
  });

  it("renders the children once the clock resolves", async () => {
    const pending = deferred();
    stubApi({ "GET /api/clock": () => pending.promise });
    renderApp("/public");

    expect(await screen.findByRole("status")).toHaveTextContent("Memuat Bara…");
    pending.resolve(Response.json(clockOff));

    expect(
      await screen.findByRole("heading", { level: 1, name: "Public dashboard" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Memuat Bara…")).not.toBeInTheDocument();
  });

  it("does not hang on the loading screen when the clock request fails", async () => {
    stubApi({ "GET /api/clock": () => new Response("down", { status: 503 }) });
    const { container } = renderApp("/public");

    expect(
      await screen.findByRole("heading", { level: 1, name: "Public dashboard" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Memuat Bara…")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Judge mode" })).not.toBeInTheDocument();
    expect(container.querySelectorAll("main.shell-main")).toHaveLength(1);
  });
});
