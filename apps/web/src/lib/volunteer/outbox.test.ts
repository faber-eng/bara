import { describe, expect, it } from "vitest";
import {
  addOutboxItem,
  countOutboxItems,
  listOutboxItems,
  type NewOutboxItem,
  removeOutboxItem,
  saveOutboxTicket,
} from "./outbox";

function item(volunteerId: string, taskId = "task-1"): NewOutboxItem {
  return {
    volunteerId,
    taskId,
    kind: "audio",
    contentType: "audio/webm",
    blob: new Blob(["voice"], { type: "audio/webm" }),
    sample: false,
    point: null,
    capturedAt: "2026-10-18T01:00:00.000Z",
    ticket: null,
  };
}

describe("the outbox", () => {
  it("keeps an item with its blob until it is removed", async () => {
    const id = await addOutboxItem(item("outbox-a"));

    const [stored] = await listOutboxItems("outbox-a");
    expect(stored?.id).toBe(id);
    expect(stored?.blob.size).toBe(5);
    expect(stored?.contentType).toBe("audio/webm");

    await removeOutboxItem(id);
    expect(await countOutboxItems("outbox-a")).toBe(0);
  });

  it("keeps each volunteer's items apart and lists oldest first", async () => {
    const first = await addOutboxItem(item("outbox-b", "task-1"));
    await addOutboxItem(item("outbox-c", "task-9"));
    const second = await addOutboxItem(item("outbox-b", "task-2"));

    const listed = await listOutboxItems("outbox-b");

    expect(listed.map((entry) => entry.id)).toEqual([first, second]);
    expect(await countOutboxItems("outbox-c")).toBe(1);
  });

  it("stores the ticket that an interrupted upload already used", async () => {
    const id = await addOutboxItem(item("outbox-d"));
    const issued = {
      ticket: { evidence_id: "ev-1", upload_url: "https://gcs/put", headers: {} },
      issuedAt: 1,
      uploaded: true,
    };

    await saveOutboxTicket(id, issued);

    const [again] = await listOutboxItems("outbox-d");
    expect(again?.ticket).toEqual(issued);
    expect(again?.id).toBe(id);
  });
});

describe("saveOutboxTicket", () => {
  it("does not bring back an item that was already removed", async () => {
    const id = await addOutboxItem(item("outbox-e"));
    await removeOutboxItem(id);
    const issued = {
      ticket: { evidence_id: "ev-1", upload_url: "u", headers: {} },
      issuedAt: 1,
      uploaded: true,
    };

    await saveOutboxTicket(id, issued);

    expect(await countOutboxItems("outbox-e")).toBe(0);
  });
});
