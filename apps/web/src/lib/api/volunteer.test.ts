import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { callsTo, initOf, stubApi } from "../../test-utils";
import { ResponseShapeError } from "./parse";
import {
  completeUpload,
  fetchInbox,
  parseInbox,
  parseUploadTicket,
  requestUpload,
} from "./volunteer";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const SIGNED_HEADERS = {
  "Content-Type": "image/jpeg",
  "x-goog-content-length-range": "0,26214400",
};

const task = {
  id: "t1",
  case_id: "c1",
  type: "dam_check",
  assignee_id: "vol-ari",
  target: { lat: 0.4, lon: 102.1 },
  deadline_at: "2026-07-23T17:00:00+07:00",
  status: "open",
  cloud_task_name: null,
  attempt: 1,
  created_at: "2026-07-20T08:00:00+07:00",
  done_at: null,
};

const verdict = {
  subject: "canal_dam",
  dam_state: "broken",
  smoke: "none",
  hot_ground_signs: "none",
  open_flame: "no",
  transcript: null,
  transcript_en: null,
  reasons: ["gap in the wall"],
  confidence: 0.9,
  needs_human: false,
};

const evidence = {
  id: "e1",
  task_id: "t1",
  case_id: "c1",
  kind: "photo",
  gcs_uri: "gs://b/e1",
  sha256: "0".repeat(64),
  point: null,
  captured_at: null,
  verdict,
  location_ok: true,
  uploaded_by: "vol-ari",
  sample: true,
};

describe("parseInbox", () => {
  it("reads tasks, messages and evidence", () => {
    const inbox = parseInbox({ tasks: [task], messages: [], evidence: [evidence] });
    expect(inbox.tasks[0]?.type).toBe("dam_check");
    expect(inbox.evidence[0]?.verdict?.dam_state).toBe("broken");
  });

  it("treats a missing evidence list as empty", () => {
    expect(parseInbox({ tasks: [], messages: [] }).evidence).toEqual([]);
  });

  it("rejects a task with an unknown type", () => {
    expect(() => parseInbox({ tasks: [{ ...task, type: "nap" }], messages: [] })).toThrow();
  });
});

describe("volunteer API calls", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_SOURCE_INBOX", "live");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("reads the inbox of the volunteer", async () => {
    const fetchMock = stubApi({
      "GET /api/v/uid-1/inbox": () => Response.json({ tasks: [task], messages: [] }),
    });
    const inbox = await fetchInbox("uid-1");
    expect(inbox.tasks).toHaveLength(1);
    expect(callsTo(fetchMock, "GET /api/v/uid-1/inbox")).toHaveLength(1);
  });

  it("asks for a signed upload with the sample flag", async () => {
    const fetchMock = stubApi({
      "POST /api/v/uid-1/uploads": () =>
        Response.json({
          evidence_id: "e1",
          upload_url: "https://gcs/put",
          headers: SIGNED_HEADERS,
        }),
    });
    const ticket = await requestUpload("uid-1", {
      task_id: "t1",
      kind: "photo",
      content_type: "image/jpeg",
      size_bytes: 10,
      sample: true,
    });
    expect(ticket).toEqual({
      evidence_id: "e1",
      upload_url: "https://gcs/put",
      headers: SIGNED_HEADERS,
    });
    const call = callsTo(fetchMock, "POST /api/v/uid-1/uploads")[0];
    expect(JSON.parse(String(initOf(call).body))).toMatchObject({ sample: true, kind: "photo" });
  });

  it("keeps the signed headers of an upload ticket", () => {
    const ticket = parseUploadTicket({
      evidence_id: "e1",
      upload_url: "https://gcs/put",
      headers: SIGNED_HEADERS,
    });
    expect(ticket.headers).toEqual(SIGNED_HEADERS);
  });

  it("rejects an upload ticket without headers", () => {
    expect(() => parseUploadTicket({ evidence_id: "e1", upload_url: "https://gcs/put" })).toThrow(
      ResponseShapeError,
    );
  });

  it("rejects an upload ticket with a non-string header value", () => {
    const body = { evidence_id: "e1", upload_url: "https://gcs/put", headers: { "X-Size": 10 } };
    expect(() => parseUploadTicket(body)).toThrow(ResponseShapeError);
  });

  it("returns the evidence from complete when the body is one, else null", async () => {
    stubApi({
      "POST /api/v/uid-1/evidence/e1/complete": () => Response.json(evidence),
      "POST /api/v/uid-1/evidence/e2/complete": () => Response.json({ status: "ok" }),
    });
    const body = { point: null, captured_at: "2026-07-20T09:00:00Z" };
    expect((await completeUpload("uid-1", "e1", body))?.id).toBe("e1");
    expect(await completeUpload("uid-1", "e2", body)).toBeNull();
  });
});
