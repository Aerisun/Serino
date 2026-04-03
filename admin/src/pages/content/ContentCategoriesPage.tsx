import { useMemo, useState, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  getListContentCategoriesQueryKey,
  useCreateContentCategory,
  useDeleteContentCategory,
  useListContentCategories,
  useUpdateContentCategory,
} from "@serino/api-client/admin";
import type { ContentCategoryRead } from "@serino/api-client/models";
import { PageHeader } from "@/components/PageHeader";
import { AdminSegmentedFilter } from "@/components/ui/AdminSegmentedFilter";
import { Button } from "@/components/ui/Button";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { CONTENT_CATEGORY_LABEL_KEYS, CONTENT_CATEGORY_TYPES, type ContentCategoryType } from "@/lib/contentCategories";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { CategoryDialog, EditCategoryDialog } from "./ContentCategoryDialogs";
import { getContentListQueryOptions } from "./contentCategoryQueries";

export default function ContentCategoriesPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [activeType, setActiveType] = useState<ContentCategoryType>("posts");
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [draftName, setDraftName] = useState("");
  const [editing, setEditing] = useState<ContentCategoryRead | null>(null);

  const { data, isLoading } = useListContentCategories(
    { content_type: activeType },
    { query: { staleTime: 60_000 } },
  );

  const categories = useMemo(() => data?.data ?? [], [data]);

  useEffect(() => {
    void queryClient.prefetchQuery(getContentListQueryOptions(activeType));
  }, [activeType, queryClient]);

  const invalidate = async (contentType: ContentCategoryType) => {
    await queryClient.invalidateQueries({
      queryKey: getListContentCategoriesQueryKey({ content_type: contentType }),
    });
    await queryClient.invalidateQueries({
      queryKey: getListContentCategoriesQueryKey(),
    });
  };

  const createCategory = useCreateContentCategory({
    mutation: {
      onSuccess: async () => {
        await invalidate(activeType);
        setCreateOpen(false);
        setDraftName("");
        toast.success(t("contentCategories.createSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const updateCategory = useUpdateContentCategory({
    mutation: {
      onSuccess: async () => {
        await invalidate(activeType);
        setEditOpen(false);
        setEditing(null);
        setDraftName("");
        toast.success(t("contentCategories.updateSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const deleteCategory = useDeleteContentCategory({
    mutation: {
      onSuccess: async () => {
        await invalidate(activeType);
        toast.success(t("contentCategories.deleteSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const handleCreate = async () => {
    const name = draftName.trim();
    if (!name) {
      toast.error(t("contentCategories.nameRequired"));
      return;
    }
    await createCategory.mutateAsync({
      data: { content_type: activeType, name },
    });
  };

  const handleUpdate = async () => {
    const name = draftName.trim();
    if (!editing) {
      return;
    }
    if (!name) {
      toast.error(t("contentCategories.nameRequired"));
      return;
    }
    await updateCategory.mutateAsync({
      categoryId: editing.id,
      data: { name },
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("contentCategories.title")}
      />

      <AdminSegmentedFilter
        value={activeType}
        onValueChange={(next) => setActiveType(next as any)}
        items={CONTENT_CATEGORY_TYPES.map((type) => ({
          value: type,
          label: t(CONTENT_CATEGORY_LABEL_KEYS[type]),
        }))}
        placement="below-header"
      />

      <section className="rounded-3xl border border-border/50 bg-background/70 p-6 shadow-[0_18px_50px_-32px_rgba(15,23,42,0.55)] backdrop-blur">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <div className="inline-flex items-center gap-1.5">
              <h2 className="text-lg font-semibold">{t(CONTENT_CATEGORY_LABEL_KEYS[activeType])}</h2>
              <LabelWithHelp
                hideLabel
                label={t(CONTENT_CATEGORY_LABEL_KEYS[activeType])}
                title="分类会用在哪里"
                description="这里管理当前内容类型的分类名称。创建后，分类会出现在对应内容编辑页的分类下拉框里。"
                usageTitle="你会在这里做什么"
                usageItems={[
                  "切换顶部类型标签后，只会管理该类型的分类。",
                  "新建后即可在对应内容编辑页选择该分类。",
                ]}
              />
            </div>
          </div>
          <Button
            onClick={() => {
              setDraftName("");
              setCreateOpen(true);
            }}
            className="shrink-0 gap-2"
          >
            <Plus className="h-4 w-4" />
            {t("contentCategories.createAction")}
          </Button>
        </div>

        {isLoading ? (
          <div className="rounded-2xl border border-dashed border-border/60 px-4 py-10 text-sm text-muted-foreground">
            {t("common.loading")}
          </div>
        ) : categories.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/60 px-4 py-10 text-sm text-muted-foreground">
            {t("contentCategories.empty")}
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {categories.map((category) => (
              <div
                key={category.id}
                className="rounded-2xl border border-border/50 bg-background/80 p-4 shadow-[0_14px_40px_-32px_rgba(15,23,42,0.85)]"
              >
                <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="text-base font-semibold">{category.name}</div>
                      <div className="text-sm text-muted-foreground">
                        {(category.usage_count ?? 0) + t("contentCategories.usedCountSuffix")}
                      </div>
                    </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => {
                        setEditing(category);
                        setDraftName(category.name);
                        setEditOpen(true);
                      }}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-destructive hover:text-destructive"
                      onClick={() => {
                        if (confirm(t("contentCategories.deleteConfirm"))) {
                          deleteCategory.mutate({ categoryId: category.id });
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <CategoryDialog
        open={createOpen}
        title={t("contentCategories.createTitle")}
        description={t(CONTENT_CATEGORY_LABEL_KEYS[activeType])}
        value={draftName}
        onValueChange={setDraftName}
        onSubmit={() => void handleCreate()}
        onOpenChange={(open) => {
          setCreateOpen(open);
          if (!open) {
            setDraftName("");
          }
        }}
        pending={createCategory.isPending}
      />

      <EditCategoryDialog
        open={editOpen}
        category={editing}
        contentType={activeType}
        categoryName={draftName}
        onNameChange={setDraftName}
        onSave={handleUpdate}
        onOpenChange={(open) => {
          setEditOpen(open);
          if (!open) {
            setEditing(null);
            setDraftName("");
          }
        }}
        pending={updateCategory.isPending}
      />
    </div>
  );
}
