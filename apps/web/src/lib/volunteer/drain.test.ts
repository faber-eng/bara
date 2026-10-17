import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { drainOutbox, isPermanentFailure } from "./drain";
import { addOutboxItem, countOutboxItems, type NewOutboxItem } from "./outbox";
import { UploadTransferError } from "./putFile";

function item(volunteerId: string, taskId: string): NewOutboxItem {
  return {
    volunteerId,
    taskId,
    kind: "audio",
    contentType: "audio/webm",
    blob: new Blob(["voice"]),
    sample: false,
    point: null,
    ticket: null,
  };
}

const done = { evidenceId: "ev", evidence: null };

describe("isPermanentFailure", () => {
  it("treats refusals as permanent and network trouble as not", () => {
    expect(isPermanentFailure(new ApiError("x", 409))).toBe(true);
    expect(isPermanentFailure(new UploadTransferError("x", 413))).toBe(true);
    expect(isPermanentFailure(new ApiError("x", 429))).toBe(false);
    expect(isPermanentFailure(new ApiError("x", 503))).toBe(false);
    expect(isPermanentFailure(new UploadTransferError("down"))).toBe(false);
    expect(isPermanentFailure(new TypeError("Failed to fetch"))).toBe(false);
  });
});

describe("drainOutbox", () => {
  it("sends every item oldest first and empties the outbox", async () => {
    await addOutboxItem(item("drain-a", "task-1"));
    await addOutboxItem(item("drain-a", "task-2"));
    const upload = vi.fn().mockResolvedValue(done);

    const result = await drainOutbox("drain-a", upload);

    expect(result).toEqual({ sent: 2, dropped: 0, waiting: 0 });
    expect(upload.mock.calls.map(([input]) => input.taskId)).toEqual(["task-1", "task-2"]);
    expect(await countOutboxItems("drain-a")).toBe(0);
  });

  it("stops at the first network failure and keeps the rest", async () => {
    await addOutboxItem(item("drain-b", "task-1"));
    await addOutboxItem(item("drain-b", "task-2"));
    const upload = vi
      .fn()
      .mockResolvedValueOnce(done)
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const result = await drainOutbox("drain-b", upload);

    expect(result).toEqual({ sent: 1, dropped: 0, waiting: 1 });
    expect(await countOutboxItems("drain-b")).toBe(1);
  });

  it("drops an item the server refuses for good and goes on", async () => {
    await addOutboxItem(item("drain-c", "task-1"));
    await addOutboxItem(item("drain-c", "task-2"));
    const upload = vi
      .fn()
      .mockRejectedValueOnce(new ApiError("closed", 409))
      .mockResolvedValueOnce(done);

    const result = await drainOutbox("drain-c", upload);

    expect(result).toEqual({ sent: 1, dropped: 1, waiting: 0 });
  });

  it("does nothing for a volunteer with no items", async () => {
    const upload = vi.fn();

    expect(await drainOutbox("drain-empty", upload)).toEqual({ sent: 0, dropped: 0, waiting: 0 });
    expect(upload).not.toHaveBeenCalled();
  });

  it("keeps the ticket an interrupted upload received", async () => {
    await addOutboxItem(item("drain-d", "task-1"));
    const issued = {
      ticket: { evidence_id: "ev-1", upload_url: "u", headers: {} },
      issuedAt: 1,
      uploaded: true,
    };
    const upload = vi.fn().mockImplementation(async (input) => {
      input.onTicket(issued);
      throw new TypeError("Failed to fetch");
    });
    await drainOutbox("drain-d", upload);
    const next = vi.fn().mockResolvedValue(done);

    await drainOutbox("drain-d", next);

    expect(next.mock.calls[0]?.[0].ticket).toEqual(issued);
  });
});
