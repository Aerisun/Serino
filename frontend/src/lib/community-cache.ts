import {
  readCommentsApiV1SiteInteractionsCommentsContentTypeSlugGet,
  readGuestbookApiV1SiteInteractionsGuestbookGet,
} from "@serino/api-client/site-interactions";
import type { CommunitySurface } from "@/lib/community-config";
import type { CommunityCommentItem, CommunityGuestbookItem } from "@/components/waline-types";

const COMMUNITY_CACHE_KEY_PREFIX = "aerisun:community-cache:";
const COMMUNITY_CACHE_TTL_MS = 5 * 60_000;

interface CacheEnvelope<T> {
  expiresAt: number;
  value: T;
}

interface CommunityPagePayload<T> {
  items: T[];
  hasMore: boolean;
  page: number;
  pageSize: number;
}

interface PageCacheParams {
  page: number;
  pageSize: number;
}

interface CommentPageCacheParams extends PageCacheParams {
  slug: string;
  surface: Exclude<CommunitySurface, "guestbook">;
}

const memoryCache = new Map<string, CacheEnvelope<unknown>>();
const inflightRequests = new Map<string, Promise<unknown>>();

const readStoredEnvelope = <T,>(key: string) => {
  const memoryHit = memoryCache.get(key) as CacheEnvelope<T> | undefined;
  const now = Date.now();
  if (memoryHit && memoryHit.expiresAt > now) {
    return memoryHit;
  }

  if (memoryHit) {
    memoryCache.delete(key);
  }

  if (typeof sessionStorage === "undefined") {
    return null;
  }

  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as CacheEnvelope<T>;
    if (!parsed || typeof parsed !== "object" || typeof parsed.expiresAt !== "number") {
      sessionStorage.removeItem(key);
      return null;
    }

    if (parsed.expiresAt <= now) {
      sessionStorage.removeItem(key);
      return null;
    }

    memoryCache.set(key, parsed as CacheEnvelope<unknown>);
    return parsed;
  } catch {
    try {
      sessionStorage.removeItem(key);
    } catch {
      // Ignore storage failures.
    }
    return null;
  }
};

const writeStoredEnvelope = <T,>(key: string, value: T, ttlMs = COMMUNITY_CACHE_TTL_MS) => {
  const envelope: CacheEnvelope<T> = {
    expiresAt: Date.now() + ttlMs,
    value,
  };

  memoryCache.set(key, envelope as CacheEnvelope<unknown>);

  if (typeof sessionStorage === "undefined") {
    return;
  }

  try {
    sessionStorage.setItem(key, JSON.stringify(envelope));
  } catch {
    // Ignore storage failures.
  }
};

const readCachedValue = <T,>(key: string) => readStoredEnvelope<T>(key)?.value ?? null;

const loadCachedValue = async <T,>(
  key: string,
  loader: () => Promise<T>,
  forceNetwork = false,
) => {
  if (!forceNetwork) {
    const cached = readCachedValue<T>(key);
    if (cached) {
      return cached;
    }
  }

  const existing = inflightRequests.get(key) as Promise<T> | undefined;
  if (existing) {
    return existing;
  }

  const request = loader()
    .then((value) => {
      writeStoredEnvelope(key, value);
      return value;
    })
    .finally(() => {
      inflightRequests.delete(key);
    });

  inflightRequests.set(key, request as Promise<unknown>);
  return request;
};

const buildGuestbookCacheKey = ({ page, pageSize }: PageCacheParams) =>
  `${COMMUNITY_CACHE_KEY_PREFIX}guestbook:${page}:${pageSize}`;

const buildCommentCacheKey = ({ surface, slug, page, pageSize }: CommentPageCacheParams) =>
  `${COMMUNITY_CACHE_KEY_PREFIX}${surface}:${encodeURIComponent(slug)}:${page}:${pageSize}`;

export const readCachedGuestbookPage = (params: PageCacheParams) =>
  readCachedValue<CommunityPagePayload<CommunityGuestbookItem>>(buildGuestbookCacheKey(params));

export const readCachedCommentPage = (params: CommentPageCacheParams) =>
  readCachedValue<CommunityPagePayload<CommunityCommentItem>>(buildCommentCacheKey(params));

export const primeGuestbookPage = async (
  params: PageCacheParams,
  options?: { forceNetwork?: boolean },
) =>
  loadCachedValue<CommunityPagePayload<CommunityGuestbookItem>>(
    buildGuestbookCacheKey(params),
    async () => {
      const response = await readGuestbookApiV1SiteInteractionsGuestbookGet({
        page: params.page,
        page_size: params.pageSize,
      });

      return {
        items: (response.data.items ?? []) as CommunityGuestbookItem[],
        hasMore: Boolean(response.data.has_more),
        page: params.page,
        pageSize: params.pageSize,
      };
    },
    options?.forceNetwork,
  );

export const primeCommentPage = async (
  params: CommentPageCacheParams,
  options?: { forceNetwork?: boolean },
) =>
  loadCachedValue<CommunityPagePayload<CommunityCommentItem>>(
    buildCommentCacheKey(params),
    async () => {
      const response = await readCommentsApiV1SiteInteractionsCommentsContentTypeSlugGet(
        params.surface,
        params.slug,
        {
          page: params.page,
          page_size: params.pageSize,
        },
      );

      return {
        items: (response.data.items ?? []) as CommunityCommentItem[],
        hasMore: Boolean(response.data.has_more),
        page: params.page,
        pageSize: params.pageSize,
      };
    },
    options?.forceNetwork,
  );

export const invalidateCommunityEntryCache = (
  surface: CommunitySurface,
  slug?: string,
) => {
  const prefix = surface === "guestbook"
    ? `${COMMUNITY_CACHE_KEY_PREFIX}guestbook:`
    : `${COMMUNITY_CACHE_KEY_PREFIX}${surface}:${encodeURIComponent(slug ?? "")}:`;

  for (const key of [...memoryCache.keys()]) {
    if (key.startsWith(prefix)) {
      memoryCache.delete(key);
    }
  }

  if (typeof sessionStorage === "undefined") {
    return;
  }

  try {
    for (let index = sessionStorage.length - 1; index >= 0; index -= 1) {
      const key = sessionStorage.key(index);
      if (key?.startsWith(prefix)) {
        sessionStorage.removeItem(key);
      }
    }
  } catch {
    // Ignore storage failures.
  }
};
