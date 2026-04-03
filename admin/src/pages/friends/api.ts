import { checkFriendHealthApiV1AdminSocialFriendsFriendIdCheckPost } from "@serino/api-client/admin";

export function checkFriendHealth(friendId: string) {
  return checkFriendHealthApiV1AdminSocialFriendsFriendIdCheckPost(friendId).then((response) => response.data as {
    friend_id: string;
    website_status: string;
    rss_status: string;
  });
}
