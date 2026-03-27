import { useMemo, useState } from "react";
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
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { useI18n } from "@/i18n";
import { CONTENT_CATEGORY_LABEL_KEYS, CONTENT_CATEGORY_TYPES, type ContentCategoryType } from "@/lib/contentCategories";
import { cn } from "@/lib/utils";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

function CategoryDialog({
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
        const message = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(message);
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
        const message = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(message);
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
        const message = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(message);
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
        description={t("contentCategories.description")}
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
            <h2 className="text-lg font-semibold">{t(CONTENT_CATEGORY_LABEL_KEYS[activeType])}</h2>
            <p className="text-sm text-muted-foreground">{t("contentCategories.sectionHint")}</p>
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

      <CategoryDialog
        open={editOpen}
        title={t("contentCategories.editTitle")}
        description={editing?.name || ""}
        value={draftName}
        onValueChange={setDraftName}
        onSubmit={() => void handleUpdate()}
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
