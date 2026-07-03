import type { QueryClient } from "@tanstack/react-query";
import type { ContentEntryRead } from "@serino/api-client/models";
import { getReadPostApiV1SitePostsSlugGetQueryKey } from "@serino/api-client/site";

type ContentCollectionPage = {
  items?: unknown;
  has_more?: unknown;
  total?: unknown;
};

type InfiniteContentList = {
  pages?: ContentCollectionPage[];
  pageParams?: unknown[];
};

type ContentDetailResponse = {
  data?: ContentEntryRead;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const sameSlug = (value: unknown, slug: string) =>
  typeof value === "string" && value === slug;

const incrementViewCount = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value) ? value + 1 : 1;

const incrementEntryViewCount = <T extends ContentEntryRead>(entry: T, slug: string): T => {
  if (!sameSlug(entry.slug, slug)) {
    return entry;
  }
  return {
    ...entry,
    view_count: incrementViewCount(entry.view_count),
  };
};

const updateCollectionPage = (page: ContentCollectionPage, slug: string) => {
  if (!Array.isArray(page.items)) {
    return page;
  }

  let changed = false;
  const items = page.items.map((item) => {
    if (!isRecord(item) || !sameSlug(item.slug, slug)) {
      return item;
    }
    changed = true;
    return {
      ...item,
      view_count: incrementViewCount(item.view_count),
    };
  });

  return changed ? { ...page, items } : page;
};

export function incrementPostViewCountInCache(queryClient: QueryClient, slug: string) {
  queryClient.setQueriesData<InfiniteContentList>({ queryKey: ["site", "posts"] }, (current) => {
    if (!current?.pages?.length) {
      return current;
    }

    let changed = false;
    const pages = current.pages.map((page) => {
      const nextPage = updateCollectionPage(page, slug);
      changed ||= nextPage !== page;
      return nextPage;
    });

    return changed ? { ...current, pages } : current;
  });

  queryClient.setQueryData<ContentDetailResponse>(
    getReadPostApiV1SitePostsSlugGetQueryKey(slug),
    (current) => {
      if (!current?.data) {
        return current;
      }
      const nextEntry = incrementEntryViewCount(current.data, slug);
      return nextEntry === current.data ? current : { ...current, data: nextEntry };
    },
  );
}
