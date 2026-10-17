import { describe, expect, it } from "vitest";
import type { Evidence } from "../contracts";
import { type FlowAction, type FlowState, flowReducer, IDLE } from "./flow";

const evidence = { id: "e1", sample: true } as Evidence;

function run(actions: FlowAction[], from: FlowState = IDLE): FlowState {
  return actions.reduce(flowReducer, from);
}

describe("flowReducer", () => {
  it("walks a photo from preview to a verdict", () => {
    const photo = new Blob(["x"]);
    const state = run([
      { type: "preparing" },
      { type: "photo_chosen", photo, sample: true },
      { type: "upload_started", kind: "photo", sample: true },
      { type: "progress", progress: 0.5 },
      { type: "uploaded" },
      { type: "judged", evidence },
    ]);

    expect(state).toEqual({ step: "done", evidence });
  });

  it("keeps the sample flag while uploading and reading", () => {
    const uploading = run([{ type: "upload_started", kind: "audio", sample: true }]);
    expect(uploading).toMatchObject({ step: "uploading", sample: true, progress: 0 });
    expect(flowReducer(uploading, { type: "uploaded" })).toEqual({
      step: "reading",
      kind: "audio",
      sample: true,
    });
  });

  it("ignores progress outside an upload", () => {
    expect(flowReducer(IDLE, { type: "progress", progress: 0.4 })).toBe(IDLE);
  });

  it("moves reading to unread when the verdict never arrives", () => {
    const state = run([
      { type: "upload_started", kind: "photo", sample: false },
      { type: "uploaded" },
      { type: "unread" },
    ]);
    expect(state).toEqual({ step: "unread", sample: false });
  });

  it("records a failure and resets to idle", () => {
    const failed = run([{ type: "failed", reason: "upload" }]);
    expect(failed).toEqual({ step: "failed", reason: "upload" });
    expect(flowReducer(failed, { type: "reset" })).toBe(IDLE);
  });

  it("does not let a late photo replace a recording", () => {
    const state = run([
      { type: "preparing" },
      { type: "recording_started" },
      { type: "photo_chosen", photo: new Blob(["x"]), sample: false },
    ]);
    expect(state).toEqual({ step: "recording" });
  });

  it("starts a recording only after preparing", () => {
    expect(flowReducer(IDLE, { type: "recording_started" })).toBe(IDLE);
  });
});
