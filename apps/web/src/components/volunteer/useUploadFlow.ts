import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useReducer, useRef } from "react";
import { fetchSampleFile } from "../../lib/api/samples";
import { fetchInbox } from "../../lib/api/volunteer";
import type { Evidence, EvidenceKind, GeoPoint, SampleItem } from "../../lib/contracts";
import { readDeviceLocation } from "../../lib/geo";
import { isPermanentFailure } from "../../lib/volunteer/drain";
import { type FailureReason, type FlowState, flowReducer, IDLE } from "../../lib/volunteer/flow";
import { resizePhoto } from "../../lib/volunteer/image";
import { addOutboxItem } from "../../lib/volunteer/outbox";
import {
  baseContentType,
  MicError,
  type MicErrorKind,
  micKindOf,
  readMicPermission,
  requestMicrophoneAccess,
  startVoiceRecording,
  type VoiceRecorder,
} from "../../lib/volunteer/recorder";
import { type IssuedTicket, type UploadResult, uploadEvidence } from "../../lib/volunteer/upload";
import { waitForVerdict } from "../../lib/volunteer/verdictWait";
import { checkedVideo, type VideoRefusal, VideoRefusedError } from "../../lib/volunteer/video";
import { inboxKey } from "./inboxQuery";
import { outboxKey } from "./outboxQuery";

type Pending = {
  blob: Blob;
  kind: EvidenceKind;
  sample: boolean;
  ticket: IssuedTicket | null;
  capturedAt: string;
};

export type UploadFlow = {
  state: FlowState;
  choosePhoto: (file: Blob, sample: boolean) => Promise<void>;
  sendPhoto: () => Promise<void>;
  chooseSample: (item: SampleItem) => Promise<void>;
  chooseVideo: (file: Blob) => Promise<void>;
  askMicrophone: () => Promise<void>;
  allowMicrophone: () => Promise<void>;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<void>;
  retry: () => Promise<void>;
  reset: () => void;
};

type FlowTarget = { volunteerId: string; taskId: string };

async function readPoint(pending: Pending): Promise<GeoPoint | null> {
  if (pending.kind === "audio" || pending.sample) return null;
  return readDeviceLocation().catch(() => null);
}

const VIDEO_FAILURES: Record<VideoRefusal, FailureReason> = {
  type: "video_type",
  size: "video_big",
  long: "video_long",
};

const MIC_FAILURES: Record<MicErrorKind, FailureReason> = {
  denied: "mic_denied",
  no_device: "mic_no_device",
  busy: "mic_busy",
  unsupported: "mic_unsupported",
  recorder_failed: "mic_failed",
};

function micFailureOf(error: unknown): FailureReason {
  return MIC_FAILURES[error instanceof MicError ? error.kind : micKindOf(error)];
}

