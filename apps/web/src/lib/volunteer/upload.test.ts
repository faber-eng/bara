import { afterEach, describe, expect, it, vi } from "vitest";
import { callsTo, stubApi } from "../../test-utils";
import { putFile } from "./putFile";
import { uploadEvidence } from "./upload";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));
vi.mock("./putFile", () => ({ putFile: vi.fn().mockResolvedValue(undefined) }));

describe("uploadEvidence", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("asks for a ticket, PUTs the blob, then completes", async () => {
    const order: string[] = [];
    vi.mocked(putFile).mockImplementation(() => {
      order.push("put");
      return Promise.resolve();
    });
    const fetchMock = stubApi({
      "POST /api/v/uid-1/uploads": () => {
        order.push("ticket");
        return Response.json({
          evidence_id: "e1",
          upload_url: "https://gcs/put",
          headers: { "Content-Type": "image/jpeg" },
        });
      },
      "POST /api/v/uid-1/evidence/e1/complete": () => {
        order.push("complete");
        return Response.json({ status: "ok" });
      },
    });
    const blob = new Blob(["abc"], { type: "image/jpeg" });

    const result = await uploadEvidence({
      volunteerId: "uid-1",
      taskId: "t1",
      kind: "photo",
      blob,
      contentType: "image/jpeg",
      sample: true,
      point: null,
      ticket: null,
      onTicket: () => {},
      onProgress: () => {},
    });

    expect(order).toEqual(["ticket", "put", "complete"]);
    expect(result).toEqual({ evidenceId: "e1", evidence: null });
    expect(putFile).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "https://gcs/put",
        blob,
        headers: { "Content-Type": "image/jpeg" },
      }),
    );
    expect(callsTo(fetchMock, "POST /api/v/uid-1/uploads")).toHaveLength(1);
  });

  it("does not complete when the PUT fails", async () => {
    vi.mocked(putFile).mockRejectedValue(new Error("403"));
    const fetchMock = stubApi({
      "POST /api/v/uid-1/uploads": () =>
        Response.json({
          evidence_id: "e1",
          upload_url: "https://gcs/put",
          headers: { "Content-Type": "image/jpeg" },
        }),
    });

    await expect(
      uploadEvidence({
        volunteerId: "uid-1",
        taskId: "t1",
        kind: "photo",
        blob: new Blob(["x"]),
        contentType: "image/jpeg",
        sample: false,
        point: null,
        ticket: null,
        onTicket: () => {},
        onProgress: () => {},
      }),
    ).rejects.toThrow("403");
    expect(callsTo(fetchMock, "POST /api/v/uid-1/evidence/e1/complete")).toHaveLength(0);
  });

  it("reuses a ticket on retry instead of asking for a new one", async () => {
    vi.mocked(putFile).mockResolvedValue(undefined);
    const fetchMock = stubApi({
      "POST /api/v/uid-1/evidence/e1/complete": () => Response.json({ status: "ok" }),
    });

    const result = await uploadEvidence({
      volunteerId: "uid-1",
      taskId: "t1",
      kind: "photo",
      blob: new Blob(["x"]),
      contentType: "image/jpeg",
      sample: false,
      point: null,
      ticket: {
        evidence_id: "e1",
        upload_url: "https://gcs/put",
        headers: { "Content-Type": "image/jpeg" },
      },
      onTicket: () => {},
      onProgress: () => {},
    });

    expect(result.evidenceId).toBe("e1");
    expect(callsTo(fetchMock, "POST /api/v/uid-1/uploads")).toHaveLength(0);
  });
});
