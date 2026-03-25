import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useListFriends,
  useCreateFriends,
  useUpdateFriends,
  useDeleteFriends,
  getListFriendsQueryKey,
  useListFriendFeedsApiV1AdminSocialFriendsFriendIdFeedsGet,
  useCreateFriendFeedApiV1AdminSocialFriendsFriendIdFeedsPost,
  useUpdateFriendFeedApiV1AdminSocialFeedsFeedIdPut,
  useDeleteFriendFeedApiV1AdminSocialFeedsFeedIdDelete,
  getListFriendFeedsApiV1AdminSocialFriendsFriendIdFeedsGetQueryKey,
} from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/Dialog";
import { Plus, Trash2, Pencil, Rss } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import type { FriendAdminRead, FriendFeedSourceAdminRead } from "@serino/api-client/models";

const EMPTY_FRIENDS: FriendAdminRead[] = [];

export default function FriendsPage() {
  const { t } = useI18n();
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editingFriend, setEditingFriend] = useState<FriendAdminRead | null>(null);
  const queryClient = useQueryClient();
  const emptyForm = {
    name: "",
    url: "",
    avatar_url: "",
    description: "",
    status: "active",
    order_index: 0,
  };
  const [form, setForm] = useState(emptyForm);

  const { data: raw, isLoading } = useListFriends({ page });
  const data = raw?.data;
  const items = data?.items ?? EMPTY_FRIENDS;
  const total = data?.total ?? 0;
  const pageSize = data?.page_size ?? 20;

  const create = useCreateFriends({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListFriendsQueryKey() });
        setCreateOpen(false);
        setForm(emptyForm);
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        const msg = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  const update = useUpdateFriends({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListFriendsQueryKey() });
        setEditOpen(false);
        setEditingFriend(null);
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        const msg = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  const del = useDeleteFriends({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListFriendsQueryKey() });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        const msg = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  function startEdit(friend: FriendAdminRead) {
    setEditingFriend(friend);
    setForm({
      name: friend.name,
      url: friend.url,
      avatar_url: friend.avatar_url ?? "",
      description: friend.description ?? "",
      status: friend.status,
      order_index: friend.order_index,
    });
    setEditOpen(true);
  }

  const fieldLabels: Record<string, string> = {
    name: t("friends.name"),
    url: t("friends.url"),
    avatar_url: t("friends.avatarUrl"),
    description: t("friends.description2"),
  };

  function FriendFormFields() {
    return (
      <div className="space-y-3">
        {(["name", "url", "avatar_url", "description"] as const).map((k) => (
          <div key={k} className="space-y-1">
            <Label>{fieldLabels[k]}</Label>
            <Input
              value={(form as any)[k]}
              onChange={(e) => setForm((p) => ({ ...p, [k]: e.target.value }))}
            />
          </div>
        ))}
        <div className="space-y-1">
          <Label>{t("common.status")}</Label>
          <select
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={form.status}
            onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}
          >
            <option value="active">{t("friends.active")}</option>
            <option value="archived">{t("friends.archived")}</option>
          </select>
        </div>
        <div className="space-y-1">
          <Label>{t("common.order")}</Label>
          <Input
            type="number"
            value={form.order_index}
            onChange={(e) =>
              setForm((p) => ({
                ...p,
                order_index: parseInt(e.target.value) || 0,
              }))
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title={t("friends.title")}
        description={t("friends.description")}
        actions={
          <Dialog
            open={createOpen}
            onOpenChange={(v) => {
              setCreateOpen(v);
              if (!v) setForm(emptyForm);
            }}
          >
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" /> {t("friends.addFriend")}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t("friends.newFriend")}</DialogTitle>
              </DialogHeader>
              <FriendFormFields />
              <Button
                onClick={() => create.mutate({ data: form })}
                disabled={create.isPending}
              >
                {t("common.create")}
              </Button>
            </DialogContent>
          </Dialog>
        }
      />

      {/* Edit dialog */}
      <Dialog
        open={editOpen}
        onOpenChange={(v) => {
          setEditOpen(v);
          if (!v) setEditingFriend(null);
        }}
      >
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t("friends.editFriend")}</DialogTitle>
          </DialogHeader>
          <FriendFormFields />
          <Button onClick={() => update.mutate({ itemId: editingFriend!.id, data: form })} disabled={update.isPending}>
            {t("common.save")}
          </Button>

          {editingFriend && <FeedSourcesSection friendId={editingFriend.id} />}
        </DialogContent>
      </Dialog>

      <div className="border rounded-lg">
        <DataTable<FriendAdminRead>
          columns={[
            { header: t("friends.name"), accessor: "name" },
            {
              header: t("common.status"),
              accessor: (row) => <StatusBadge status={row.status} />,
            },
            {
              header: t("siteConfig.updated"),
              accessor: (row) => formatDate(row.updated_at),
            },
            {
              header: "",
              accessor: (row) => (
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation();
                      startEdit(row);
                    }}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation();
                      del.mutate({ itemId: row.id });
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ),
            },
          ]}
          data={items}
          total={total}
          page={page}
          pageSize={pageSize}
          onPageChange={setPage}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}

