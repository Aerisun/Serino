import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useListFriends,
  useCreateFriends,
  useUpdateFriends,
  useDeleteFriends,
  getListFriendsQueryKey,
  useCreateFriendFeedApiV1AdminSocialFriendsFriendIdFeedsPost,
} from "@serino/api-client/admin";
import { checkFriendHealth } from "@/pages/friends/api";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { DirtySaveButton, PendingSaveBadge } from "@/components/ui/DirtySaveButton";
import { AdminSectionTabs } from "@/components/ui/AdminSectionTabs";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/Dialog";
import { FileText, Plus, Trash2, Pencil, Settings2, Users, Rss } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { toast } from "sonner";
import type { FriendAdminRead } from "@serino/api-client/models";
import { FeedSourcesSection } from "./FeedSourcesSection";
import { FriendsPageContentSection } from "./FriendsPageContentSection";
import { FriendsMoreConfigSection } from "./FriendsMoreConfigSection";

const EMPTY_FRIENDS: FriendAdminRead[] = [];
const FRIEND_FORM_KEYS = ["name", "url", "avatar_url", "description"] as const;
const EMPTY_FRIEND_FORM = {
  name: "",
  url: "",
  avatar_url: "",
  description: "",
};
const EMPTY_FEED_DRAFT = { feed_url: "" };

type FriendsSection = "friends" | "page-content" | "more-config";
type FriendFormKey = (typeof FRIEND_FORM_KEYS)[number];
type FriendFormState = Record<FriendFormKey, string>;
type FriendFeedDraft = typeof EMPTY_FEED_DRAFT;

interface FriendFormFieldsProps {
  fieldLabels: Record<FriendFormKey, string>;
  form: FriendFormState;
  onFieldChange: (key: FriendFormKey, value: string) => void;
}

function FriendFormFields({
  fieldLabels,
  form,
  onFieldChange,
}: FriendFormFieldsProps) {
  return (
    <div className="mx-auto w-full max-w-xl space-y-3">
      {FRIEND_FORM_KEYS.map((key) => (
        <div key={key} className="space-y-1">
          <Label>{fieldLabels[key]}</Label>
          <Input
            value={form[key]}
            onChange={(event) => onFieldChange(key, event.target.value)}
          />
        </div>
      ))}
    </div>
  );
}

