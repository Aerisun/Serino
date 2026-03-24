import client from "../client";
import type { Comment, GuestbookEntry, ModerateAction, PaginatedResponse } from "@/types/models";

export interface ModerationListParams {
  page?: number;
  page_size?: number;
  status?: string;
  path?: string;
  surface?: string;
  keyword?: string;
  author?: string;
  email?: string;
  sort?: string;
}

export async function listComments(params?: ModerationListParams): Promise<PaginatedResponse<Comment>> {
  const res = await client.get("/api/v1/admin/moderation/comments", { params });
  return res.data;
}

export async function moderateComment(commentId: string, data: ModerateAction): Promise<Comment> {
  const res = await client.post(`/api/v1/admin/moderation/comments/${commentId}/moderate`, data);
  return res.data;
}

export async function listGuestbook(params?: ModerationListParams): Promise<PaginatedResponse<GuestbookEntry>> {
  const res = await client.get("/api/v1/admin/moderation/guestbook", { params });
  return res.data;
}

export async function moderateGuestbook(entryId: string, data: ModerateAction): Promise<GuestbookEntry> {
  const res = await client.post(`/api/v1/admin/moderation/guestbook/${entryId}/moderate`, data);
  return res.data;
}
