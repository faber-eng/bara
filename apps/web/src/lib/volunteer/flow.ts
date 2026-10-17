import type { Evidence, EvidenceKind } from "../contracts";

export type FailureReason = "prepare" | "upload" | "read" | "mic";

export type FlowState =
  | { step: "idle" }
  | { step: "preparing" }
  | { step: "preview"; photo: Blob; sample: boolean }
  | { step: "recording" }
  | { step: "uploading"; kind: EvidenceKind; progress: number; sample: boolean }
  | { step: "reading"; kind: EvidenceKind; sample: boolean }
  | { step: "done"; evidence: Evidence }
  | { step: "unread"; sample: boolean }
  | { step: "failed"; reason: FailureReason };

export type FlowAction =
  | { type: "preparing" }
  | { type: "photo_chosen"; photo: Blob; sample: boolean }
  | { type: "recording_started" }
  | { type: "upload_started"; kind: EvidenceKind; sample: boolean }
  | { type: "progress"; progress: number }
  | { type: "uploaded" }
  | { type: "judged"; evidence: Evidence }
  | { type: "unread" }
  | { type: "failed"; reason: FailureReason }
  | { type: "reset" };

export const IDLE: FlowState = { step: "idle" };

function onChosen(state: FlowState, action: { photo: Blob; sample: boolean }): FlowState {
  if (state.step !== "preparing") return state;
  return { step: "preview", photo: action.photo, sample: action.sample };
}

function onProgress(state: FlowState, progress: number): FlowState {
  if (state.step !== "uploading") return state;
  return { ...state, progress };
}

function onUploaded(state: FlowState): FlowState {
  if (state.step !== "uploading") return state;
  return { step: "reading", kind: state.kind, sample: state.sample };
}

function onUnread(state: FlowState): FlowState {
  if (state.step !== "reading") return state;
  return { step: "unread", sample: state.sample };
}

export function flowReducer(state: FlowState, action: FlowAction): FlowState {
  switch (action.type) {
    case "preparing":
      return state.step === "idle" ? { step: "preparing" } : state;
    case "photo_chosen":
      return onChosen(state, action);
    case "recording_started":
      return state.step === "preparing" ? { step: "recording" } : state;
    case "upload_started":
      return { step: "uploading", kind: action.kind, progress: 0, sample: action.sample };
    case "progress":
      return onProgress(state, action.progress);
    case "uploaded":
      return onUploaded(state);
    case "judged":
      return { step: "done", evidence: action.evidence };
    case "unread":
      return onUnread(state);
    case "failed":
      return { step: "failed", reason: action.reason };
    case "reset":
      return IDLE;
    default:
      return unhandledAction(action);
  }
}

function unhandledAction(action: never): never {
  throw new Error(`unhandled flow action: ${JSON.stringify(action)}`);
}
