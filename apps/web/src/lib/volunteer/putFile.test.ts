import { afterEach, describe, expect, it, vi } from "vitest";
import { putFile, UploadTransferError } from "./putFile";

class FakeXhr {
  static last: FakeXhr;
  method = "";
  url = "";
  headers: Record<string, string> = {};
  sent: Blob | null = null;
  status = 0;
  upload: { onprogress: ((event: ProgressEvent) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  timeout = 0;

  constructor() {
    FakeXhr.last = this;
  }

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }

  send(blob: Blob) {
    this.sent = blob;
  }

  abort() {
    this.onabort?.();
  }
}

const TICKET_HEADERS = {
  "Content-Type": "image/jpeg",
  "x-goog-content-length-range": "0,26214400",
};

function start(onProgress = vi.fn()) {
  const blob = new Blob(["x"]);
  const done = putFile({ url: "https://gcs/put", blob, headers: TICKET_HEADERS, onProgress });
  return { blob, done, xhr: FakeXhr.last, onProgress };
}

describe("putFile", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("PUTs the blob and resolves on 200", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const { blob, done, xhr } = start();

    xhr.status = 200;
    xhr.onload?.();

    await expect(done).resolves.toBeUndefined();
    expect(xhr.method).toBe("PUT");
    expect(xhr.url).toBe("https://gcs/put");
    expect(xhr.sent).toBe(blob);
  });

  it("sets every header of the ticket on the request", () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const { xhr } = start();

    expect(xhr.headers).toEqual(TICKET_HEADERS);
  });

  it("reports progress as a fraction", () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const { xhr, onProgress } = start();

    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 25, total: 100 } as ProgressEvent);

    expect(onProgress).toHaveBeenCalledWith(0.25);
  });

  it("rejects on a non-2xx status", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const { done, xhr } = start();

    xhr.status = 403;
    xhr.onload?.();

    await expect(done).rejects.toBeInstanceOf(UploadTransferError);
  });

  it("rejects on a network error", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const { done, xhr } = start();

    xhr.onerror?.();

    await expect(done).rejects.toBeInstanceOf(UploadTransferError);
  });

  it("sets a timeout and rejects when it fires", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const { done, xhr } = start();

    expect(xhr.timeout).toBeGreaterThan(0);
    xhr.ontimeout?.();

    await expect(done).rejects.toBeInstanceOf(UploadTransferError);
  });
});
