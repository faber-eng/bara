import { afterEach, describe, expect, it, vi } from "vitest";
import {
  baseContentType,
  MicError,
  micKindOf,
  pickMimeType,
  readMicPermission,
  requestMicrophoneAccess,
  startVoiceRecording,
} from "./recorder";

afterEach(() => vi.unstubAllGlobals());

function domError(name: string): Error {
  const error = new Error(name);
  error.name = name;
  return error;
}

function stubMicrophone(getUserMedia: () => Promise<unknown>) {
  vi.stubGlobal("navigator", { mediaDevices: { getUserMedia } });
  vi.stubGlobal("MediaRecorder", class {});
}

describe("baseContentType", () => {
  it("drops the codec parameter", () => {
    expect(baseContentType("audio/webm;codecs=opus")).toBe("audio/webm");
    expect(baseContentType("audio/mp4")).toBe("audio/mp4");
  });
});

describe("micKindOf", () => {
  it("maps browser errors to a kind", () => {
    expect(micKindOf(domError("NotAllowedError"))).toBe("denied");
    expect(micKindOf(domError("SecurityError"))).toBe("denied");
    expect(micKindOf(domError("NotFoundError"))).toBe("no_device");
    expect(micKindOf(domError("OverconstrainedError"))).toBe("no_device");
    expect(micKindOf(domError("NotReadableError"))).toBe("busy");
    expect(micKindOf(domError("AbortError"))).toBe("busy");
    expect(micKindOf(domError("Other"))).toBe("recorder_failed");
    expect(micKindOf("nope")).toBe("recorder_failed");
  });
});

describe("pickMimeType", () => {
  it("prefers webm, then mp4, then nothing", () => {
    const supports = (allowed: string[]) => (type: string) => allowed.includes(type);
    expect(pickMimeType(supports(["audio/webm", "audio/mp4"]))).toBe("audio/webm");
    expect(pickMimeType(supports(["audio/mp4"]))).toBe("audio/mp4");
    expect(pickMimeType(supports([]))).toBeUndefined();
    expect(pickMimeType(undefined)).toBeUndefined();
  });
});

describe("startVoiceRecording", () => {
  it("throws unsupported without getUserMedia", async () => {
    vi.stubGlobal("navigator", {});
    vi.stubGlobal("MediaRecorder", class {});
    await expect(startVoiceRecording()).rejects.toMatchObject({ kind: "unsupported" });
  });

  it("throws unsupported without MediaRecorder", async () => {
    vi.stubGlobal("navigator", { mediaDevices: { getUserMedia: async () => ({}) } });
    vi.stubGlobal("MediaRecorder", undefined);
    await expect(startVoiceRecording()).rejects.toMatchObject({ kind: "unsupported" });
  });

  it("keeps the cause of a denied prompt", async () => {
    stubMicrophone(() => Promise.reject(domError("NotAllowedError")));
    const failure = await startVoiceRecording().catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(MicError);
    expect(failure).toMatchObject({ kind: "denied" });
  });

  it("reports recorder_failed when the recorder cannot be built", async () => {
    const stop = vi.fn();
    stubMicrophone(async () => ({ getTracks: () => [{ stop }] }));
    vi.stubGlobal(
      "MediaRecorder",
      class {
        constructor() {
          throw domError("NotSupportedError");
        }
      },
    );
    await expect(startVoiceRecording()).rejects.toMatchObject({ kind: "recorder_failed" });
    expect(stop).toHaveBeenCalled();
  });
});

describe("requestMicrophoneAccess", () => {
  it("opens the microphone once and releases the tracks", async () => {
    const stop = vi.fn();
    const getUserMedia = vi.fn(async () => ({ getTracks: () => [{ stop }] }));
    stubMicrophone(getUserMedia);
    await requestMicrophoneAccess();
    expect(getUserMedia).toHaveBeenCalledTimes(1);
    expect(stop).toHaveBeenCalledTimes(1);
  });

  it("throws the mapped kind on refusal", async () => {
    stubMicrophone(() => Promise.reject(domError("NotFoundError")));
    await expect(requestMicrophoneAccess()).rejects.toMatchObject({ kind: "no_device" });
  });
});

describe("readMicPermission", () => {
  it("returns prompt when the permissions API is missing or throws", async () => {
    vi.stubGlobal("navigator", {});
    expect(await readMicPermission()).toBe("prompt");
    vi.stubGlobal("navigator", { permissions: { query: () => Promise.reject(new Error("x")) } });
    expect(await readMicPermission()).toBe("prompt");
  });

  it("returns the browser state", async () => {
    vi.stubGlobal("navigator", { permissions: { query: async () => ({ state: "granted" }) } });
    expect(await readMicPermission()).toBe("granted");
    vi.stubGlobal("navigator", { permissions: { query: async () => ({ state: "denied" }) } });
    expect(await readMicPermission()).toBe("denied");
  });
});
