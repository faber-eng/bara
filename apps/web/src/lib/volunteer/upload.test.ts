import { afterEach, describe, expect, it, vi } from "vitest";
import { callsTo, stubApi } from "../../test-utils";
import { putFile, UploadTransferError } from "./putFile";
import { uploadEvidence } from "./upload";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));
vi.mock("./putFile", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./putFile")>()),
  putFile: vi.fn().mockResolvedValue(undefined),
}));

function ticketBody(evidenceId: string) {
  return {
    evidence_id: evidenceId,
    upload_url: "https://gcs/put",
    headers: { "Content-Type": "image/jpeg" },
  };
}

function retryInput(options: { issuedAt: number; onTicket?: () => void }) {
  return {
    volunteerId: "uid-1",
    taskId: "t1",
    kind: "photo" as const,
    blob: new Blob(["x"]),
    contentType: "image/jpeg",
    sample: false,
    point: null,
    capturedAt: "2026-10-18T01:00:00.000Z",
    ticket: { ticket: ticketBody("e1"), issuedAt: options.issuedAt, uploaded: false },
    onTicket: options.onTicket ?? (() => {}),
    onProgress: () => {},
  };
}

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
      capturedAt: "2026-10-18T01:00:00.000Z",
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
        capturedAt: "2026-10-18T01:00:00.000Z",
        ticket: null,
        onTicket: () => {},
        onProgress: () => {},
      }),
    ).rejects.toThrow("403");
    expect(callsTo(fetchMock, "POST /api/v/uid-1/evidence/e1/complete")).toHaveLength(0);
  });

  it("reuses a fresh ticket on retry instead of asking for a new one", async () => {
    vi.mocked(putFile).mockResolvedValue(undefined);
    const fetchMock = stubApi({
      "POST /api/v/uid-1/evidence/e1/complete": () => Response.json({ status: "ok" }),
    });

    const result = await uploadEvidence(retryInput({ issuedAt: Date.now() - 60_000 }));

    expect(result.evidenceId).toBe("e1");
    expect(callsTo(fetchMock, "POST /api/v/uid-1/uploads")).toHaveLength(0);
  });

  it("asks for a new ticket when the old one is older than the signed URL life", async () => {
    vi.mocked(putFile).mockResolvedValue(undefined);
    const onTicket = vi.fn();
    const fetchMock = stubApi({
      "POST /api/v/uid-1/uploads": () => Response.json(ticketBody("e2")),
      "POST /api/v/uid-1/evidence/e2/complete": () => Response.json({ status: "ok" }),
    });

    const result = await uploadEvidence(
      retryInput({ issuedAt: Date.now() - 16 * 60_000, onTicket }),
    );

    expect(result.evidenceId).toBe("e2");
    expect(callsTo(fetchMock, "POST /api/v/uid-1/uploads")).toHaveLength(1);
    expect(onTicket).toHaveBeenCalledWith(
      expect.objectContaining({ ticket: expect.objectContaining({ evidence_id: "e2" }) }),
    );
  });

  it("gets a new ticket and puts again when a reused ticket answers 403", async () => {
    vi.mocked(putFile)
      .mockRejectedValueOnce(new UploadTransferError("Upload returned 403", 403))
      .mockResolvedValueOnce(undefined);
    const fetchMock = stubApi({
      "POST /api/v/uid-1/uploads": () => Response.json(ticketBody("e2")),
      "POST /api/v/uid-1/evidence/e2/complete": () => Response.json({ status: "ok" }),
    });

    const result = await uploadEvidence(retryInput({ issuedAt: Date.now() - 60_000 }));

    expect(result.evidenceId).toBe("e2");
    expect(putFile).toHaveBeenCalledTimes(2);
    expect(callsTo(fetchMock, "POST /api/v/uid-1/uploads")).toHaveLength(1);
  });

  it("treats a 400 on a reused ticket as expired too", async () => {
    vi.mocked(putFile)
      .mockRejectedValueOnce(new UploadTransferError("Upload returned 400", 400))
      .mockResolvedValueOnce(undefined);
    stubApi({
      "POST /api/v/uid-1/uploads": () => Response.json(ticketBody("e2")),
      "POST /api/v/uid-1/evidence/e2/complete": () => Response.json({ status: "ok" }),
    });

    const result = await uploadEvidence(retryInput({ issuedAt: Date.now() - 60_000 }));

    expect(result.evidenceId).toBe("e2");
  });

  it("completes the same evidence without a second PUT when the file already went up", async () => {
    vi.mocked(putFile).mockResolvedValue(undefined);
    const fetchMock = stubApi({
      "POST /api/v/uid-1/evidence/e1/complete": () => Response.json({ status: "ok" }),
    });
    const input = retryInput({ issuedAt: Date.now() - 16 * 60_000 });

    const result = await uploadEvidence({
      ...input,
      ticket: { ...input.ticket, uploaded: true },
    });

    expect(result.evidenceId).toBe("e1");
    expect(putFile).not.toHaveBeenCalled();
    expect(callsTo(fetchMock, "POST /api/v/uid-1/uploads")).toHaveLength(0);
  });

  it("marks the ticket uploaded once the PUT worked, before completing", async () => {
    vi.mocked(putFile).mockResolvedValue(undefined);
    const onTicket = vi.fn();
    stubApi({
      "POST /api/v/uid-1/uploads": () => Response.json(ticketBody("e1")),
      "POST /api/v/uid-1/evidence/e1/complete": () => new Response("down", { status: 500 }),
    });

    await expect(
      uploadEvidence({ ...retryInput({ issuedAt: 0 }), ticket: null, onTicket }),
    ).rejects.toThrow();

    expect(onTicket).toHaveBeenLastCalledWith(expect.objectContaining({ uploaded: true }));
  });

  it("does not loop when a brand new ticket answers 403", async () => {
    vi.mocked(putFile).mockRejectedValue(new UploadTransferError("Upload returned 403", 403));
    const fetchMock = stubApi({
      "POST /api/v/uid-1/uploads": () => Response.json(ticketBody("e2")),
    });

    await expect(uploadEvidence({ ...retryInput({ issuedAt: 0 }), ticket: null })).rejects.toThrow(
      "403",
    );
    expect(callsTo(fetchMock, "POST /api/v/uid-1/uploads")).toHaveLength(1);
    expect(putFile).toHaveBeenCalledTimes(1);
  });
});
