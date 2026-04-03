import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useListDiary,
  useListExcerpts,
  useListPosts,
  useListThoughts,
  useUpdateDiary,
  useUpdateExcerpts,
  useUpdatePosts,
  useUpdateThoughts,
} from "@serino/api-client/admin";
import type { ContentCategoryRead, ContentRead } from "@serino/api-client/models";
import { FolderMinus, FolderPlus, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { useI18n } from "@/i18n";
import type { ContentCategoryType } from "@/lib/contentCategories";
import { CONTENT_LIST_PARAMS, getContentListQueryKey } from "./contentCategoryQueries";

export function CategoryDialog({
  open,
  title,
  description,
  value,
  onValueChange,
  onSubmit,
  onOpenChange,
  pending,
}: {
  open: boolean;
  title: string;
  description: string;
  value: string;
  onValueChange: (value: string) => void;
  onSubmit: () => void;
  onOpenChange: (open: boolean) => void;
  pending: boolean;
}) {
  const { t } = useI18n();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md rounded-2xl">
        <DialogHeader className="text-left">
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>{t("contentCategories.nameLabel")}</Label>
            <Input
              value={value}
              onChange={(event) => onValueChange(event.target.value)}
              placeholder={t("contentCategories.namePlaceholder")}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  onSubmit();
                }
              }}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" type="button" onClick={() => onOpenChange(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="button" onClick={onSubmit} disabled={pending}>
              {pending ? t("common.saving") : t("common.confirm")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

interface EditCategoryDialogProps {
  open: boolean;
  category: ContentCategoryRead | null;
  contentType: ContentCategoryType;
  onOpenChange: (open: boolean) => void;
  onNameChange: (name: string) => void;
  onSave: () => void;
  categoryName: string;
  pending: boolean;
}

export function EditCategoryDialog({
  open,
  category,
  contentType,
  onOpenChange,
  onNameChange,
  onSave,
  categoryName,
  pending,
}: EditCategoryDialogProps) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [showAddModal, setShowAddModal] = useState(false);
  const [optimisticCategoryByItemId, setOptimisticCategoryByItemId] = useState<Record<string, string | null>>({});
  const [movingItemIds, setMovingItemIds] = useState<Set<string>>(new Set());

  const postsResult = useListPosts(CONTENT_LIST_PARAMS, {
    query: { enabled: open && contentType === "posts" && !!category, staleTime: 60_000, refetchOnWindowFocus: false },
  });
  const diaryResult = useListDiary(CONTENT_LIST_PARAMS, {
    query: { enabled: open && contentType === "diary" && !!category, staleTime: 60_000, refetchOnWindowFocus: false },
  });
  const thoughtsResult = useListThoughts(CONTENT_LIST_PARAMS, {
    query: { enabled: open && contentType === "thoughts" && !!category, staleTime: 60_000, refetchOnWindowFocus: false },
  });
  const excerptsResult = useListExcerpts(CONTENT_LIST_PARAMS, {
    query: { enabled: open && contentType === "excerpts" && !!category, staleTime: 60_000, refetchOnWindowFocus: false },
  });

  const contentResult = useMemo(() => {
    switch (contentType) {
      case "posts":
        return postsResult;
      case "diary":
        return diaryResult;
      case "thoughts":
        return thoughtsResult;
      case "excerpts":
        return excerptsResult;
    }
  }, [contentType, diaryResult, excerptsResult, postsResult, thoughtsResult]);

  const isLoadingContent = contentResult.isLoading;
  const allContent = contentResult.data;
  const allItems = useMemo(() => ((allContent?.data?.items as ContentRead[] | undefined) ?? []), [allContent]);

  const listItems = useMemo(() => {
    if (Object.keys(optimisticCategoryByItemId).length === 0) {
      return allItems;
    }
    return allItems.map((item: any) => {
      if (!(item.id in optimisticCategoryByItemId)) {
        return item;
      }
      return { ...item, category: optimisticCategoryByItemId[item.id] };
    });
  }, [allItems, optimisticCategoryByItemId]);

  const currentCategoryName = category?.name ?? "";
  const managedItems = useMemo(() => listItems.filter((item: any) => item.category === currentCategoryName), [currentCategoryName, listItems]);
  const unclassifiedItems = useMemo(() => listItems.filter((item: any) => !item.category), [listItems]);

  useEffect(() => {
    if (!open) {
      setShowAddModal(false);
      setOptimisticCategoryByItemId({});
      setMovingItemIds(new Set());
    }
  }, [open]);

  useEffect(() => {
    setOptimisticCategoryByItemId({});
    setMovingItemIds(new Set());
  }, [category?.id, contentType]);

  const postsUpdate = useUpdatePosts();
  const diaryUpdate = useUpdateDiary();
  const thoughtsUpdate = useUpdateThoughts();
  const excerptsUpdate = useUpdateExcerpts();

  const updateMutation = useMemo(() => {
    switch (contentType) {
      case "posts":
        return postsUpdate;
      case "diary":
        return diaryUpdate;
      case "thoughts":
        return thoughtsUpdate;
      case "excerpts":
        return excerptsUpdate;
    }
  }, [contentType, diaryUpdate, excerptsUpdate, postsUpdate, thoughtsUpdate]);

  const listQueryKey = useMemo(() => getContentListQueryKey(contentType), [contentType]);

  const markItemMoving = (itemId: string, moving: boolean) => {
    setMovingItemIds((prev) => {
      const next = new Set(prev);
      if (moving) next.add(itemId);
      else next.delete(itemId);
      return next;
    });
  };

  const patchListCacheCategory = (itemId: string, nextCategory: string | null) => {
    queryClient.setQueryData(listQueryKey, (cached: any) => {
      if (!cached?.data?.items || !Array.isArray(cached.data.items)) {
        return cached;
      }
      return {
        ...cached,
        data: {
          ...cached.data,
          items: cached.data.items.map((entry: ContentRead) =>
            entry.id === itemId ? { ...entry, category: nextCategory } : entry
          ),
        },
      };
    });
  };

  const applyCategoryChange = async (item: ContentRead, nextCategory: string | null) => {
    if (!category) return;

    const previousCategory = item.category ?? null;
    if (previousCategory === nextCategory) return;

    markItemMoving(item.id, true);
    setOptimisticCategoryByItemId((prev) => ({ ...prev, [item.id]: nextCategory }));

    try {
      await updateMutation.mutateAsync({
        itemId: item.id,
        data: { category: nextCategory },
      });
      patchListCacheCategory(item.id, nextCategory);
      setOptimisticCategoryByItemId((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
      toast.success(t("common.operationSuccess"));
    } catch {
      setOptimisticCategoryByItemId((prev) => ({ ...prev, [item.id]: previousCategory }));
      toast.error(t("common.operationFailed"));
    } finally {
      markItemMoving(item.id, false);
    }
  };

  const isItemMoving = (itemId: string) => movingItemIds.has(itemId);

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-2xl rounded-2xl">
          <DialogHeader className="text-left">
            <DialogTitle>{t("contentCategories.editTitle")}</DialogTitle>
            <DialogDescription>{category?.name}</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{t("contentCategories.nameLabel")}</Label>
              <Input
                value={categoryName}
                onChange={(event) => onNameChange(event.target.value)}
                placeholder={t("contentCategories.namePlaceholder")}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    onSave();
                  }
                }}
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>{t("contentCategories.managedItems")}</Label>
                <span className="text-xs text-muted-foreground">{managedItems.length}</span>
              </div>
              {isLoadingContent ? (
                <div className="rounded-lg border border-dashed border-border/60 px-4 py-8 text-center text-sm text-muted-foreground">
                  {t("contentCategories.loadingItems")}
                </div>
              ) : managedItems.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border/60 px-4 py-8 text-center text-sm text-muted-foreground">
                  {t("contentCategories.noManagedItems")}
                </div>
              ) : (
                <div className="max-h-48 overflow-y-auto rounded-lg border border-border/50 bg-background/50">
                  <div className="p-3 space-y-2">
                    {managedItems.map((item: any) => (
                      <div key={item.id} className="flex items-center justify-between rounded-lg bg-background/80 px-3 py-2 text-sm">
                        <span className="truncate flex-1">{item.title || item.summary || item.id}</span>
                        <Button
                          variant="outline"
                          size="sm"
                          className="ml-3 shrink-0 gap-1.5"
                          onClick={() => void applyCategoryChange(item, null)}
                          disabled={isItemMoving(item.id)}
                          aria-label={t("contentCategories.removeItem")}
                        >
                          {isItemMoving(item.id) ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FolderMinus className="h-3.5 w-3.5" />}
                          {t("contentCategories.removeItem")}
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {unclassifiedItems.length > 0 ? (
              <Button variant="outline" className="w-full" onClick={() => setShowAddModal(true)}>
                <FolderPlus className="h-4 w-4 mr-2" />
                {t("contentCategories.addItems")} ({unclassifiedItems.length})
              </Button>
            ) : null}
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="ghost" type="button" onClick={() => onOpenChange(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="button" onClick={onSave} disabled={pending}>
              {pending ? t("common.saving") : t("common.confirm")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showAddModal} onOpenChange={setShowAddModal}>
        <DialogContent className="max-w-2xl rounded-2xl">
          <DialogHeader className="text-left">
            <DialogTitle>{t("contentCategories.unclassifiedItems")}</DialogTitle>
            <DialogDescription>{t("contentCategories.addItems")}</DialogDescription>
          </DialogHeader>

          {isLoadingContent ? (
            <div className="rounded-lg border border-dashed border-border/60 px-4 py-8 text-center text-sm text-muted-foreground">
              {t("contentCategories.loadingItems")}
            </div>
          ) : unclassifiedItems.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border/60 px-4 py-8 text-center text-sm text-muted-foreground">
              {t("contentCategories.noUnclassifiedItems")}
            </div>
          ) : (
            <div className="max-h-96 overflow-y-auto rounded-lg border border-border/50 bg-background/50">
              <div className="p-3 space-y-2">
                {unclassifiedItems.map((item: any) => (
                  <div key={item.id} className="flex items-center justify-between rounded-lg bg-background/80 px-3 py-2 text-sm">
                    <span className="truncate flex-1">{item.title || item.summary || item.id}</span>
                    <Button
                      variant="outline"
                      size="sm"
                      className="ml-3 shrink-0 gap-1.5"
                      onClick={() => void applyCategoryChange(item, category?.name ?? null)}
                      disabled={isItemMoving(item.id)}
                      aria-label={t("contentCategories.addToCategory")}
                    >
                      {isItemMoving(item.id) ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FolderPlus className="h-3.5 w-3.5" />}
                      {t("contentCategories.addToCategory")}
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setShowAddModal(false)}>
              {t("common.done")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
