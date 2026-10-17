export const MAX_VIDEO_SECONDS = 30;
export const MAX_UPLOAD_BYTES = 26_214_400;
const METADATA_TIMEOUT_MS = 5_000;
const CONTENT_TYPE_BY_EXTENSION: Record<string, string> = {
  mp4: "video/mp4",
  mov: "video/quicktime",
};
const ALLOWED_TYPES = ["video/mp4", "video/quicktime"];

export type VideoRefusal = "type" | "size" | "long";

export class VideoRefusedError extends Error {
  override name = "VideoRefusedError";
  readonly refusal: VideoRefusal;

  constructor(refusal: VideoRefusal) {
    super(`The video was refused: ${refusal}`);
    this.refusal = refusal;
  }
}

function extensionOf(name: string): string {
  return name.split(".").pop()?.toLowerCase() ?? "";
}

export function videoContentType(file: Blob & { name?: string }): string {
  const declared = file.type.split(";")[0]?.trim() ?? "";
  if (ALLOWED_TYPES.includes(declared)) return declared;
  if (declared !== "") throw new VideoRefusedError("type");
  const inferred = CONTENT_TYPE_BY_EXTENSION[extensionOf(file.name ?? "")];
  if (inferred === undefined) throw new VideoRefusedError("type");
  return inferred;
}

export function readDuration(file: Blob): Promise<number | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const probe = document.createElement("video");
    const finish = (seconds: number | null) => {
      clearTimeout(timer);
      probe.removeAttribute("src");
      URL.revokeObjectURL(url);
      resolve(seconds);
    };
    const timer = setTimeout(() => finish(null), METADATA_TIMEOUT_MS);
    probe.preload = "metadata";
    probe.onloadedmetadata = () => finish(Number.isFinite(probe.duration) ? probe.duration : null);
    probe.onerror = () => finish(null);
    probe.src = url;
  });
}

export async function checkedVideo(
  file: Blob & { name?: string },
  duration: (file: Blob) => Promise<number | null> = readDuration,
): Promise<Blob> {
  const contentType = videoContentType(file);
  if (file.size > MAX_UPLOAD_BYTES) throw new VideoRefusedError("size");
  const seconds = await duration(file);
  if (seconds !== null && seconds > MAX_VIDEO_SECONDS) throw new VideoRefusedError("long");
  return file.type === contentType ? file : new Blob([file], { type: contentType });
}
