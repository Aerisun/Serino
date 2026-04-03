import { useEffect, useState } from "react";
import {
  PREVIEW_REQUEST_MESSAGE,
  isPreviewDataMessage,
} from "@serino/utils";

export interface ContentPreviewData {
  type: "posts" | "diary" | "thoughts" | "excerpts" | "resume";
  slug?: string;
  title: string;
  summary?: string;
  body?: string;
  tags?: string[];
  status?: string;
  category?: string;
  mood?: string;
  weather?: string;
  poem?: string;
  published_at?: string | null;
  created_at?: string;
  location?: string;
  email?: string;
  profile_image_url?: string;
  author_name?: string;
  source?: string;
}

interface UsePreviewChannelResult<T> {
  data: T | null;
  isLoading: boolean;
}

const PREVIEW_WAIT_TIMEOUT = 1200;

export function usePreviewChannel<T = ContentPreviewData>(
  storageKey: string,
): UsePreviewChannelResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(storageKey));

  useEffect(() => {
    if (!storageKey) {
      setData(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    let timeoutId = 0;

    const readStoredData = () => {
      try {
        const raw = localStorage.getItem(storageKey);
        if (!raw) {
          return false;
        }

        setData(JSON.parse(raw) as T);
        setIsLoading(false);
        return true;
      } catch {
        return false;
      }
    };

    const hasStoredData = readStoredData();

    const onStorage = (event: StorageEvent) => {
      if (event.key !== storageKey || !event.newValue) {
        return;
      }

      try {
        const nextData = JSON.parse(event.newValue) as T;
        setData(nextData);
        setIsLoading(false);
      } catch {
        /* ignore invalid preview payloads */
      }
    };

    const onMessage = (event: MessageEvent) => {
      if (window.opener && event.source !== window.opener) {
        return;
      }
      if (!isPreviewDataMessage<T>(event.data)) return;
      if (event.data.storageKey !== storageKey) return;

      setData(event.data.payload);
      setIsLoading(false);

      try {
        localStorage.setItem(storageKey, JSON.stringify(event.data.payload));
      } catch {
        /* ignore storage write failures */
      }
    };

    window.addEventListener("storage", onStorage);
    window.addEventListener("message", onMessage);

    if (!hasStoredData && window.opener) {
      window.opener.postMessage(
        {
          type: PREVIEW_REQUEST_MESSAGE,
          storageKey,
        },
        "*",
      );
    }

    timeoutId = window.setTimeout(() => {
      setIsLoading(false);
    }, PREVIEW_WAIT_TIMEOUT);

    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("message", onMessage);
      window.clearTimeout(timeoutId);
    };
  }, [storageKey]);

  return { data, isLoading };
}
