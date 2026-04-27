import { useEffect, useRef, useState } from "react";
import {
  PREVIEW_DATA_MESSAGE,
  isPreviewRequestMessage,
} from "@serino/utils/preview";
import { useSystemInfoApiV1AdminSystemInfoGet } from "@serino/api-client/admin";
import { resolveFrontendUrl } from "@/lib/frontend-url";

interface UseContentPreviewOptions<T> {
  storageKey: string;
  payload: T;
  previewPath: string;
}

export function useContentPreview<T>({
  storageKey,
  payload,
  previewPath,
}: UseContentPreviewOptions<T>) {
  const [previewOpen, setPreviewOpen] = useState(false);
  const { data: systemInfo } = useSystemInfoApiV1AdminSystemInfoGet();
  const frontendUrl = resolveFrontendUrl(systemInfo?.site_url);
  const frontendOrigin = new URL(frontendUrl, window.location.origin).origin;
  const previewUrl = new URL(previewPath, `${frontendUrl}/`).toString();
  const previewWindowRef = useRef<Window | null>(null);
  const currentPreviewUrlRef = useRef(previewUrl);

  useEffect(() => {
    if (!previewOpen) return;

    const previewWindow = previewWindowRef.current;
    if (!previewWindow || previewWindow.closed) {
      setPreviewOpen(false);
      return;
    }

    localStorage.setItem(storageKey, JSON.stringify(payload));
    previewWindow.postMessage(
      {
        type: PREVIEW_DATA_MESSAGE,
        storageKey,
        payload,
      },
      frontendOrigin,
    );
  }, [frontendOrigin, payload, previewOpen, storageKey]);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== frontendOrigin) return;
      if (!isPreviewRequestMessage(event.data)) return;
      if (event.data.storageKey !== storageKey) return;
      if (!event.source) return;

      localStorage.setItem(storageKey, JSON.stringify(payload));
      (event.source as WindowProxy).postMessage(
        {
          type: PREVIEW_DATA_MESSAGE,
          storageKey,
          payload,
        },
        event.origin,
      );
    };

    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [frontendOrigin, payload, storageKey]);

  const openPreview = () => {
    const existingWindow = previewWindowRef.current;
    if (existingWindow && !existingWindow.closed) {
      localStorage.setItem(storageKey, JSON.stringify(payload));
      if (currentPreviewUrlRef.current !== previewUrl) {
        existingWindow.location.href = previewUrl;
        currentPreviewUrlRef.current = previewUrl;
        window.setTimeout(() => {
          if (existingWindow.closed) {
            setPreviewOpen(false);
            return;
          }

          existingWindow.postMessage(
            {
              type: PREVIEW_DATA_MESSAGE,
              storageKey,
              payload,
            },
            frontendOrigin,
          );
        }, 250);
      } else {
        existingWindow.postMessage(
          {
            type: PREVIEW_DATA_MESSAGE,
            storageKey,
            payload,
          },
          frontendOrigin,
        );
      }
      existingWindow.focus();
      setPreviewOpen(true);
      return;
    }

    localStorage.setItem(storageKey, JSON.stringify(payload));
    const previewWindow = window.open(previewUrl, "_blank");
    previewWindowRef.current = previewWindow;
    currentPreviewUrlRef.current = previewUrl;
    setPreviewOpen(Boolean(previewWindow));

    if (previewWindow) {
      window.setTimeout(() => {
        if (previewWindow.closed) {
          setPreviewOpen(false);
          return;
        }

        previewWindow.postMessage(
          {
            type: PREVIEW_DATA_MESSAGE,
            storageKey,
            payload,
          },
          frontendOrigin,
        );
      }, 250);
    }
  };

  return {
    frontendUrl,
    openPreview,
  };
}
