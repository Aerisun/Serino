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
} from "@/api/generated/admin/admin";
import type { ContentCreate, ContentUpdate } from "@/api/generated/model";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { Label } from "@/components/ui/Label";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/Select";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import { Trash2, Save } from "lucide-react";

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
    slug: "", title: "", summary: "", body: "", tags: [], status: "draft", visibility: "public", published_at: null,
    author_name: "", source: "",
  });

  useEffect(() => {
    if (item) setForm({ slug: item.slug, title: item.title, summary: item.summary || "", body: item.body, tags: item.tags, status: item.status, visibility: item.visibility, published_at: item.published_at, author_name: item.author_name || "", source: item.source || "" });
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

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      if (isNew) {
        await createExcerpt({ data: form });
      } else {
        await updateExcerpt({ itemId: id!, data: form as ContentUpdate });
      }
    } finally {
      setIsSaving(false);
    }
  };

  const setField = (k: string, v: any) => setForm((p) => ({ ...p, [k]: v }));

  return (
    <div>
      <PageHeader
        title={isNew ? t("excerpts.newExcerpt") : t("excerpts.editExcerpt")}
        actions={
          <div className="flex gap-2">
            {!isNew && <Button variant="destructive" onClick={() => { if (confirm(t("excerpts.deleteConfirm"))) deleteExcerptMutate({ itemId: id! }); }}><Trash2 className="h-4 w-4 mr-2" /> {t("common.delete")}</Button>}
            <Button onClick={handleSubmit} disabled={isSaving}><Save className="h-4 w-4 mr-2" /> {isSaving ? t("common.saving") : t("common.save")}</Button>
          </div>
        }
      />
      <form onSubmit={handleSubmit} className="space-y-6 max-w-3xl">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2"><Label>{t("posts.postTitle")}</Label><Input value={form.title} onChange={(e) => setField("title", e.target.value)} required /></div>
          <div className="space-y-2"><Label>{t("posts.slug")}</Label><Input value={form.slug} onChange={(e) => setField("slug", e.target.value)} required /></div>
        </div>
        <div className="space-y-2"><Label>{t("posts.summary")}</Label><Textarea value={form.summary || ""} onChange={(e) => setField("summary", e.target.value)} rows={2} /></div>
        <div className="space-y-2"><Label>{t("posts.body")}</Label><MarkdownEditor value={form.body} onChange={(v) => setField("body", v)} minHeight="250px" /></div>
        <div className="space-y-2"><Label>{t("posts.tags")}</Label><Input value={form.tags?.join(", ") || ""} onChange={(e) => setField("tags", e.target.value.split(",").map((t) => t.trim()).filter(Boolean))} /></div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2"><Label>{t("excerpts.authorName")}</Label><Input value={form.author_name || ""} onChange={(e) => setField("author_name", e.target.value)} placeholder={t("excerpts.authorPlaceholder")} /></div>
          <div className="space-y-2"><Label>{t("excerpts.source")}</Label><Input value={form.source || ""} onChange={(e) => setField("source", e.target.value)} placeholder={t("excerpts.sourcePlaceholder")} /></div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>{t("posts.status")}</Label>
            <Select value={form.status} onValueChange={(v) => setField("status", v)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="draft">{t("posts.draft")}</SelectItem><SelectItem value="published">{t("posts.published")}</SelectItem><SelectItem value="archived">{t("posts.archived")}</SelectItem></SelectContent></Select>
          </div>
          <div className="space-y-2">
            <Label>{t("posts.visibility")}</Label>
            <Select value={form.visibility} onValueChange={(v) => setField("visibility", v)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="public">{t("posts.public")}</SelectItem><SelectItem value="private">{t("posts.private")}</SelectItem></SelectContent></Select>
          </div>
        </div>
      </form>
    </div>
  );
}
