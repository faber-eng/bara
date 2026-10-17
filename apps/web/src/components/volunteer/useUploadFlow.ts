import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useReducer, useRef } from "react";
import { fetchInbox } from "../../lib/api/volunteer";
import type { UploadTicket } from "../../lib/api/volunteerTypes";
import type { Evidence, EvidenceKind, GeoPoint } from "../../lib/contracts";
import { readDeviceLocation } from "../../lib/geo";
import { type FailureReason, type FlowState, flowReducer, IDLE } from "../../lib/volunteer/flow";
import { resizePhoto } from "../../lib/volunteer/image";
import {
  baseContentType,
  startVoiceRecording,
  type VoiceRecorder,
} from "../../lib/volunteer/recorder";
import { uploadEvidence } from "../../lib/volunteer/upload";
import { waitForVerdict } from "../../lib/volunteer/verdictWait";
import { inboxKey } from "./inboxQuery";

type Pending = {
  blob: Blob;
  kind: EvidenceKind;
  sample: boolean;
  ticket: UploadTicket | null;
};

export type UploadFlow = {
  state: FlowState;
  choosePhoto: (file: Blob, sample: boolean) => Promise<void>;
  sendPhoto: () => Promise<void>;
  sendSampleVoice: (file: Blob) => Promise<void>;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<void>;
  retry: () => Promise<void>;
  reset: () => void;
};

type FlowTarget = { volunteerId: string; taskId: string };

async function readPoint(pending: Pending): Promise<GeoPoint | null> {
  if (pending.kind !== "photo" || pending.sample) return null;
  return readDeviceLocation().catch(() => null);
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

  async function send(pending: Pending) {
    lastSend.current = pending;
    dispatch({ type: "upload_started", kind: pending.kind, sample: pending.sample });
    try {
      const result = await uploadEvidence({
        volunteerId,
        taskId,
        kind: pending.kind,
        blob: pending.blob,
        contentType: contentTypeOf(pending),
        sample: pending.sample,
        point: await readPoint(pending),
        ticket: pending.ticket,
        onTicket: (ticket) => {
          pending.ticket = ticket;
        },
        onProgress: (progress) => dispatch({ type: "progress", progress }),
      });
      dispatch({ type: "uploaded" });
      await judge(result.evidenceId, result.evidence);
    } catch {
      fail("upload");
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

  async function sendPhoto() {
    if (state.step !== "preview") return;
    await send({ blob: state.photo, kind: "photo", sample: state.sample, ticket: null });
  }

  async function sendSampleVoice(file: Blob) {
    await send({ blob: file, kind: "audio", sample: true, ticket: null });
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
    } catch {
      fail("mic");
    }
  }

  async function stopRecording() {
    const active = recorder.current;
    recorder.current = null;
    if (active === null) return;
    try {
      const blob = await active.stop();
      if (blob.size === 0) throw new Error("The recording is empty");
      await send({ blob, kind: "audio", sample: false, ticket: null });
    } catch {
      fail("mic");
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
    sendSampleVoice,
    startRecording,
    stopRecording,
    retry,
    reset,
  };
}
