import detail from "@fixtures/case_detail.json";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { initOf } from "../../test-utils";
import { closeCase, fetchCaseDetail, parseCaseDetail } from "./caseDetail";
import { fetchCases } from "./cases";
import { ApiError } from "./client";
import { resetClock } from "./clock";
import { clearFixtureClosures } from "./fixtureClosures";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

describe("parseCaseDetail", () => {
  it("accepts the case detail fixture", () => {
    const parsed = parseCaseDetail(detail);
    expect(parsed.tasks).toHaveLength(2);
    expect(parsed.evidence).toHaveLength(2);
    expect(parsed.agent_runs[0]?.tool_calls).toHaveLength(4);
    expect(parsed.timeline).toHaveLength(3);
  });

  it("keeps tool call args as JSON", () => {
    const call = parseCaseDetail(detail).agent_runs[0]?.tool_calls[3];
    expect(call?.args).toEqual({
      case_id: "case-0001",
      assignee_id: "vol-ari",
      task_type: "dam_check",
      deadline_hours: 72,
    });
  });

  it("accepts a case with no runs and no final decision", () => {
    const run = { ...detail.agent_runs[0], final_json: null };
    expect(parseCaseDetail({ ...detail, agent_runs: [run] }).agent_runs[0]?.final_json).toBeNull();
  });

  it.each([
    ["a non-object", []],
    ["a missing timeline", { ...detail, timeline: undefined }],
    ["an unknown evidence kind", { ...detail, evidence: [{ ...detail.evidence[0], kind: "gif" }] }],
    [
      "a verdict without confidence",
      {
        ...detail,
        evidence: [
          {
            ...detail.evidence[0],
            verdict: { ...detail.evidence[0]?.verdict, confidence: "high" },
          },
        ],
      },
    ],
    [
      "a tool call without ms",
      {
        ...detail,
        agent_runs: [
          { ...detail.agent_runs[0], tool_calls: [{ name: "x", args: {}, result_summary: "" }] },
        ],
      },
    ],
    ["an unknown task status", { ...detail, tasks: [{ ...detail.tasks[0], status: "later" }] }],
  ])("rejects %s", (_label, body) => {
    expect(() => parseCaseDetail(body)).toThrow();
  });
});

describe("fetchCaseDetail", () => {
  beforeEach(async () => {
    clearFixtureClosures();
    await resetClock();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("serves the fixture for case-0001 with no request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const result = await fetchCaseDetail("case-0001");
    expect(result.agent_runs).toHaveLength(1);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("builds an empty detail from the case list for another fixture case", async () => {
    const result = await fetchCaseDetail("case-0005");
    expect(result.case.id).toBe("case-0005");
    expect(result.evidence).toEqual([]);
    expect(result.agent_runs).toEqual([]);
  });

  it("rejects an unknown fixture case with a 404", async () => {
    const failure = await fetchCaseDetail("nope").catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).status).toBe(404);
  });

  it("asks GET /api/cases/{id} when live", async () => {
    vi.stubEnv("VITE_SOURCE_CASEDETAIL", "live");
    const fetchMock = vi.fn().mockResolvedValue(Response.json(detail));
    vi.stubGlobal("fetch", fetchMock);
    await fetchCaseDetail("case-0001");
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/cases/case-0001");
  });
});

describe("closeCase", () => {
  beforeEach(async () => {
    clearFixtureClosures();
    await resetClock();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("posts to /api/cases/{id}/close when live", async () => {
    vi.stubEnv("VITE_SOURCE_CASEDETAIL", "live");
    const fetchMock = vi.fn().mockResolvedValue(Response.json({}));
    vi.stubGlobal("fetch", fetchMock);
    await closeCase("case-0005");
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/cases/case-0005/close");
    expect(initOf(fetchMock.mock.calls[0]).method).toBe("POST");
  });

  it("accepts a close answered with no body", async () => {
    vi.stubEnv("VITE_SOURCE_CASEDETAIL", "live");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    await expect(closeCase("case-0005")).resolves.toBeUndefined();
  });

  it("reopens a closed fixture case when the scenario resets", async () => {
    await closeCase("case-0005");
    await resetClock();
    expect((await fetchCaseDetail("case-0005")).case.status).toBe("resolved_pending_human");
  });

  it("closes the fixture case in the detail and in the list", async () => {
    await closeCase("case-0005");
    const result = await fetchCaseDetail("case-0005");
    expect(result.case.status).toBe("closed");
    expect(result.case.closed_by).not.toBeNull();
    const listed = (await fetchCases("riau")).find((entry) => entry.case.id === "case-0005");
    expect(listed?.case.status).toBe("closed");
  });

  it("refuses to close a fixture case that is not waiting for a person", async () => {
    const failure = await closeCase("case-0001").catch((error: unknown) => error);
    expect((failure as ApiError).status).toBe(409);
  });
});
