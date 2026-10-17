export const MAX_PHOTO_EDGE = 1600;
export const PHOTO_QUALITY = 0.8;

export type Size = { width: number; height: number };

export class PhotoPrepareError extends Error {
  override name = "PhotoPrepareError";
}

export function fitWithin(size: Size, maxEdge: number): Size {
  const longest = Math.max(size.width, size.height);
  if (longest <= maxEdge) return size;
  const scale = maxEdge / longest;
  return { width: Math.round(size.width * scale), height: Math.round(size.height * scale) };
}

function canvasToJpeg(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob === null) reject(new PhotoPrepareError("The photo could not be encoded"));
        else resolve(blob);
      },
      "image/jpeg",
      PHOTO_QUALITY,
    );
  });
}

async function decode(file: Blob): Promise<ImageBitmap> {
  try {
    return await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    throw new PhotoPrepareError("The photo could not be read");
  }
}

export async function resizePhoto(file: Blob): Promise<Blob> {
  const bitmap = await decode(file);
  const target = fitWithin({ width: bitmap.width, height: bitmap.height }, MAX_PHOTO_EDGE);
  const canvas = document.createElement("canvas");
  canvas.width = target.width;
  canvas.height = target.height;
  const context = canvas.getContext("2d");
  if (context === null) {
    bitmap.close();
    throw new PhotoPrepareError("The photo could not be drawn");
  }
  context.drawImage(bitmap, 0, 0, target.width, target.height);
  bitmap.close();
  return canvasToJpeg(canvas);
}
