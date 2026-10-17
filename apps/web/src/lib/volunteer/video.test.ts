import { describe, expect, it } from "vitest";
import {
  checkedVideo,
  MAX_UPLOAD_BYTES,
  MAX_VIDEO_SECONDS,
  VideoRefusedError,
  videoContentType,
} from "./video";

function clip(type: string, name = "clip", size = 3): File {
  return new File([new Uint8Array(size)], name, { type });
}

async function refusalOf(action: Promise<unknown>): Promise<string> {
  try {
    await action;
  } catch (error) {
    if (error instanceof VideoRefusedError) return error.refusal;
    throw error;
  }
  return "none";
}

describe("videoContentType", () => {
  it("accepts MP4 and QuickTime", () => {
    expect(videoContentType(clip("video/mp4"))).toBe("video/mp4");
    expect(videoContentType(clip("video/quicktime"))).toBe("video/quicktime");
  });

  it("reads the type from the extension when the browser leaves it empty", () => {
    expect(videoContentType(clip("", "IMG_1.MOV"))).toBe("video/quicktime");
    expect(videoContentType(clip("", "a.mp4"))).toBe("video/mp4");
  });

  it("refuses webm and unknown files", () => {
    expect(() => videoContentType(clip("video/webm"))).toThrow(VideoRefusedError);
    expect(() => videoContentType(clip("", "notes.txt"))).toThrow(VideoRefusedError);
  });
});

describe("checkedVideo", () => {
  it("passes a clip of exactly the limit", async () => {
    const file = clip("video/mp4");
    expect(await checkedVideo(file, async () => MAX_VIDEO_SECONDS)).toBe(file);
  });

  it("refuses a clip over the limit", async () => {
    expect(await refusalOf(checkedVideo(clip("video/mp4"), async () => 31))).toBe("long");
  });

  it("lets the server decide when the length cannot be read", async () => {
    const file = clip("video/mp4");
    expect(await checkedVideo(file, async () => null)).toBe(file);
  });

  it("refuses a file over the upload cap", async () => {
    const big = clip("video/mp4", "big.mp4", MAX_UPLOAD_BYTES + 1);
    expect(await refusalOf(checkedVideo(big, async () => 5))).toBe("size");
  });

  it("gives a file with an inferred type that type", async () => {
    const checked = await checkedVideo(clip("", "IMG.MOV"), async () => 5);
    expect(checked.type).toBe("video/quicktime");
  });
});
