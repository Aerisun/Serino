import client from "../client";
import type { Comment, GuestbookEntry, ModerateAction, PaginatedResponse } from "@/types/models";

export async function listComments(params?: { page?: number; page_size?: number; status?: string }): Promise<PaginatedResponse<Comment>> {
  const res = await client.get("/moderation/comments", { params });
  return res.data;
}

export async function moderateComment(commentId: string, data: ModerateAction): Promise<Comment> {
  const res = await client.post(`/moderation/comments/${commentId}/moderate`, data);
  return res.data;
}

export async function listGuestbook(params?: { page?: number; page_size?: number; status?: string }): Promise<PaginatedResponse<GuestbookEntry>> {
  const res = await client.get("/moderation/guestbook", { params });
  return res.data;
}

export async function moderateGuestbook(entryId: string, data: ModerateAction): Promise<GuestbookEntry> {
  const res = await client.post(`/moderation/guestbook/${entryId}/moderate`, data);
  return res.data;
}
