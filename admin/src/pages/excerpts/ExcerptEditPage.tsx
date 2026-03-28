import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  useGetExcerpts,
  useCreateExcerpts,
  useUpdateExcerpts,
  useDeleteExcerpts,
  getListExcerptsQueryKey,
  getGetExcerptsQueryKey,
} from "@serino/api-client/admin";
import type { ContentCreate, ContentUpdate } from "@serino/api-client/models";
import { PageHeader } from "@/components/PageHeader";
import { ContentEditorHeaderActions } from "@/components/content/ContentEditorHeaderActions";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { ContentCategoryField } from "@/components/content/ContentCategoryField";
import { Label } from "@/components/ui/Label";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";

export default function ExcerptEditPage() {
  const { id } = useParams();
  const isNew = id === "new";
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useI18n();

  const { data: itemData } = useGetExcerpts(id!, {
    query: { enabled: !isNew && !!id },
  });
  const item = itemData?.data;

  const [form, setForm] = useState<ContentCreate>({
    slug: "", title: "", summary: "", body: "", tags: [], status: "draft", visibility: "private", published_at: null,
    category: "",
    author_name: "", source: "",
  });
  const [isPublishedAtManual, setIsPublishedAtManual] = useState(false);

  useEffect(() => {
    if (item) {
      const effectivePublishedAt = item.published_at || item.updated_at || null;
      const hasManualPublishedAt =
        Boolean(item.published_at) &&
        (!item.updated_at ||
          Math.abs(new Date(item.published_at!).getTime() - new Date(item.updated_at).getTime()) > 60_000);
      setForm({ slug: item.slug, title: item.title, summary: item.summary || "", body: item.body, tags: item.tags, status: item.status, visibility: item.visibility, published_at: effectivePublishedAt, category: item.category || "", author_name: item.author_name || "", source: item.source || "" });
      setIsPublishedAtManual(hasManualPublishedAt);
    }
  }, [item]);

  const invalidateQueries = () => {
    queryClient.invalidateQueries({ queryKey: getListExcerptsQueryKey() });
    if (id && !isNew) {
      queryClient.invalidateQueries({ queryKey: getGetExcerptsQueryKey(id) });
    }
  };

  const { mutateAsync: createExcerpt } = useCreateExcerpts({
    mutation: {
      onSuccess: (data) => {
        invalidateQueries();
        toast.success(t("common.operationSuccess"));
        navigate(`/excerpts/${data.data.id}`, { replace: true });
      },
      onError: (error: any) => { const msg = error?.response?.data?.detail || t("common.operationFailed"); toast.error(msg); },
    },
  });

  const { mutateAsync: updateExcerpt } = useUpdateExcerpts({
    mutation: {
      onSuccess: () => {
        invalidateQueries();
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => { const msg = error?.response?.data?.detail || t("common.operationFailed"); toast.error(msg); },
    },
  });

  const { mutate: deleteExcerptMutate } = useDeleteExcerpts({
    mutation: {
      onSuccess: () => {
        invalidateQueries();
        toast.success(t("common.operationSuccess"));
        navigate("/excerpts");
      },
      onError: (error: any) => { const msg = error?.response?.data?.detail || t("common.operationFailed"); toast.error(msg); },
    },
  });

  const [isSaving, setIsSaving] = useState(false);

  const saveExcerpt = async (mode: "draft" | "confirm") => {
    const nextStatus = mode === "draft" ? "draft" : form.visibility === "public" ? "published" : "archived";
    const nextPublishedAt =
      isPublishedAtManual && form.published_at
        ? form.published_at
        : new Date().toISOString();
    const nextForm = { ...form, status: nextStatus, published_at: nextPublishedAt };

    setIsSaving(true);
    try {
      if (isNew) {
        await createExcerpt({ data: nextForm });
      } else {
        await updateExcerpt({ itemId: id!, data: nextForm as ContentUpdate });
      }
      setForm((prev) => ({ ...prev, status: nextStatus, published_at: nextPublishedAt }));
    } finally {
      setIsSaving(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    await saveExcerpt("confirm");
  };

  const setField = (k: string, v: any) => setForm((p) => ({ ...p, [k]: v }));

  return (
    <div>
      <PageHeader
        title={isNew ? t("excerpts.newExcerpt") : t("excerpts.editExcerpt")}
        actions={
          <ContentEditorHeaderActions
            visibility={form.visibility}
            isSaving={isSaving}
            onToggleVisibility={() =>
              setField(
                "visibility",
                form.visibility === "public" ? "private" : "public",
              )
            }
            onSaveDraft={() => void saveExcerpt("draft")}
            onConfirm={() => void saveExcerpt("confirm")}
          />
        }
      />
      <form onSubmit={handleSubmit} className="space-y-6 max-w-3xl">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2"><Label>{t("posts.postTitle")}</Label><Input value={form.title} onChange={(e) => setField("title", e.target.value)} required /></div>
          <div className="space-y-2"><Label>{t("posts.slug")}</Label><Input value={form.slug} onChange={(e) => setField("slug", e.target.value)} required /></div>
        </div>
        <div className="space-y-2"><Label>{t("posts.body")}</Label><MarkdownEditor value={form.body} onChange={(v) => setField("body", v)} minHeight="250px" /></div>
        <div className="space-y-2"><Label>{t("posts.tags")}</Label><Input value={form.tags?.join(", ") || ""} onChange={(e) => setField("tags", e.target.value.split(",").map((t) => t.trim()).filter(Boolean))} /></div>
        <ContentCategoryField contentType="excerpts" label={t("contentCategories.fieldLabel")} value={form.category || ""} placeholder={t("contentCategories.excerptPlaceholder")} onChange={(nextValue) => setField("category", nextValue)} />
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2"><Label>{t("excerpts.authorName")}</Label><Input value={form.author_name || ""} onChange={(e) => setField("author_name", e.target.value)} placeholder={t("excerpts.authorPlaceholder")} /></div>
          <div className="space-y-2"><Label>{t("excerpts.source")}</Label><Input value={form.source || ""} onChange={(e) => setField("source", e.target.value)} placeholder={t("excerpts.sourcePlaceholder")} /></div>
        </div>

        <div className="pt-6 border-t border-border">
          <div className="rounded-2xl border border-border/60 bg-muted/20 px-4 py-4 sm:px-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
              {!isNew && (
                <Button
                  variant="destructive"
                  type="button"
                  className="h-11 rounded-xl px-5 shadow-sm shadow-destructive/25"
                  onClick={() => {
                    if (confirm(t("excerpts.deleteConfirm"))) {
                      deleteExcerptMutate({ itemId: id! });
                    }
                  }}
                >
                  <Trash2 className="h-4 w-4 mr-2" /> {t("common.delete")}
                </Button>
              )}
              <div className="space-y-2 w-full sm:w-80 sm:ml-auto">
                <Label className="text-sm font-medium">{t("posts.publishedAt")}</Label>
                <Input
                  className="h-11 rounded-xl border-border/60 bg-background/90 shadow-sm"
                  type="datetime-local"
                  value={
                    form.published_at
                      ? new Date(form.published_at).toISOString().slice(0, 16)
                      : ""
                  }
                  onChange={(e) => {
                    const nextPublishedAt = e.target.value
                      ? new Date(e.target.value).toISOString()
                      : null;
                    setIsPublishedAtManual(Boolean(nextPublishedAt));
                    setField("published_at", nextPublishedAt);
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}
