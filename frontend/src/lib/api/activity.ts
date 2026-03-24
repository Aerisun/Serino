import { apiClient } from "@/lib/api";

export interface PublicCalendarEvent {
  date: string;
  type: string;
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
  kind: string;
  actor_name: string;
  actor_avatar: string;
  target_title: string;
  excerpt?: string | null;
  created_at: string;
  href: string;
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

export async function fetchPublicCalendar(rangeStart: string, rangeEnd: string, init?: RequestInit) {
  const path = new URL("/api/v1/public/calendar", "http://localhost");
  path.searchParams.set("from", rangeStart);
  path.searchParams.set("to", rangeEnd);
  return apiClient.get<PublicCalendarRead>(`${path.pathname}${path.search}`, init);
}

export async function fetchRecentActivity(limit?: number, init?: RequestInit) {
  const path = new URL("/api/v1/public/recent-activity", "http://localhost");
  if (limit) {
    path.searchParams.set("limit", String(limit));
  }
  return apiClient.get<PublicRecentActivityRead>(`${path.pathname}${path.search}`, init);
}

export async function fetchActivityHeatmap(weeks?: number, init?: RequestInit) {
  const path = new URL("/api/v1/public/activity-heatmap", "http://localhost");
  if (weeks) {
    path.searchParams.set("weeks", String(weeks));
  }
  return apiClient.get<PublicActivityHeatmapRead>(`${path.pathname}${path.search}`, init);
}
