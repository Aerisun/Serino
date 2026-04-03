import {
  getListDiaryQueryKey,
  getListDiaryQueryOptions,
  getListExcerptsQueryKey,
  getListExcerptsQueryOptions,
  getListPostsQueryKey,
  getListPostsQueryOptions,
  getListThoughtsQueryKey,
  getListThoughtsQueryOptions,
} from "@serino/api-client/admin";
import type { ContentCategoryType } from "@/lib/contentCategories";

export const CONTENT_LIST_PARAMS = { page: 1, page_size: 100 } as const;

export function getContentListQueryKey(contentType: ContentCategoryType) {
  switch (contentType) {
    case "posts":
      return getListPostsQueryKey(CONTENT_LIST_PARAMS);
    case "diary":
      return getListDiaryQueryKey(CONTENT_LIST_PARAMS);
    case "thoughts":
      return getListThoughtsQueryKey(CONTENT_LIST_PARAMS);
    case "excerpts":
      return getListExcerptsQueryKey(CONTENT_LIST_PARAMS);
  }
}

export function getContentListQueryOptions(contentType: ContentCategoryType) {
  const query = { staleTime: 60_000, refetchOnWindowFocus: false };
  switch (contentType) {
    case "posts":
      return getListPostsQueryOptions(CONTENT_LIST_PARAMS, { query });
    case "diary":
      return getListDiaryQueryOptions(CONTENT_LIST_PARAMS, { query });
    case "thoughts":
      return getListThoughtsQueryOptions(CONTENT_LIST_PARAMS, { query });
    case "excerpts":
      return getListExcerptsQueryOptions(CONTENT_LIST_PARAMS, { query });
  }
}
