import { useCallback, useEffect, useRef, useState } from "react";
import {
  createReactionApiV1SiteInteractionsReactionsPost,
  deleteReactionApiV1SiteInteractionsReactionsContentTypeSlugReactionTypeDelete,
  readReactionApiV1SiteInteractionsReactionsContentTypeSlugReactionTypeGet,
} from "@serino/api-client/site-interactions";

export type ContentReactionSurface = "posts" | "diary" | "thoughts" | "excerpts" | "friends";

interface UseContentReactionOptions {
  contentType: ContentReactionSurface | null;
  slug: string | null;
  initialTotal?: number;
  reactionType?: string;
  enabled?: boolean;
}

interface ReactionUpdatedDetail {
  reactionKey: string;
  total: number;
  active: boolean;
}

const REACTION_TOKEN_STORAGE_PREFIX = "aerisun:reaction-token:";
const REACTION_UPDATED_EVENT = "aerisun:reaction-updated";

const createReactionClientToken = (reactionKey: string) => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${reactionKey}:${crypto.randomUUID()}`;
  }

  return `${reactionKey}:${Math.random().toString(36).slice(2)}`;
};

const readOrCreateReactionToken = (reactionKey: string) => {
  const storageKey = `${REACTION_TOKEN_STORAGE_PREFIX}${reactionKey}`;

  try {
    const existing = localStorage.getItem(storageKey);
    if (existing) {
      return existing;
    }

    const nextToken = createReactionClientToken(reactionKey);
    localStorage.setItem(storageKey, nextToken);
    return nextToken;
  } catch {
    return createReactionClientToken(reactionKey);
  }
};

export const useContentReaction = ({
  contentType,
  slug,
  initialTotal = 0,
  reactionType = "like",
  enabled = true,
}: UseContentReactionOptions) => {
  const reactionKey = enabled && contentType && slug ? `${contentType}:${slug}:${reactionType}` : null;
  const [count, setCount] = useState(initialTotal);
  const [active, setActive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [clientToken, setClientToken] = useState<string | null>(null);
  const syncVersionRef = useRef(0);

  useEffect(() => {
    setCount(initialTotal);
  }, [initialTotal, reactionKey]);

  useEffect(() => {
    if (!reactionKey) {
      setClientToken(null);
      setCount(initialTotal);
      setActive(false);
      return;
    }

    setClientToken(readOrCreateReactionToken(reactionKey));
  }, [initialTotal, reactionKey]);

  useEffect(() => {
    if (!reactionKey || !contentType || !slug || !clientToken) {
      return;
    }

    const syncVersion = ++syncVersionRef.current;

    readReactionApiV1SiteInteractionsReactionsContentTypeSlugReactionTypeGet(
      contentType,
      slug,
      reactionType,
      { client_token: clientToken },
    )
      .then((response) => {
        if (syncVersionRef.current !== syncVersion) {
          return;
        }

        setCount(response.data.total ?? initialTotal);
        setActive(Boolean(response.data.active));
      })
      .catch(() => {});
  }, [clientToken, contentType, initialTotal, reactionKey, reactionType, slug]);

  useEffect(() => {
    if (!reactionKey || typeof window === "undefined") {
      return;
    }

    const handleReactionUpdated = (event: Event) => {
      const detail = (event as CustomEvent<ReactionUpdatedDetail>).detail;
      if (!detail || detail.reactionKey !== reactionKey) {
        return;
      }

      setCount(detail.total);
      setActive(detail.active);
    };

    window.addEventListener(REACTION_UPDATED_EVENT, handleReactionUpdated as EventListener);
    return () => {
      window.removeEventListener(REACTION_UPDATED_EVENT, handleReactionUpdated as EventListener);
    };
  }, [reactionKey]);

  const toggle = useCallback(async () => {
    if (!reactionKey || !contentType || !slug || !clientToken || busy) {
      return false;
    }

    const syncVersion = ++syncVersionRef.current;
    setBusy(true);

    try {
      const response = active
        ? await deleteReactionApiV1SiteInteractionsReactionsContentTypeSlugReactionTypeDelete(
            contentType,
            slug,
            reactionType,
            { client_token: clientToken },
          )
        : await createReactionApiV1SiteInteractionsReactionsPost({
            content_type: contentType,
            content_slug: slug,
            reaction_type: reactionType,
            client_token: clientToken,
          });

      if (syncVersionRef.current !== syncVersion) {
        return false;
      }

      const nextTotal = response.data.total ?? Math.max(0, count + (active ? -1 : 1));
      const nextActive = Boolean(response.data.active ?? !active);

      setCount(nextTotal);
      setActive(nextActive);

      if (typeof window !== "undefined") {
        window.dispatchEvent(
          new CustomEvent<ReactionUpdatedDetail>(REACTION_UPDATED_EVENT, {
            detail: {
              reactionKey,
              total: nextTotal,
              active: nextActive,
            },
          }),
        );
      }

      return true;
    } catch {
      return false;
    } finally {
      if (syncVersionRef.current === syncVersion) {
        setBusy(false);
      }
    }
  }, [active, busy, clientToken, contentType, count, reactionKey, reactionType, slug]);

  return {
    active,
    busy,
    count,
    enabled: Boolean(reactionKey),
    toggle,
  };
};
