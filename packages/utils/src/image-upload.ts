const COMPRESSIBLE_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const DEFAULT_COMPRESSED_IMAGE_TYPE = "image/webp";
const DEFAULT_TARGET_MAX_BYTES = 512 * 1024;

export interface CompressImageOptions {
  maxDimension?: number;
  quality?: number;
  minBytesToCompress?: number;
  targetMaxBytes?: number;
}

export type UploadImageMode = "compress" | "original";

export interface PrepareImageUploadFileOptions extends CompressImageOptions {
  mode?: UploadImageMode;
}

function loadImage(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Failed to load image"));
    };
    image.src = url;
  });
}

function canvasToBlob(canvas: HTMLCanvasElement, type: string, quality?: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("Failed to export compressed image"));
        return;
      }
      resolve(blob);
    }, type, quality);
  });
}

export function canCompressImage(file: File): boolean {
  return COMPRESSIBLE_IMAGE_TYPES.has(file.type);
}

export async function compressImageFile(
  file: File,
  options: CompressImageOptions = {},
): Promise<File> {
  const {
    maxDimension = 1920,
    quality = 0.82,
    targetMaxBytes = DEFAULT_TARGET_MAX_BYTES,
    minBytesToCompress = targetMaxBytes,
  } = options;

  if (!canCompressImage(file) || file.size < minBytesToCompress) {
    return file;
  }

  const image = await loadImage(file);
  const longestEdge = Math.max(image.width, image.height);
  const outputType = DEFAULT_COMPRESSED_IMAGE_TYPE;
  const buildCandidate = async (dimensionLimit: number, outputQuality: number): Promise<Blob> => {
    const scale = Math.min(1, dimensionLimit / longestEdge);
    const width = Math.max(1, Math.round(image.width * scale));
    const height = Math.max(1, Math.round(image.height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;

    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Canvas is not supported");
    }

    context.drawImage(image, 0, 0, width, height);
    return canvasToBlob(canvas, outputType, outputQuality);
  };

  const targetRatio = Math.min(1, Math.sqrt(targetMaxBytes / file.size));
  const firstDimensionLimit = Math.max(960, Math.min(maxDimension, Math.round(longestEdge * Math.max(targetRatio * 1.08, 0.72))));
  const firstQuality = Math.max(0.7, Math.min(0.9, quality));

  let bestBlob = await buildCandidate(firstDimensionLimit, firstQuality);

  if (bestBlob.size > targetMaxBytes) {
    const secondRatio = Math.min(1, Math.sqrt(targetMaxBytes / bestBlob.size));
    const secondDimensionLimit = Math.max(
      840,
      Math.min(firstDimensionLimit, Math.round(firstDimensionLimit * Math.max(secondRatio * 0.98, 0.82))),
    );
    const secondQuality = Math.max(0.64, Math.min(firstQuality - 0.06, 0.82));
    const secondBlob = await buildCandidate(secondDimensionLimit, secondQuality);
    if (
      Math.abs(secondBlob.size - targetMaxBytes) < Math.abs(bestBlob.size - targetMaxBytes)
      || (secondBlob.size <= targetMaxBytes && bestBlob.size > targetMaxBytes)
    ) {
      bestBlob = secondBlob;
    }
  }

  if (!bestBlob || bestBlob.size >= file.size) {
    return file;
  }

  const extension = outputType === "image/webp" ? "webp" : "jpg";
  const baseName = file.name.replace(/\.[^.]+$/, "");
  return new File([bestBlob], `${baseName}.${extension}`, {
    type: outputType,
    lastModified: Date.now(),
  });
}

export async function prepareImageUploadFile(
  file: File,
  options: PrepareImageUploadFileOptions = {},
): Promise<File> {
  const { mode = "original", ...compressOptions } = options;

  if (mode !== "compress") {
    return file;
  }

  return compressImageFile(file, compressOptions);
}
