import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getDiary, createDiary, updateDiary, deleteDiary } from "@/api/endpoints/diary";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { Label } from "@/components/ui/Label";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/Select";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import type { ContentCreate, ContentUpdate } from "@/types/models";
import { Trash2, Save, ExternalLink } from "lucide-react";

export default function DiaryEditPage() {
  const { id } = useParams();
  const isNew = id === "new";
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useI18n();

  const { data: item } = useQuery({
    queryKey: ["diary", id],
    queryFn: () => getDiary(id!),
    enabled: !isNew && !!id,
  });

  const [form, setForm] = useState<ContentCreate>({
    slug: "", title: "", summary: "", body: "", tags: [], status: "draft", visibility: "public", published_at: null,
    mood: "", weather: "", poem: "",
  });

  useEffect(() => {
    if (item) setForm({ slug: item.slug, title: item.title, summary: item.summary || "", body: item.body, tags: item.tags, status: item.status, visibility: item.visibility, published_at: item.published_at, mood: (item as any).mood || "", weather: (item as any).weather || "", poem: (item as any).poem || "" });
  }, [item]);

  const save = useMutation({
    mutationFn: () => isNew ? createDiary(form) : updateDiary(id!, form as ContentUpdate),
    onSuccess: (data) => { queryClient.invalidateQueries({ queryKey: ["diary"] }); toast.success(t("common.operationSuccess")); if (isNew) navigate(`/diary/${data.id}`, { replace: true }); },
    onError: (error: any) => { const msg = error?.response?.data?.detail || t("common.operationFailed"); toast.error(msg); },
  });

  const del = useMutation({
    mutationFn: () => deleteDiary(id!),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["diary"] }); toast.success(t("common.operationSuccess")); navigate("/diary"); },
    onError: (error: any) => { const msg = error?.response?.data?.detail || t("common.operationFailed"); toast.error(msg); },
  });

  const setField = (k: string, v: any) => setForm((p) => ({ ...p, [k]: v }));
  const handleSubmit = (e: FormEvent) => { e.preventDefault(); save.mutate(); };

  return (
    <div>
      <PageHeader
        title={isNew ? t("diary.newEntry") : t("diary.editEntry")}
        actions={
          <div className="flex gap-2">
            {!isNew && form.slug && form.status === "published" && (
              <Button variant="outline" onClick={() => window.open(`${import.meta.env.VITE_FRONTEND_URL || 'http://localhost:8080'}/diary/${form.slug}`, '_blank')}>
                <ExternalLink className="h-4 w-4 mr-2" /> {t("common.preview")}
              </Button>
            )}
            {!isNew && <Button variant="destructive" onClick={() => { if (confirm(t("diary.deleteConfirm"))) del.mutate(); }}><Trash2 className="h-4 w-4 mr-2" /> {t("common.delete")}</Button>}
            <Button onClick={handleSubmit} disabled={save.isPending}><Save className="h-4 w-4 mr-2" /> {save.isPending ? t("common.saving") : t("common.save")}</Button>
          </div>
        }
      />
      <form onSubmit={handleSubmit} className="space-y-6 max-w-3xl">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2"><Label>{t("posts.postTitle")}</Label><Input value={form.title} onChange={(e) => setField("title", e.target.value)} required /></div>
          <div className="space-y-2"><Label>{t("posts.slug")}</Label><Input value={form.slug} onChange={(e) => setField("slug", e.target.value)} required /></div>
        </div>
        <div className="space-y-2"><Label>{t("posts.summary")}</Label><Textarea value={form.summary || ""} onChange={(e) => setField("summary", e.target.value)} rows={2} /></div>
        <div className="space-y-2"><Label>{t("posts.body")}</Label><MarkdownEditor value={form.body} onChange={(v) => setField("body", v)} minHeight="350px" /></div>
        <div className="space-y-2"><Label>{t("posts.tags")}</Label><Input value={form.tags?.join(", ") || ""} onChange={(e) => setField("tags", e.target.value.split(",").map((t) => t.trim()).filter(Boolean))} /></div>
        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-2"><Label>{t("diary.mood")}</Label><Input value={form.mood || ""} onChange={(e) => setField("mood", e.target.value)} placeholder={t("diary.moodPlaceholder")} /></div>
          <div className="space-y-2"><Label>{t("diary.weather")}</Label><Input value={form.weather || ""} onChange={(e) => setField("weather", e.target.value)} placeholder={t("diary.weatherPlaceholder")} /></div>
          <div className="space-y-2"><Label>{t("diary.poem")}</Label><Input value={form.poem || ""} onChange={(e) => setField("poem", e.target.value)} placeholder={t("diary.poemPlaceholder")} /></div>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-2">
            <Label>{t("posts.status")}</Label>
            <Select value={form.status} onValueChange={(v) => setField("status", v)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="draft">{t("posts.draft")}</SelectItem><SelectItem value="published">{t("posts.published")}</SelectItem><SelectItem value="archived">{t("posts.archived")}</SelectItem></SelectContent></Select>
          </div>
          <div className="space-y-2">
            <Label>{t("posts.visibility")}</Label>
            <Select value={form.visibility} onValueChange={(v) => setField("visibility", v)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="public">{t("posts.public")}</SelectItem><SelectItem value="private">{t("posts.private")}</SelectItem><SelectItem value="unlisted">{t("posts.unlisted")}</SelectItem></SelectContent></Select>
          </div>
          <div className="space-y-2">
            <Label>{t("posts.publishedAt")}</Label>
            <Input type="datetime-local" value={form.published_at ? new Date(form.published_at).toISOString().slice(0, 16) : ""} onChange={(e) => setField("published_at", e.target.value ? new Date(e.target.value).toISOString() : null)} />
          </div>
        </div>
      </form>
    </div>
  );
}