export default function FriendsPage() {
  const { t } = useI18n();
  const [page, setPage] = useState(1);
  const [section, setSection] = useState<FriendsSection>("friends");
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editingFriend, setEditingFriend] = useState<FriendAdminRead | null>(
    null,
  );
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FriendFormState>(EMPTY_FRIEND_FORM);
  const [createFeedDrafts, setCreateFeedDrafts] = useState<FriendFeedDraft[]>([
    EMPTY_FEED_DRAFT,
  ]);

  const { data: raw, isLoading } = useListFriends({ page });
  const data = raw?.data;
  const items = data?.items ?? EMPTY_FRIENDS;
  const total = data?.total ?? 0;
  const pageSize = data?.page_size ?? 20;

  const create = useCreateFriends({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListFriendsQueryKey() });
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const createFeed = useCreateFriendFeedApiV1AdminSocialFriendsFriendIdFeedsPost({
    mutation: {
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
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
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
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
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
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
    });
    setEditOpen(true);
  }

  function resetCreateDialog() {
    setForm(EMPTY_FRIEND_FORM);
    setCreateFeedDrafts([EMPTY_FEED_DRAFT]);
  }

  function addCreateFeedDraft() {
    setCreateFeedDrafts((prev) => [...prev, EMPTY_FEED_DRAFT]);
  }

  function updateFriendFormField(key: FriendFormKey, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function updateCreateFeedDraft(
    index: number,
    key: "feed_url",
    value: string,
  ) {
    setCreateFeedDrafts((prev) =>
      prev.map((draft, draftIndex) =>
        draftIndex === index ? { ...draft, [key]: value } : draft,
      ),
    );
  }

  function removeCreateFeedDraft(index: number) {
    setCreateFeedDrafts((prev) =>
      prev.length === 1 ? prev : prev.filter((_, draftIndex) => draftIndex !== index),
    );
  }

  const createDirty =
    Object.values(form).some((value) => value.trim().length > 0) ||
    createFeedDrafts.some((draft) => draft.feed_url.trim().length > 0);
  const createValid = form.name.trim().length > 0 && form.url.trim().length > 0;
  const editDirty = editingFriend
    ? form.name !== editingFriend.name ||
      form.url !== editingFriend.url ||
      form.avatar_url !== (editingFriend.avatar_url ?? "") ||
      form.description !== (editingFriend.description ?? "")
    : false;
  const editConfirmDirty = editDirty || editingFriend?.status === "archived";
  const editValid = form.name.trim().length > 0 && form.url.trim().length > 0;

  async function runImmediateCheck(friendId: string) {
    try {
      await checkFriendHealth(friendId);
    } catch (error) {
      const message = error instanceof Error ? error.message : t("common.operationFailed");
      toast.error(message);
    } finally {
      await queryClient.invalidateQueries({ queryKey: getListFriendsQueryKey() });
    }
  }

  function buildFriendPayload(status: "active" | "archived") {
    return {
      name: form.name.trim(),
      url: form.url.trim(),
      avatar_url: form.avatar_url.trim() || null,
      description: form.description.trim() || null,
      status,
    };
  }

  async function handleCreateFriend(status: "active" | "archived" = "active") {
    const created = await create.mutateAsync({ data: buildFriendPayload(status) });
    const friend = created.data;

    if (!friend) {
      throw new Error(t("common.operationFailed"));
    }

    const feedDrafts = createFeedDrafts
      .map((draft) => ({
        feed_url: draft.feed_url.trim(),
      }))
      .filter((draft) => draft.feed_url.length > 0);

    for (const draft of feedDrafts) {
      await createFeed.mutateAsync({
        friendId: friend.id,
        data: {
          friend_id: friend.id,
          feed_url: draft.feed_url,
          is_enabled: true,
        },
      });
    }

    if (status === "active") {
      await runImmediateCheck(friend.id);
    }

    setCreateOpen(false);
    resetCreateDialog();
    toast.success(t("common.operationSuccess"));
  }

  async function handleUpdateFriend(status: "active" | "archived" = "active") {
    if (!editingFriend) return;
    await update.mutateAsync({
      itemId: editingFriend.id,
      data: buildFriendPayload(status),
    });
    if (status === "active") {
      await runImmediateCheck(editingFriend.id);
    }
  }

  async function toggleFriendVisibility(friend: FriendAdminRead) {
    const nextStatus = friend.status === "archived" ? "active" : "archived";
    await update.mutateAsync({
      itemId: friend.id,
      data: {
        status: nextStatus,
      },
    });
    if (nextStatus === "active") {
      await runImmediateCheck(friend.id);
    }
  }

  const fieldLabels: Record<string, string> = {
    name: t("friends.name"),
    url: t("friends.url"),
    avatar_url: t("friends.avatarUrl"),
    description: t("friends.description2"),
  };

  return (
    <div>
      <PageHeader 
        title={t("friends.title")} 
        description={t("friends.description")}
        secondary={
          <AdminSectionTabs
            value={section}
            onValueChange={(value) => setSection(value as FriendsSection)}
            items={[
              {
                value: "friends",
                label: t("friends.tabs.friends"),
                description: t("friends.sectionDescriptions.friends"),
                icon: Users,
              },
              {
                value: "page-content",
                label: t("friends.tabs.pageContent"),
                description: t("friends.sectionDescriptions.pageContent"),
                icon: FileText,
              },
              {
                value: "more-config",
                label: t("friends.tabs.moreConfig"),
                description: t("friends.sectionDescriptions.moreConfig"),
                icon: Settings2,
              },
            ]}
          />
        }
      />

      {section === "friends" ? (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Dialog
              open={createOpen}
              onOpenChange={(v) => {
                setCreateOpen(v);
                if (!v) resetCreateDialog();
              }}
            >
              <DialogTrigger asChild>
                <Button>
                  <Plus className="h-4 w-4 mr-2" /> {t("friends.addFriend")}
                </Button>
              </DialogTrigger>
              <DialogContent
                hideCloseButton
                className="max-w-2xl max-h-[80vh] overflow-hidden"
              >
                <div className="flex max-h-[calc(80vh-3rem)] flex-col gap-4 overflow-y-auto pr-1">
                  <DialogHeader className="gap-4 sm:flex-row sm:items-start sm:justify-between sm:space-y-0">
                    <DialogTitle>{t("friends.newFriend")}</DialogTitle>
                    <div className="flex items-center gap-2 self-start">
                      {createDirty ? <PendingSaveBadge /> : null}
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={!createValid || create.isPending}
                        onClick={() => void handleCreateFriend("archived")}
                      >
                        {t("common.saveDraft")}
                      </Button>
                      <DirtySaveButton
                        dirty={createDirty}
                        saving={create.isPending}
                        idleLabel={t("common.confirm")}
                        disabled={!createValid}
                        onClick={() => void handleCreateFriend("active")}
                      />
                    </div>
                  </DialogHeader>
                  <FriendFormFields
                    fieldLabels={fieldLabels}
                    form={form}
                    onFieldChange={updateFriendFormField}
                  />
                  <div className="border-t pt-4 space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="flex items-center gap-2 text-sm font-semibold">
                        <Rss className="h-4 w-4" /> {t("friends.feedSources")}
                      </h3>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={addCreateFeedDraft}
                        type="button"
                      >
                        <Plus className="h-3 w-3 mr-1" /> {t("friends.addFeed")}
                      </Button>
                    </div>

                    <div className="space-y-3">
                      {createFeedDrafts.map((draft, index) => (
                        <div
                          key={index}
                          className="mx-auto flex w-full max-w-xl gap-2 items-end"
                        >
                          <div className="flex-1">
                            <Input
                              value={draft.feed_url}
                              onChange={(e) =>
                                updateCreateFeedDraft(index, "feed_url", e.target.value)
                              }
                              placeholder="https://example.com/feed.xml"
                            />
                          </div>
                          <Button
                            size="sm"
                            variant="ghost"
                            type="button"
                            onClick={() => removeCreateFeedDraft(index)}
                            disabled={createFeedDrafts.length === 1}
                          >
                            {t("common.delete")}
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          <Card>
            <CardContent className="p-0">
              <DataTable<FriendAdminRead>
                columns={[
                  { header: t("friends.name"), accessor: "name" },
                  {
                    header: t("friends.websiteStatus"),
                    accessor: (row) => <StatusBadge status={row.status} />,
                  },
                  {
                    header: t("friends.rssStatus"),
                    accessor: (row) => <StatusBadge status={row.rss_status} />,
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
                          variant="outline"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleFriendVisibility(row);
                          }}
                        >
                          {row.status === "archived"
                            ? t("friends.show")
                            : t("friends.archiveAction")}
                        </Button>
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
            </CardContent>
          </Card>
        </div>
      ) : section === "page-content" ? (
        <FriendsPageContentSection />
      ) : (
        <FriendsMoreConfigSection />
      )}

      {/* Edit dialog */}
      <Dialog
        open={editOpen}
        onOpenChange={(v) => {
          setEditOpen(v);
          if (!v) setEditingFriend(null);
        }}
      >
        <DialogContent
          hideCloseButton
          className="max-w-2xl max-h-[80vh] overflow-hidden"
        >
          <div className="flex max-h-[calc(80vh-3rem)] flex-col gap-4 overflow-y-auto pr-1">
            <DialogHeader className="gap-4 sm:flex-row sm:items-start sm:justify-between sm:space-y-0">
              <DialogTitle>{t("friends.editFriend")}</DialogTitle>
              <div className="flex items-center gap-2 self-start">
                {editDirty ? <PendingSaveBadge /> : null}
                <DirtySaveButton
                  dirty={editConfirmDirty}
                  saving={update.isPending}
                  idleLabel={t("common.confirm")}
                  disabled={!editValid}
                  onClick={() => void handleUpdateFriend("active")}
                />
              </div>
            </DialogHeader>
            <FriendFormFields
              fieldLabels={fieldLabels}
              form={form}
              onFieldChange={updateFriendFormField}
            />

            {editingFriend && <FeedSourcesSection friendId={editingFriend.id} />}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
