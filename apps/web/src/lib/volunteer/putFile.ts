export class UploadTransferError extends Error {
  override name = "UploadTransferError";
  readonly status: number | null;

  constructor(message: string, status: number | null = null) {
    super(message);
    this.status = status;
  }
}

export type PutFileInput = {
  url: string;
  blob: Blob;
  headers: Record<string, string>;
  onProgress: (fraction: number) => void;
  signal?: AbortSignal;
};

const PUT_TIMEOUT_MS = 120_000;

function isSuccess(status: number): boolean {
  return status >= 200 && status < 300;
}

function applyHeaders(request: XMLHttpRequest, headers: Record<string, string>): void {
  for (const [name, value] of Object.entries(headers)) request.setRequestHeader(name, value);
}

export function putFile(input: PutFileInput): Promise<void> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", input.url);
    applyHeaders(request, input.headers);
    request.timeout = PUT_TIMEOUT_MS;
    request.ontimeout = () => reject(new UploadTransferError("Upload timed out"));
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) input.onProgress(event.loaded / event.total);
    };
    request.onload = () => {
      if (isSuccess(request.status)) resolve();
      else reject(new UploadTransferError(`Upload returned ${request.status}`, request.status));
    };
    request.onerror = () => reject(new UploadTransferError("Upload could not reach the server"));
    request.onabort = () => reject(new UploadTransferError("Upload was cancelled"));
    input.signal?.addEventListener("abort", () => request.abort(), { once: true });
    request.send(input.blob);
  });
}
