export class UploadTransferError extends Error {
  override name = "UploadTransferError";
}

export type PutFileInput = {
  url: string;
  blob: Blob;
  contentType: string;
  onProgress: (fraction: number) => void;
  signal?: AbortSignal;
};

const PUT_TIMEOUT_MS = 120_000;

function isSuccess(status: number): boolean {
  return status >= 200 && status < 300;
}

export function putFile(input: PutFileInput): Promise<void> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", input.url);
    request.setRequestHeader("Content-Type", input.contentType);
    request.timeout = PUT_TIMEOUT_MS;
    request.ontimeout = () => reject(new UploadTransferError("Upload timed out"));
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) input.onProgress(event.loaded / event.total);
    };
    request.onload = () => {
      if (isSuccess(request.status)) resolve();
      else reject(new UploadTransferError(`Upload returned ${request.status}`));
    };
    request.onerror = () => reject(new UploadTransferError("Upload could not reach the server"));
    request.onabort = () => reject(new UploadTransferError("Upload was cancelled"));
    input.signal?.addEventListener("abort", () => request.abort(), { once: true });
    request.send(input.blob);
  });
}
