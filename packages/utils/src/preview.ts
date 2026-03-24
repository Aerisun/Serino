export const PREVIEW_REQUEST_MESSAGE = "aerisun-preview:request";
export const PREVIEW_DATA_MESSAGE = "aerisun-preview:data";

interface PreviewMessageBase {
  storageKey: string;
}

export interface PreviewRequestMessage extends PreviewMessageBase {
  type: typeof PREVIEW_REQUEST_MESSAGE;
}

export interface PreviewDataMessage<T = unknown> extends PreviewMessageBase {
  type: typeof PREVIEW_DATA_MESSAGE;
  payload: T;
}

export const isPreviewRequestMessage = (
  value: unknown,
): value is PreviewRequestMessage => {
  if (!value || typeof value !== "object") {
    return false;
  }

  const message = value as Partial<PreviewRequestMessage>;
  return (
    message.type === PREVIEW_REQUEST_MESSAGE &&
    typeof message.storageKey === "string"
  );
};

export const isPreviewDataMessage = <T = unknown>(
  value: unknown,
): value is PreviewDataMessage<T> => {
  if (!value || typeof value !== "object") {
    return false;
  }

  const message = value as Partial<PreviewDataMessage<T>>;
  return (
    message.type === PREVIEW_DATA_MESSAGE &&
    typeof message.storageKey === "string" &&
    "payload" in message
  );
};
