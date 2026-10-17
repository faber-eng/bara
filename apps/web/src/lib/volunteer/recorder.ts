export class MicUnavailableError extends Error {
  override name = "MicUnavailableError";
}

export type VoiceRecorder = { stop: () => Promise<Blob>; cancel: () => void };

const PREFERRED_TYPE = "audio/webm";

export function baseContentType(mime: string): string {
  return mime.split(";")[0]?.trim() ?? "";
}

function pickMimeType(): string | undefined {
  return MediaRecorder.isTypeSupported(PREFERRED_TYPE) ? PREFERRED_TYPE : undefined;
}

async function openMicrophone(): Promise<MediaStream> {
  try {
    return await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    throw new MicUnavailableError("The microphone could not be opened");
  }
}

function releaseTracks(stream: MediaStream): void {
  for (const track of stream.getTracks()) track.stop();
}

function recordingBlob(chunks: Blob[], recorder: MediaRecorder): Blob {
  return new Blob(chunks, { type: baseContentType(recorder.mimeType) });
}

function beginRecording(stream: MediaStream): VoiceRecorder {
  const recorder = new MediaRecorder(stream, { mimeType: pickMimeType() });
  const chunks: Blob[] = [];
  const finished = new Promise<Blob>((resolve, reject) => {
    recorder.onstop = () => {
      releaseTracks(stream);
      resolve(recordingBlob(chunks, recorder));
    };
    recorder.onerror = () => {
      releaseTracks(stream);
      reject(new MicUnavailableError("The recording failed"));
    };
  });
  recorder.ondataavailable = (event) => chunks.push(event.data);
  recorder.start();
  return {
    stop: () => {
      if (recorder.state === "inactive") releaseTracks(stream);
      else recorder.stop();
      return recorder.state === "inactive" && chunks.length === 0
        ? Promise.reject(new MicUnavailableError("The recording had stopped"))
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
    throw new MicUnavailableError("The recorder could not start");
  }
}