function FeedSourcesSection({ friendId }: { friendId: string }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: feedsRaw, isLoading } = useListFriendFeedsApiV1AdminSocialFriendsFriendIdFeedsGet(friendId);
  const feeds = feedsRaw?.data;
  const [addOpen, setAddOpen] = useState(false);
  const [feedForm, setFeedForm] = useState({ feed_url: "", is_enabled: true });
  const [editingFeedId, setEditingFeedId] = useState<string | null>(null);

  const createFeed = useCreateFriendFeedApiV1AdminSocialFriendsFriendIdFeedsPost({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListFriendFeedsApiV1AdminSocialFriendsFriendIdFeedsGetQueryKey(friendId) });
        setAddOpen(false);
        setFeedForm({ feed_url: "", is_enabled: true });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        const msg = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  const updateFeed = useUpdateFriendFeedApiV1AdminSocialFeedsFeedIdPut({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListFriendFeedsApiV1AdminSocialFriendsFriendIdFeedsGetQueryKey(friendId) });
        setEditingFeedId(null);
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        const msg = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  const delFeed = useDeleteFriendFeedApiV1AdminSocialFeedsFeedIdDelete({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListFriendFeedsApiV1AdminSocialFriendsFriendIdFeedsGetQueryKey(friendId) });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        const msg = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  function startEditFeed(feed: FriendFeedSourceAdminRead) {
    setEditingFeedId(feed.id);
    setFeedForm({ feed_url: feed.feed_url, is_enabled: feed.is_enabled });
  }

  return (
    <div className="border-t pt-4 mt-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <Rss className="h-4 w-4" /> {t("friends.feedSources")}
        </h3>
        <Button
          size="sm"
          variant="outline"
          onClick={() => setAddOpen(!addOpen)}
        >
          <Plus className="h-3 w-3 mr-1" /> {t("friends.addFeed")}
        </Button>
      </div>

      {addOpen && (
        <div className="flex gap-2 mb-3 items-end">
          <div className="flex-1 space-y-1">
            <Label className="text-xs">{t("friends.feedUrl")}</Label>
            <Input
              value={feedForm.feed_url}
              onChange={(e) =>
                setFeedForm((p) => ({ ...p, feed_url: e.target.value }))
              }
              placeholder="https://example.com/feed.xml"
            />
          </div>
          <label className="flex items-center gap-1 text-sm pb-2">
            <input
              type="checkbox"
              checked={feedForm.is_enabled}
              onChange={(e) =>
                setFeedForm((p) => ({ ...p, is_enabled: e.target.checked }))
              }
            />
            {t("siteConfig.enabled")}
          </label>
          <Button
            size="sm"
            onClick={() => createFeed.mutate({
              friendId,
              data: {
                friend_id: friendId,
                feed_url: feedForm.feed_url,
                is_enabled: feedForm.is_enabled,
              },
            })}
            disabled={createFeed.isPending}
          >
            {t("common.add")}
          </Button>
        </div>
      )}

      {isLoading && (
        <p className="text-sm text-muted-foreground">
          {t("friends.loadingFeeds")}
        </p>
      )}
      {feeds && feeds.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("friends.noFeeds")}</p>
      )}
      {feeds?.map((feed) => (
        <div
          key={feed.id}
          className="flex items-center gap-2 py-2 border-b last:border-0"
        >
          {editingFeedId === feed.id ? (
            <>
              <Input
                className="flex-1"
                value={feedForm.feed_url}
                onChange={(e) =>
                  setFeedForm((p) => ({ ...p, feed_url: e.target.value }))
                }
              />
              <label className="flex items-center gap-1 text-sm">
                <input
                  type="checkbox"
                  checked={feedForm.is_enabled}
                  onChange={(e) =>
                    setFeedForm((p) => ({ ...p, is_enabled: e.target.checked }))
                  }
                />
                {t("siteConfig.enabled")}
              </label>
              <Button
                size="sm"
                onClick={() => updateFeed.mutate({
                  feedId: editingFeedId!,
                  data: {
                    feed_url: feedForm.feed_url,
                    is_enabled: feedForm.is_enabled,
                  },
                })}
                disabled={updateFeed.isPending}
              >
                {t("common.save")}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setEditingFeedId(null)}
              >
                {t("common.cancel")}
              </Button>
            </>
          ) : (
            <>
              <span className="flex-1 text-sm truncate">{feed.feed_url}</span>
              <StatusBadge status={feed.is_enabled ? "active" : "inactive"} />
              <Button
                variant="ghost"
                size="icon"
                onClick={() => startEditFeed(feed)}
              >
                <Pencil className="h-3 w-3" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => delFeed.mutate({ feedId: feed.id })}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </>
          )}
        </div>
      ))}
    </div>
  );
}
