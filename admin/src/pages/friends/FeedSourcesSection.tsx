import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  getListFriendFeedsApiV1AdminSocialFriendsFriendIdFeedsGetQueryKey,
  useCreateFriendFeedApiV1AdminSocialFriendsFriendIdFeedsPost,
  useDeleteFriendFeedApiV1AdminSocialFeedsFeedIdDelete,
  useListFriendFeedsApiV1AdminSocialFriendsFriendIdFeedsGet,
  useUpdateFriendFeedApiV1AdminSocialFeedsFeedIdPut,
} from "@serino/api-client/admin";
import type { FriendFeedSourceAdminRead } from "@serino/api-client/models";
import { Plus, Pencil, Rss, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";

export function FeedSourcesSection({ friendId }: { friendId: string }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: feedsRaw, isLoading } = useListFriendFeedsApiV1AdminSocialFriendsFriendIdFeedsGet(friendId);
  const feeds = feedsRaw?.data;
  const [addOpen, setAddOpen] = useState(false);
  const [feedForm, setFeedForm] = useState({ feed_url: "" });
  const [editingFeedId, setEditingFeedId] = useState<string | null>(null);

  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: getListFriendFeedsApiV1AdminSocialFriendsFriendIdFeedsGetQueryKey(friendId),
    });

  const createFeed = useCreateFriendFeedApiV1AdminSocialFriendsFriendIdFeedsPost({
    mutation: {
      onSuccess: () => {
        void invalidate();
        setAddOpen(false);
        setFeedForm({ feed_url: "" });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const updateFeed = useUpdateFriendFeedApiV1AdminSocialFeedsFeedIdPut({
    mutation: {
      onSuccess: () => {
        void invalidate();
        setEditingFeedId(null);
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const delFeed = useDeleteFriendFeedApiV1AdminSocialFeedsFeedIdDelete({
    mutation: {
      onSuccess: () => {
        void invalidate();
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  function startEditFeed(feed: FriendFeedSourceAdminRead) {
    setEditingFeedId(feed.id);
    setFeedForm({ feed_url: feed.feed_url });
  }

  return (
    <div className="border-t pt-4 mt-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <Rss className="h-4 w-4" /> {t("friends.feedSources")}
        </h3>
        <Button size="sm" variant="outline" onClick={() => setAddOpen(!addOpen)}>
          <Plus className="h-3 w-3 mr-1" /> {t("friends.addFeed")}
        </Button>
      </div>

      {addOpen ? (
        <div className="flex gap-2 mb-3 items-end">
          <div className="flex-1">
            <Input
              value={feedForm.feed_url}
              onChange={(e) => setFeedForm((p) => ({ ...p, feed_url: e.target.value }))}
              placeholder="https://example.com/feed.xml"
            />
          </div>
          <Button
            size="sm"
            onClick={() =>
              createFeed.mutate({
                friendId,
                data: {
                  friend_id: friendId,
                  feed_url: feedForm.feed_url.trim(),
                  is_enabled: true,
                },
              })
            }
            disabled={createFeed.isPending}
          >
            {t("common.add")}
          </Button>
        </div>
      ) : null}

      {isLoading ? <p className="text-sm text-muted-foreground">{t("friends.loadingFeeds")}</p> : null}
      {feeds && feeds.length === 0 ? <p className="text-sm text-muted-foreground">{t("friends.noFeeds")}</p> : null}
      {feeds?.map((feed) => (
        <div key={feed.id} className="flex items-center gap-2 py-2 border-b last:border-0">
          {editingFeedId === feed.id ? (
            <>
              <Input
                className="flex-1"
                value={feedForm.feed_url}
                onChange={(e) => setFeedForm((p) => ({ ...p, feed_url: e.target.value }))}
              />
              <Button
                size="sm"
                onClick={() =>
                  updateFeed.mutate({
                    feedId: editingFeedId,
                    data: {
                      feed_url: feedForm.feed_url.trim(),
                      is_enabled: true,
                    },
                  })
                }
                disabled={updateFeed.isPending}
              >
                {t("common.save")}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditingFeedId(null)}>
                {t("common.cancel")}
              </Button>
            </>
          ) : (
            <>
              <span className="flex-1 text-sm truncate">{feed.feed_url}</span>
              <StatusBadge status={feed.rss_status} />
              <Button variant="ghost" size="icon" onClick={() => startEditFeed(feed)}>
                <Pencil className="h-3 w-3" />
              </Button>
              <Button variant="ghost" size="icon" onClick={() => delFeed.mutate({ feedId: feed.id })}>
                <Trash2 className="h-3 w-3" />
              </Button>
            </>
          )}
        </div>
      ))}
    </div>
  );
}
