import fixture from "@fixtures/escalation.json";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { initOf } from "../../test-utils";
import { fetchCases } from "./cases";
import { resetClock } from "./clock";
import { ackEscalation, fetchBrigadeInbox, parseEscalations } from "./escalations";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

describe("parseEscalations", () => {
  it("accepts the escalation fixture in a list", () => {
    const parsed = parseEscalations([fixture]);
    expect(parsed[0]?.pack.timeline).toHaveLength(4);
    expect(parsed[0]?.acknowledged_at).toBeNull();
  });

  it.each([
    ["a non-array", fixture],
    ["a missing brief", [{ ...fixture, brief_en: undefined }]],
    ["a pack without photos", [{ ...fixture, pack: { ...fixture.pack, photos: "x" } }]],
    [
      "a timeline entry without text",
      [{ ...fixture, pack: { ...fixture.pack, timeline: [{ at: "x" }] } }],
    ],
    ["a numeric ack time", [{ ...fixture, acknowledged_at: 5 }]],
  ])("rejects %s", (_label, body) => {
    expect(() => parseEscalations(body)).toThrow();
  });
});

describe("brigade inbox", () => {
  beforeEach(async () => {
    await resetClock();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("serves the fixture with no request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const inbox = await fetchBrigadeInbox("contact-daops-pekanbaru");
    expect(inbox).toHaveLength(1);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("drops an acknowledged escalation from the fixture inbox and moves its case to monitoring", async () => {
    await ackEscalation("esc-0001");
    expect(await fetchBrigadeInbox("contact-daops-pekanbaru")).toEqual([]);
    const listed = (await fetchCases("riau")).find((entry) => entry.case.id === "case-0007");
    expect(listed?.case.status).toBe("monitoring");
  });

  it("asks GET /api/brigade/{contactId}/inbox when live", async () => {
    vi.stubEnv("VITE_SOURCE_ESCALATIONS", "live");
    const fetchMock = vi.fn().mockResolvedValue(Response.json([fixture]));
    vi.stubGlobal("fetch", fetchMock);
    await fetchBrigadeInbox("contact-x");
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/brigade/contact-x/inbox");
  });

  it("posts the ack when live", async () => {
    vi.stubEnv("VITE_SOURCE_ESCALATIONS", "live");
    const fetchMock = vi.fn().mockResolvedValue(Response.json({}));
    vi.stubGlobal("fetch", fetchMock);
    await ackEscalation("esc-0001");
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/brigade/escalations/esc-0001/ack");
    expect(initOf(fetchMock.mock.calls[0]).method).toBe("POST");
  });
});
