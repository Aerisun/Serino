import { apiClient } from "@/lib/api";

export interface PublicFriend {
  name: string;
  description?: string | null;
  avatar?: string | null;
  url: string;
  status: string;
  order_index: number;
}

export interface PublicFriendCollection {
  items: PublicFriend[];
}

export interface PublicFriendFeedItem {
  title: string;
  summary?: string | null;
  url: string;
  blogName: string;
  avatar?: string | null;
  publishedAt?: string | null;
}

export interface PublicFriendFeedCollection {
  items: PublicFriendFeedItem[];
}

export const formatFriendFeedDate = (value: string | null | undefined) => {
  if (!value) {
    return "";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
  }).format(parsed);
};

export async function fetchPublicFriends(limit?: number, init?: RequestInit) {
  const path = new URL("/api/v1/public/friends", "http://localhost");
  if (limit) {
    path.searchParams.set("limit", String(limit));
  }
  return apiClient.get<PublicFriendCollection>(`${path.pathname}${path.search}`, init);
}

export async function fetchPublicFriendFeed(limit?: number, init?: RequestInit) {
  const path = new URL("/api/v1/public/friend-feed", "http://localhost");
  if (limit) {
    path.searchParams.set("limit", String(limit));
  }
  return apiClient.get<PublicFriendFeedCollection>(`${path.pathname}${path.search}`, init);
}
