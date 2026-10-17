import escalation from "@fixtures/escalation.json";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetClock } from "../lib/api/clock";
import { getIdToken } from "../lib/auth";
import { setJudgeMode } from "../lib/judge/store";
import { callsTo, headerOf, renderApp, stubApi } from "../test-utils";

vi.mock("../lib/auth", () => ({ getIdToken: vi.fn() }));

function tokenFor(uid: string, provider: string): string {
  return `h.${btoa(JSON.stringify({ sub: uid, firebase: { sign_in_provider: provider } }))}.s`;
}

const REAL_TOKEN = tokenFor("uid-brigade-1", "google.com");
const ANONYMOUS_TOKEN = tokenFor("anon-1", "anonymous");

describe("/brigade", () => {
  beforeEach(async () => {
    setJudgeMode(false);
    localStorage.clear();
    vi.mocked(getIdToken).mockResolvedValue(ANONYMOUS_TOKEN);
    await resetClock();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("shows the escalation card with both briefs, timeline and map", async () => {
    renderApp("/brigade");

    const card = await screen.findByRole("article", { name: "Escalation for case-0007" });
    expect(card).toHaveTextContent("Patroli melihat asap tipis");
    expect(card).toHaveTextContent("A patrol saw smoke wisps");
    expect(card).toHaveTextContent("Smoke wisps reported in riau-0533.");
    expect(card).toHaveTextContent("0.5330, 102.2040");
    expect(screen.getByRole("link", { name: "Open in Google Maps" })).toHaveAttribute(
      "href",
      escalation.pack.map_url,
    );
    expect(screen.getByText("1 open")).toBeInTheDocument();
  });

  it("acknowledges and removes the card, and the case becomes monitoring", async () => {
    renderApp("/brigade");

    fireEvent.click(await screen.findByRole("button", { name: /Acknowledge/ }));

    expect(await screen.findByText("No open escalations.")).toBeInTheDocument();
    expect(screen.getByText("0 open")).toBeInTheDocument();
    const { fetchCases } = await import("../lib/api/cases");
    const listed = (await fetchCases("riau")).find((entry) => entry.case.id === "case-0007");
    expect(listed?.case.status).toBe("monitoring");
  });

  it("labels the card as example data while judge mode is on", async () => {
    renderApp("/brigade");

    expect(await screen.findByRole("article")).toBeInTheDocument();
    expect(await screen.findByText("Example data")).toBeInTheDocument();
  });

  it("works for a real brigade user: own uid, Bearer token, no judge header", async () => {
    vi.mocked(getIdToken).mockResolvedValue(REAL_TOKEN);
    vi.stubEnv("VITE_SOURCE_ESCALATIONS", "live");
    vi.stubEnv("VITE_SOURCE_CLOCK", "live");
    let acked = false;
    const fetchMock = stubApi({
      "GET /api/clock": () =>
        Response.json({ now: "2026-07-20T08:00:00+07:00", offset_seconds: 0, judge_mode: false }),
      "GET /api/brigade/uid-brigade-1/inbox": () => Response.json(acked ? [] : [escalation]),
      "POST /api/brigade/escalations/esc-0001/ack": () => {
        acked = true;
        return new Response(null, { status: 204 });
      },
    });
    renderApp("/brigade");

    fireEvent.click(await screen.findByRole("button", { name: /Acknowledge/ }));

    expect(await screen.findByText("No open escalations.")).toBeInTheDocument();
    const inbox = callsTo(fetchMock, "GET /api/brigade/uid-brigade-1/inbox")[0];
    expect(headerOf(inbox, "Authorization")).toBe(`Bearer ${REAL_TOKEN}`);
    expect(headerOf(inbox, "X-Bara-Role")).toBeNull();
    expect(screen.queryByText("Example data")).not.toBeInTheDocument();
    const ack = callsTo(fetchMock, "POST /api/brigade/escalations/esc-0001/ack")[0];
    expect(headerOf(ack, "Authorization")).toBe(`Bearer ${REAL_TOKEN}`);
  });

  it("uses the example contact and the brigade role in judge mode, even with another person picked", async () => {
    vi.stubEnv("VITE_SOURCE_ESCALATIONS", "live");
    vi.stubEnv("VITE_SOURCE_CLOCK", "live");
    const fetchMock = stubApi({
      "GET /api/clock": () =>
        Response.json({ now: "2026-07-20T08:00:00+07:00", offset_seconds: 0, judge_mode: true }),
      "GET /api/brigade/contact-daops-pekanbaru/inbox": () => Response.json([escalation]),
    });
    renderApp("/brigade");

    expect(await screen.findByRole("article")).toBeInTheDocument();
    expect(await screen.findByText("Example data")).toBeInTheDocument();
    const calls = callsTo(fetchMock, "GET /api/brigade/contact-daops-pekanbaru/inbox");
    expect(calls.length).toBeGreaterThan(0);
    expect(headerOf(calls[0], "X-Bara-Role")).toBe("brigade");
  });

  it("keeps the card and says so when acknowledging fails", async () => {
    vi.mocked(getIdToken).mockResolvedValue(REAL_TOKEN);
    vi.stubEnv("VITE_SOURCE_ESCALATIONS", "live");
    vi.stubEnv("VITE_SOURCE_CLOCK", "live");
    stubApi({
      "GET /api/clock": () =>
        Response.json({ now: "2026-07-20T08:00:00+07:00", offset_seconds: 0, judge_mode: false }),
      "GET /api/brigade/uid-brigade-1/inbox": () => Response.json([escalation]),
      "POST /api/brigade/escalations/esc-0001/ack": () => new Response("x", { status: 500 }),
    });
    renderApp("/brigade");

    fireEvent.click(await screen.findByRole("button", { name: /Acknowledge/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not acknowledge");
    await waitFor(() => expect(screen.getByRole("button", { name: /Acknowledge/ })).toBeEnabled());
  });

  it("tells an account without the brigade role", async () => {
    vi.mocked(getIdToken).mockResolvedValue(REAL_TOKEN);
    vi.stubEnv("VITE_SOURCE_ESCALATIONS", "live");
    vi.stubEnv("VITE_SOURCE_CLOCK", "live");
    stubApi({
      "GET /api/clock": () =>
        Response.json({ now: "2026-07-20T08:00:00+07:00", offset_seconds: 0, judge_mode: false }),
      "GET /api/brigade/uid-brigade-1/inbox": () => new Response("no", { status: 403 }),
    });
    renderApp("/brigade");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This account does not have the brigade role",
    );
  });

  it("shows the empty state", async () => {
    vi.mocked(getIdToken).mockResolvedValue(REAL_TOKEN);
    vi.stubEnv("VITE_SOURCE_ESCALATIONS", "live");
    vi.stubEnv("VITE_SOURCE_CLOCK", "live");
    stubApi({
      "GET /api/clock": () =>
        Response.json({ now: "2026-07-20T08:00:00+07:00", offset_seconds: 0, judge_mode: false }),
      "GET /api/brigade/uid-brigade-1/inbox": () => Response.json([]),
    });
    renderApp("/brigade");

    expect(await screen.findByText("No open escalations.")).toBeInTheDocument();
  });
});