function newPending(blob: Blob, kind: EvidenceKind, sample: boolean): Pending {
  return { blob, kind, sample, ticket: null, capturedAt: new Date().toISOString() };
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function contentTypeOf(pending: Pending): string {
  return pending.kind === "photo" ? "image/jpeg" : baseContentType(pending.blob.type);
}

export function useUploadFlow({ volunteerId, taskId }: FlowTarget): UploadFlow {
  const [state, dispatch] = useReducer(flowReducer, IDLE);
  const queryClient = useQueryClient();
  const lastSend = useRef<Pending | null>(null);
  const recorder = useRef<VoiceRecorder | null>(null);
  const cancelled = useRef(false);

  useEffect(() => {
    cancelled.current = false;
    return () => {
      cancelled.current = true;
      recorder.current?.cancel();
      recorder.current = null;
    };
  }, []);

  function fail(reason: FailureReason) {
    dispatch({ type: "failed", reason });
  }

  async function findVerdict(evidenceId: string): Promise<Evidence | null> {
    return waitForVerdict({
      evidenceId,
      wait: sleep,
      isCancelled: () => cancelled.current,
      readEvidence: async () => (await fetchInbox(volunteerId)).evidence,
    });
  }

  async function judge(evidenceId: string, early: Evidence | null) {
    try {
      const evidence = early?.verdict ? early : await findVerdict(evidenceId);
      dispatch(evidence === null ? { type: "unread" } : { type: "judged", evidence });
    } catch {
      fail("read");
    } finally {
      void queryClient.invalidateQueries({ queryKey: inboxKey(volunteerId) });
    }
  }

  async function settle(result: UploadResult) {
    dispatch({ type: "uploaded" });
    await judge(result.evidenceId, result.evidence);
  }

  async function queueForLater(pending: Pending, point: GeoPoint | null) {
    try {
      await addOutboxItem({
        volunteerId,
        taskId,
        kind: pending.kind,
        contentType: contentTypeOf(pending),
        blob: pending.blob,
        sample: pending.sample,
        point,
        capturedAt: pending.capturedAt,
        ticket: pending.ticket,
      });
    } catch {
      fail("upload");
      return;
    }
    dispatch({ type: "queued" });
    void queryClient.invalidateQueries({ queryKey: outboxKey(volunteerId) });
  }

  async function send(pending: Pending) {
    lastSend.current = pending;
    dispatch({ type: "upload_started", kind: pending.kind, sample: pending.sample });
    const point = await readPoint(pending);
    try {
      const result = await uploadEvidence({
        volunteerId,
        taskId,
        kind: pending.kind,
        blob: pending.blob,
        contentType: contentTypeOf(pending),
        sample: pending.sample,
        point,
        capturedAt: pending.capturedAt,
        ticket: pending.ticket,
        onTicket: (issued) => {
          pending.ticket = issued;
        },
        onProgress: (progress) => dispatch({ type: "progress", progress }),
      });
      await settle(result);
    } catch (error) {
      if (isPermanentFailure(error)) fail("upload");
      else await queueForLater(pending, point);
    }
  }

  async function choosePhoto(file: Blob, sample: boolean) {
    dispatch({ type: "preparing" });
    try {
      dispatch({ type: "photo_chosen", photo: await resizePhoto(file), sample });
    } catch {
      fail("prepare");
    }
  }

  async function chooseVideo(file: Blob) {
    dispatch({ type: "preparing" });
    try {
      const video = await checkedVideo(file);
      await send(newPending(video, "video", false));
    } catch (error) {
      fail(error instanceof VideoRefusedError ? VIDEO_FAILURES[error.refusal] : "prepare");
    }
  }

  async function sendPhoto() {
    if (state.step !== "preview") return;
    await send(newPending(state.photo, "photo", state.sample));
  }

  async function chooseSample(item: SampleItem) {
    if (state.step !== "idle") return;
    dispatch({ type: "preparing" });
    try {
      const file = await fetchSampleFile(item);
      if (cancelled.current) return;
      await sendSampleFile(item, file);
    } catch {
      fail("prepare");
    }
  }

  async function sendSampleFile(item: SampleItem, file: Blob) {
    if (item.kind === "photo") {
      dispatch({ type: "photo_chosen", photo: await resizePhoto(file), sample: true });
      return;
    }
    if (item.kind === "voice" && baseContentType(file.type) !== "") {
      await send(newPending(file, "audio", true));
      return;
    }
    throw new Error("The sample cannot be sent as evidence");
  }

  async function startRecording() {
    dispatch({ type: "preparing" });
    try {
      const started = await startVoiceRecording();
      if (cancelled.current) {
        started.cancel();
        return;
      }
      recorder.current = started;
      dispatch({ type: "recording_started" });
    } catch (error) {
      fail(micFailureOf(error));
    }
  }

  async function askMicrophone() {
    dispatch({ type: "preparing" });
    const permission = await readMicPermission();
    if (cancelled.current) return;
    if (permission === "denied") fail("mic_denied");
    else if (permission === "granted") await startRecording();
    else dispatch({ type: "mic_gate_opened" });
  }

  async function allowMicrophone() {
    try {
      await requestMicrophoneAccess();
      dispatch({ type: "mic_allowed" });
    } catch (error) {
      fail(micFailureOf(error));
    }
  }

  async function stopRecording() {
    const active = recorder.current;
    recorder.current = null;
    if (active === null) return;
    try {
      const blob = await active.stop();
      if (blob.size === 0) throw new Error("The recording is empty");
      await send(newPending(blob, "audio", false));
    } catch (error) {
      fail(micFailureOf(error));
    }
  }

  async function retry() {
    if (lastSend.current !== null) await send(lastSend.current);
  }

  function reset() {
    lastSend.current = null;
    dispatch({ type: "reset" });
  }

  return {
    state,
    choosePhoto,
    sendPhoto,
    chooseSample,
    chooseVideo,
    askMicrophone,
    allowMicrophone,
    startRecording,
    stopRecording,
    retry,
    reset,
  };
}
