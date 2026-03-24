import client from "../client";
import type { Friend, FriendCreate, FriendUpdate, FriendFeedSource, FriendFeedSourceCreate, FriendFeedSourceUpdate, PaginatedResponse } from "@/types/models";

export async function listFriends(params?: { page?: number; page_size?: number }): Promise<PaginatedResponse<Friend>> {
  const res = await client.get("/api/v1/admin/social/friends/", { params });
  return res.data;
}

export async function getFriend(id: string): Promise<Friend> {
  const res = await client.get(`/api/v1/admin/social/friends/${id}`);
  return res.data;
}

export async function createFriend(data: FriendCreate): Promise<Friend> {
  const res = await client.post("/api/v1/admin/social/friends/", data);
  return res.data;
}

export async function updateFriend(id: string, data: FriendUpdate): Promise<Friend> {
  const res = await client.put(`/api/v1/admin/social/friends/${id}`, data);
  return res.data;
}

export async function deleteFriend(id: string): Promise<void> {
  await client.delete(`/api/v1/admin/social/friends/${id}`);
}

// --- Feed Sources ---
export async function listFriendFeeds(friendId: string): Promise<FriendFeedSource[]> {
  const res = await client.get(`/api/v1/admin/social/friends/${friendId}/feeds`);
  return res.data;
}

export async function createFriendFeed(friendId: string, data: FriendFeedSourceCreate): Promise<FriendFeedSource> {
  const res = await client.post(`/api/v1/admin/social/friends/${friendId}/feeds`, data);
  return res.data;
}

export async function updateFriendFeed(feedId: string, data: FriendFeedSourceUpdate): Promise<FriendFeedSource> {
  const res = await client.put(`/api/v1/admin/social/feeds/${feedId}`, data);
  return res.data;
}

export async function deleteFriendFeed(feedId: string): Promise<void> {
  await client.delete(`/api/v1/admin/social/feeds/${feedId}`);
}
