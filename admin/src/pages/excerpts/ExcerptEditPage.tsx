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
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { ContentCategoryField } from "@/components/content/ContentCategoryField";
import { Label } from "@/components/ui/Label";
import { StatusVisibilityPills } from "@/components/StatusVisibilityPills";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import { Trash2, LogOut, Check } from "lucide-react";

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

  useEffect(() => {
    if (item) setForm({ slug: item.slug, title: item.title, summary: item.summary || "", body: item.body, tags: item.tags, status: item.status, visibility: item.visibility, published_at: item.published_at, category: item.category || "", author_name: item.author_name || "", source: item.source || "" });
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
    const nextForm = { ...form, status: nextStatus };

    setIsSaving(true);
    try {
      if (isNew) {
        await createExcerpt({ data: nextForm });
      } else {
        await updateExcerpt({ itemId: id!, data: nextForm as ContentUpdate });
      }
      setForm((prev) => ({ ...prev, status: nextStatus }));
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
          <div className="flex flex-wrap items-center gap-2">
            <StatusVisibilityPills visibility={form.visibility} onToggleVisibility={() => setField("visibility", form.visibility === "public" ? "private" : "public")} />
            <Button variant="secondary" className="border-white/70 bg-white/70 text-slate-900 shadow-[0_10px_30px_-12px_rgba(255,255,255,0.85)] backdrop-blur-md ring-1 ring-white/50 hover:bg-white/85 hover:shadow-[0_16px_40px_-14px_rgba(255,255,255,0.9)] dark:border-white/20 dark:bg-white/15 dark:text-white dark:ring-white/15 dark:hover:bg-white/20" onClick={() => void saveExcerpt("draft")} disabled={isSaving}><LogOut className="h-4 w-4 mr-2" /> {isSaving ? t("common.saving") : t("common.saveDraft")}</Button>
            <Button variant="secondary" className="border-emerald-300/70 bg-emerald-500/85 text-white shadow-[0_10px_30px_-12px_rgba(34,197,94,0.75)] backdrop-blur-md ring-1 ring-emerald-200/50 hover:bg-emerald-500 hover:shadow-[0_16px_40px_-14px_rgba(34,197,94,0.85)] dark:border-emerald-400/30 dark:bg-emerald-500/75 dark:text-white dark:ring-emerald-300/20 dark:hover:bg-emerald-400/80" onClick={() => void saveExcerpt("confirm")} disabled={isSaving}><Check className="h-4 w-4 mr-2" /> {isSaving ? t("common.saving") : t("common.confirm")}</Button>
          </div>
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

        {!isNew && (
          <div className="pt-6 border-t border-border flex justify-start">
            <Button
              variant="destructive"
              type="button"
              onClick={() => {
                if (confirm(t("excerpts.deleteConfirm"))) {
                  deleteExcerptMutate({ itemId: id! });
                }
              }}
            >
              <Trash2 className="h-4 w-4 mr-2" /> {t("common.delete")}
            </Button>
          </div>
        )}
      </form>
    </div>
  );
}
