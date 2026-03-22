import { apiClient } from "@/lib/api";

export interface PublicFriend {
  name: string;
  description: string | null;
  avatar: string | null;
  url: string;
  status: string;
  order_index: number;
}

export interface PublicFriendCollection {
  items: PublicFriend[];
}

export interface PublicFriendFeedItem {
  title: string;
  summary: string | null;
  url: string;
  blogName: string;
  avatar: string | null;
  publishedAt: string | null;
}

export interface PublicFriendFeedCollection {
  items: PublicFriendFeedItem[];
}

export const formatFriendFeedDate = (value: string | null | undefined) => {
  if (!value) return "";

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }

  const year = parsed.getFullYear();
  const month = String(parsed.getMonth() + 1).padStart(2, "0");
  const day = String(parsed.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

export interface PublicGuestbookEntry {
  id: string;
  name: string;
  website: string | null;
  body: string;
  status: string;
  created_at: string;
  avatar?: string | null;
  avatar_url?: string | null;
}

export interface PublicGuestbookCollection {
  items: PublicGuestbookEntry[];
}

export interface PublicGuestbookCreatePayload {
  name: string;
  email?: string;
  website?: string;
  body: string;
}

export interface PublicGuestbookCreateResponse {
  item: PublicGuestbookEntry;
  accepted: boolean;
}

export interface PublicComment {
  id: string;
  parent_id: string | null;
  author_name: string;
  body: string;
  status: string;
  created_at: string;
  replies: PublicComment[];
  avatar?: string | null;
  avatar_url?: string | null;
  like_count?: number;
  liked?: boolean;
  is_author?: boolean;
}

export interface PublicCommentCollection {
  items: PublicComment[];
}

export interface PublicCommentCreatePayload {
  author_name: string;
  author_email?: string;
  body: string;
  parent_id?: string | null;
}

export interface PublicCommentCreateResponse {
  item: PublicComment;
  accepted: boolean;
}

export interface PublicReactionCreatePayload {
  content_type: string;
  content_slug: string;
  reaction_type: string;
  client_token?: string;
}

export interface PublicReactionRead {
  content_type: string;
  content_slug: string;
  reaction_type: string;
  total: number;
}

export interface PublicCalendarEvent {
  date: string;
  type: "post" | "diary" | "excerpt";
  title: string;
  slug: string;
  href: string;
}

export interface PublicCalendarRead {
  range_start: string;
  range_end: string;
  events: PublicCalendarEvent[];
}

export interface PublicRecentActivityItem {
  kind: "comment" | "reply" | "like" | "guestbook";
  actor_name: string | null;
  actor_avatar: string | null;
  target_title: string | null;
  excerpt: string | null;
  created_at: string;
  href: string | null;
}

export interface PublicRecentActivityRead {
  items: PublicRecentActivityItem[];
}

export interface PublicActivityHeatmapStats {
  total_contributions: number;
  peak_week: number;
  average_per_week: number;
}

export interface PublicActivityHeatmapWeek {
  week_start: string;
  total: number;
  days: number[];
  month_label: string;
  label: string;
}

export interface PublicActivityHeatmapRead {
  stats: PublicActivityHeatmapStats;
  weeks: PublicActivityHeatmapWeek[];
}

export async function fetchPublicFriends(limit?: number, init?: RequestInit) {
  const path = new URL("/api/v1/public/friends", "http://localhost");
  if (limit) path.searchParams.set("limit", String(limit));
  return apiClient.get<PublicFriendCollection>(`${path.pathname}${path.search}`, init);
}

export async function fetchPublicFriendFeed(limit?: number, init?: RequestInit) {
  const path = new URL("/api/v1/public/friend-feed", "http://localhost");
  if (limit) path.searchParams.set("limit", String(limit));
  return apiClient.get<PublicFriendFeedCollection>(`${path.pathname}${path.search}`, init);
}

export async function fetchPublicGuestbook(limit?: number, init?: RequestInit) {
  const path = new URL("/api/v1/public/guestbook", "http://localhost");
  if (limit) path.searchParams.set("limit", String(limit));
  return apiClient.get<PublicGuestbookCollection>(`${path.pathname}${path.search}`, init);
}

export async function createPublicGuestbookEntry(payload: PublicGuestbookCreatePayload, init?: RequestInit) {
  return apiClient.post<PublicGuestbookCreateResponse>("/api/v1/public/guestbook", payload, init);
}

export async function fetchPublicComments(contentType: string, contentSlug: string, init?: RequestInit) {
  return apiClient.get<PublicCommentCollection>(
    `/api/v1/public/comments/${encodeURIComponent(contentType)}/${encodeURIComponent(contentSlug)}`,
    init,
  );
}

export async function createPublicComment(
  contentType: string,
  contentSlug: string,
  payload: PublicCommentCreatePayload,
  init?: RequestInit,
) {
  return apiClient.post<PublicCommentCreateResponse>(
    `/api/v1/public/comments/${encodeURIComponent(contentType)}/${encodeURIComponent(contentSlug)}`,
    payload,
    init,
  );
}

export async function createPublicReaction(payload: PublicReactionCreatePayload, init?: RequestInit) {
  return apiClient.post<PublicReactionRead>("/api/v1/public/reactions", payload, init);
}

export async function fetchPublicReaction(
  contentType: string,
  contentSlug: string,
  reactionType: string,
  init?: RequestInit,
) {
  return apiClient.get<PublicReactionRead>(
    `/api/v1/public/reactions/${encodeURIComponent(contentType)}/${encodeURIComponent(contentSlug)}/${encodeURIComponent(reactionType)}`,
    init,
  );
}

export async function fetchPublicCalendar(from?: string, to?: string, init?: RequestInit) {
  const path = new URL("/api/v1/public/calendar", "http://localhost");
  if (from) path.searchParams.set("from", from);
  if (to) path.searchParams.set("to", to);
  return apiClient.get<PublicCalendarRead>(`${path.pathname}${path.search}`, init);
}

export async function fetchRecentActivity(limit?: number, init?: RequestInit) {
  const path = new URL("/api/v1/public/recent-activity", "http://localhost");
  if (limit) path.searchParams.set("limit", String(limit));
  return apiClient.get<PublicRecentActivityRead>(`${path.pathname}${path.search}`, init);
}

export async function fetchActivityHeatmap(weeks?: number, init?: RequestInit) {
  const path = new URL("/api/v1/public/activity-heatmap", "http://localhost");
  if (weeks) path.searchParams.set("weeks", String(weeks));
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (tz) path.searchParams.set("tz", tz);
  } catch { /* ignore */ }
  return apiClient.get<PublicActivityHeatmapRead>(`${path.pathname}${path.search}`, init);
}
