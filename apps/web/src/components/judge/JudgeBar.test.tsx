import { QueryClient } from "@tanstack/react-query";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setJudgeMode } from "../../lib/judge/store";
import { callsTo, headerOf, initOf, renderApp, stubApi } from "../../test-utils";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const clockOn = { now: "2026-07-20T08:00:00+07:00", offset_seconds: 0, judge_mode: true };
const clockAdvanced = {
  now: "2026-07-22T08:00:00+07:00",
  offset_seconds: 172800,
  judge_mode: true,
};

function deferred() {
  let resolve: (response: Response) => void = () => {};
  const promise = new Promise<Response>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function bar() {
  return screen.getByRole("region", { name: "Judge mode" });
}

describe("judge bar", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_SOURCE_CLOCK", "live");
    setJudgeMode(false);
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("holds the page back until the first clock request settles", async () => {
    const pending = deferred();
    const fetchMock = stubApi({ "GET /api/clock": () => pending.promise });
    renderApp("/nope");

    await waitFor(() => expect(callsTo(fetchMock, "GET /api/clock")).toHaveLength(1));
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();

    pending.resolve(Response.json(clockOn));

    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("shows the sim time in Asia/Jakarta with a Sim label", async () => {
    stubApi({ "GET /api/clock": () => Response.json(clockOn) });
    renderApp("/nope");

    expect(await screen.findByText("Sim · 20 Jul 2026, 08:00")).toBeInTheDocument();
  });

  it("is hidden when judge mode is off", async () => {
    stubApi({ "GET /api/clock": () => Response.json({ ...clockOn, judge_mode: false }) });
    renderApp("/nope");

    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Judge mode" })).not.toBeInTheDocument();
  });

  it("is hidden and the page still renders when the clock request fails", async () => {
    stubApi({ "GET /api/clock": () => new Response("down", { status: 500 }) });
    renderApp("/nope");

    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Judge mode" })).not.toBeInTheDocument();
  });

  it("sends no role header on any call when judge mode is off", async () => {
    const fetchMock = stubApi({
      "GET /api/clock": () => Response.json({ ...clockOn, judge_mode: false }),
    });
    renderApp("/nope");
    await screen.findByRole("heading", { level: 1 });

    const clockCall = callsTo(fetchMock, "GET /api/clock")[0];
    expect(headerOf(clockCall, "Authorization")).toBe("Bearer token-1");
    expect(headerOf(clockCall, "X-Bara-Role")).toBeNull();
  });

  it("lists the five example people in the role switcher", async () => {
    stubApi({ "GET /api/clock": () => Response.json(clockOn) });
    renderApp("/nope");
    await screen.findByRole("region", { name: "Judge mode" });

    const options = within(screen.getByRole("combobox", { name: "Role" })).getAllByRole("option");

    expect(options.map((option) => option.textContent)).toEqual([
      "Ops",
      "Volunteer Ari (example)",
      "Repair team Sari (example)",
      "Patrol Dedi (example)",
      "Brigade Pekanbaru (example)",
    ]);
  });

  it.each([
    ["vol-ari", "volunteer", "Your tasks"],
    ["team-sari", "volunteer", "Your tasks"],
    ["vol-dedi", "volunteer", "Your tasks"],
    ["contact-daops-pekanbaru", "brigade", "Brigade inbox"],
  ])(
    "switching to %s sends %s on the next call, navigates and invalidates",
    async (key, role, title) => {
      const fetchMock = stubApi({ "GET /api/clock": () => Response.json(clockOn) });
      const queryClient = new QueryClient();
      queryClient.setQueryData(["cases", "riau"], []);
      renderApp("/nope", queryClient);
      const select = await screen.findByRole("combobox", { name: "Role" });
      const callsBefore = callsTo(fetchMock, "GET /api/clock").length;

      fireEvent.change(select, { target: { value: key } });

      expect(await screen.findByRole("heading", { level: 1, name: title })).toBeInTheDocument();
      await waitFor(() =>
        expect(callsTo(fetchMock, "GET /api/clock").length).toBeGreaterThan(callsBefore),
      );
      const clockCalls = callsTo(fetchMock, "GET /api/clock");
      expect(headerOf(clockCalls[clockCalls.length - 1], "X-Bara-Role")).toBe(role);
      expect(queryClient.getQueryState(["cases", "riau"])?.isInvalidated).toBe(true);
    },
  );

  it("keeps ops as the first role header", async () => {
    const fetchMock = stubApi({ "GET /api/clock": () => Response.json(clockOn) });
    renderApp("/nope");
    await screen.findByRole("region", { name: "Judge mode" });

    expect(headerOf(callsTo(fetchMock, "GET /api/clock")[0], "X-Bara-Role")).toBeNull();
    fireEvent.change(screen.getByRole("combobox", { name: "Role" }), {
      target: { value: "vol-ari" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Role" }), { target: { value: "ops" } });
    await screen.findByRole("heading", { level: 1, name: "Ops dashboard" });
    await waitFor(() => {
      const calls = callsTo(fetchMock, "GET /api/clock");
      expect(headerOf(calls[calls.length - 1], "X-Bara-Role")).toBe("ops");
    });
  });

  it.each([6, 24, 48])("+%ih posts the hours to /api/judge/advance", async (hours) => {
    const fetchMock = stubApi({
      "GET /api/clock": () => Response.json(clockOn),
      "POST /api/judge/advance": () => Response.json(clockAdvanced),
    });
    renderApp("/nope");
    await screen.findByRole("region", { name: "Judge mode" });

    fireEvent.click(within(bar()).getByRole("button", { name: `+${hours}h` }));

    await waitFor(() => expect(callsTo(fetchMock, "POST /api/judge/advance")).toHaveLength(1));
    const call = callsTo(fetchMock, "POST /api/judge/advance")[0];
    expect(initOf(call).body).toBe(JSON.stringify({ hours }));
  });

  it("disables the buttons while advancing, then shows the new sim time and invalidates cases", async () => {
    const pending = deferred();
    let current = clockOn;
    stubApi({
      "GET /api/clock": () => Response.json(current),
      "POST /api/judge/advance": () => pending.promise,
    });
    const queryClient = new QueryClient();
    queryClient.setQueryData(["cases", "riau"], []);
    renderApp("/nope", queryClient);
    await screen.findByRole("region", { name: "Judge mode" });

    fireEvent.click(within(bar()).getByRole("button", { name: "+48h" }));

    await waitFor(() => expect(within(bar()).getByRole("button", { name: "+48h" })).toBeDisabled());
    expect(within(bar()).getByRole("button", { name: "+6h" })).toBeDisabled();
    expect(within(bar()).getByRole("button", { name: "Reset scenario" })).toBeDisabled();

    current = clockAdvanced;
    pending.resolve(Response.json(clockAdvanced));

    expect(await screen.findByText("Sim · 22 Jul 2026, 08:00")).toBeInTheDocument();
    expect(within(bar()).getByRole("button", { name: "+48h" })).toBeEnabled();
    expect(queryClient.getQueryState(["cases", "riau"])?.isInvalidated).toBe(true);
  });

  it("shows an alert and re-enables the buttons when advance fails", async () => {
    stubApi({
      "GET /api/clock": () => Response.json(clockOn),
      "POST /api/judge/advance": () => new Response("boom", { status: 500 }),
    });
    renderApp("/nope");
    await screen.findByRole("region", { name: "Judge mode" });

    fireEvent.click(within(bar()).getByRole("button", { name: "+24h" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not move the clock");
    expect(within(bar()).getByRole("button", { name: "+24h" })).toBeEnabled();
  });

  it("posts to /api/judge/reset", async () => {
    let current = clockAdvanced;
    const fetchMock = stubApi({
      "GET /api/clock": () => Response.json(current),
      "POST /api/judge/reset": () => {
        current = clockOn;
        return Response.json(clockOn);
      },
    });
    renderApp("/nope");
    await screen.findByText("Sim · 22 Jul 2026, 08:00");

    fireEvent.click(within(bar()).getByRole("button", { name: "Reset scenario" }));

    expect(await screen.findByText("Sim · 20 Jul 2026, 08:00")).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST /api/judge/reset")).toHaveLength(1);
  });

  it("explains a 429 on reset as a rate limit", async () => {
    stubApi({
      "GET /api/clock": () => Response.json(clockOn),
      "POST /api/judge/reset": () => new Response("slow down", { status: 429 }),
    });
    renderApp("/nope");
    await screen.findByRole("region", { name: "Judge mode" });

    fireEvent.click(within(bar()).getByRole("button", { name: "Reset scenario" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Reset is rate-limited");
    expect(within(bar()).getByRole("button", { name: "Reset scenario" })).toBeEnabled();
  });
});

describe("judge bar on the clock fixture", () => {
  beforeEach(() => {
    setJudgeMode(false);
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("moves the sim time with no request to the API", async () => {
    const fetchMock = stubApi({});
    renderApp("/nope");
    await screen.findByText("Sim · 20 Jul 2026, 08:00");

    fireEvent.click(within(bar()).getByRole("button", { name: "+48h" }));

    expect(await screen.findByText("Sim · 22 Jul 2026, 08:00")).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST /api/judge/advance")).toHaveLength(0);

    await waitFor(() =>
      expect(within(bar()).getByRole("button", { name: "Reset scenario" })).toBeEnabled(),
    );
    fireEvent.click(within(bar()).getByRole("button", { name: "Reset scenario" }));
    expect(await screen.findByText("Sim · 20 Jul 2026, 08:00")).toBeInTheDocument();
  });
});
