export type MicErrorKind = "denied" | "no_device" | "busy" | "unsupported" | "recorder_failed";

export class MicError extends Error {
  override name = "MicError";
  readonly kind: MicErrorKind;

  constructor(kind: MicErrorKind, message: string) {
    super(message);
    this.kind = kind;
  }
}

export type VoiceRecorder = { stop: () => Promise<Blob>; cancel: () => void };

export type MicPermission = "granted" | "prompt" | "denied";

const PREFERRED_TYPES = ["audio/webm", "audio/mp4"];

const KIND_BY_ERROR_NAME: Record<string, MicErrorKind> = {
  NotAllowedError: "denied",
  SecurityError: "denied",
  NotFoundError: "no_device",
  OverconstrainedError: "no_device",
  NotReadableError: "busy",
  AbortError: "busy",
};

export function baseContentType(mime: string): string {
  return mime.split(";")[0]?.trim() ?? "";
}

export function micKindOf(error: unknown): MicErrorKind {
  if (!(error instanceof Error)) return "recorder_failed";
  return KIND_BY_ERROR_NAME[error.name] ?? "recorder_failed";
}

export function pickMimeType(isTypeSupported: ((type: string) => boolean) | undefined) {
  if (!isTypeSupported) return undefined;
  return PREFERRED_TYPES.find((type) => isTypeSupported(type));
}

function assertSupported(): void {
  const hasMicrophone = typeof navigator.mediaDevices?.getUserMedia === "function";
  const hasRecorder = typeof MediaRecorder !== "undefined";
  if (!hasMicrophone || !hasRecorder) {
    throw new MicError("unsupported", "This browser cannot record audio");
  }
}

async function openMicrophone(): Promise<MediaStream> {
  assertSupported();
  try {
    return await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (error) {
    throw new MicError(micKindOf(error), "The microphone could not be opened");
  }
}

function newMediaRecorder(stream: MediaStream): MediaRecorder {
  const mimeType = pickMimeType(MediaRecorder.isTypeSupported?.bind(MediaRecorder));
  return mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
}

export async function readMicPermission(): Promise<MicPermission> {
  try {
    const status = await navigator.permissions?.query({ name: "microphone" as PermissionName });
    return status?.state ?? "prompt";
  } catch {
    return "prompt";
  }
}

export async function requestMicrophoneAccess(): Promise<void> {
  releaseTracks(await openMicrophone());
}

function releaseTracks(stream: MediaStream): void {
  for (const track of stream.getTracks()) track.stop();
}

function recordingBlob(chunks: Blob[], recorder: MediaRecorder): Blob {
  return new Blob(chunks, { type: baseContentType(recorder.mimeType) });
}

function beginRecording(stream: MediaStream): VoiceRecorder {
  const recorder = newMediaRecorder(stream);
  const chunks: Blob[] = [];
  const finished = new Promise<Blob>((resolve, reject) => {
    recorder.onstop = () => {
      releaseTracks(stream);
      resolve(recordingBlob(chunks, recorder));
    };
    recorder.onerror = () => {
      releaseTracks(stream);
      reject(new MicError("recorder_failed", "The recording failed"));
    };
  });
  recorder.ondataavailable = (event) => chunks.push(event.data);
  recorder.start();
  return {
    stop: () => {
      if (recorder.state === "inactive") releaseTracks(stream);
      else recorder.stop();
      return recorder.state === "inactive" && chunks.length === 0
        ? Promise.reject(new MicError("recorder_failed", "The recording had stopped"))
        : finished;
    },
    cancel: () => {
      recorder.onstop = null;
      if (recorder.state !== "inactive") recorder.stop();
      releaseTracks(stream);
    },
  };
}

export async function startVoiceRecording(): Promise<VoiceRecorder> {
  const stream = await openMicrophone();
  try {
    return beginRecording(stream);
  } catch {
    releaseTracks(stream);
    throw new MicError("recorder_failed", "The recorder could not start");
  }
}
