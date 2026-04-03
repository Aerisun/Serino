const COMPRESSIBLE_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

export interface CompressImageOptions {
  maxDimension?: number;
  quality?: number;
  minBytesToCompress?: number;
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
  const { maxDimension = 1920, quality = 0.82, minBytesToCompress = 300 * 1024 } = options;

  if (!canCompressImage(file) || file.size < minBytesToCompress) {
    return file;
  }

  const image = await loadImage(file);
  const scale = Math.min(1, maxDimension / Math.max(image.width, image.height));
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

  const outputType = file.type === "image/png" ? "image/png" : "image/jpeg";
  const outputQuality = outputType === "image/png" ? undefined : quality;
  const blob = await canvasToBlob(canvas, outputType, outputQuality);

  if (blob.size >= file.size) {
    return file;
  }

  const extension = outputType === "image/png" ? "png" : "jpg";
  const baseName = file.name.replace(/\.[^.]+$/, "");
  return new File([blob], `${baseName}.${extension}`, {
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
