import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getThought, createThought, updateThought, deleteThought } from "@/api/endpoints/thoughts";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Label } from "@/components/ui/Label";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/Select";
import { useI18n } from "@/i18n";
import type { ContentCreate, ContentUpdate } from "@/types/models";
import { Trash2, Save } from "lucide-react";

export default function ThoughtEditPage() {
  const { id } = useParams();
  const isNew = id === "new";
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useI18n();

  const { data: item } = useQuery({
    queryKey: ["thoughts", id], queryFn: () => getThought(id!), enabled: !isNew && !!id,
  });

  const [form, setForm] = useState<ContentCreate>({
    slug: "", title: "", summary: "", body: "", tags: [], status: "draft", visibility: "public", published_at: null,
    mood: "",
  });

  useEffect(() => {
    if (item) setForm({ slug: item.slug, title: item.title, summary: item.summary || "", body: item.body, tags: item.tags, status: item.status, visibility: item.visibility, published_at: item.published_at, mood: (item as any).mood || "" });
  }, [item]);

  const save = useMutation({
    mutationFn: () => isNew ? createThought(form) : updateThought(id!, form as ContentUpdate),
    onSuccess: (data) => { queryClient.invalidateQueries({ queryKey: ["thoughts"] }); if (isNew) navigate(`/thoughts/${data.id}`, { replace: true }); },
  });

  const del = useMutation({
    mutationFn: () => deleteThought(id!),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["thoughts"] }); navigate("/thoughts"); },
  });

  const setField = (k: string, v: any) => setForm((p) => ({ ...p, [k]: v }));
  const handleSubmit = (e: FormEvent) => { e.preventDefault(); save.mutate(); };

  return (
    <div>
      <PageHeader
        title={isNew ? t("thoughts.newThought") : t("thoughts.editThought")}
        actions={
          <div className="flex gap-2">
            {!isNew && <Button variant="destructive" onClick={() => { if (confirm(t("thoughts.deleteConfirm"))) del.mutate(); }}><Trash2 className="h-4 w-4 mr-2" /> {t("common.delete")}</Button>}
            <Button onClick={handleSubmit} disabled={save.isPending}><Save className="h-4 w-4 mr-2" /> {save.isPending ? t("common.saving") : t("common.save")}</Button>
          </div>
        }
      />
      <form onSubmit={handleSubmit} className="space-y-6 max-w-3xl">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2"><Label>{t("posts.postTitle")}</Label><Input value={form.title} onChange={(e) => setField("title", e.target.value)} required /></div>
          <div className="space-y-2"><Label>{t("posts.slug")}</Label><Input value={form.slug} onChange={(e) => setField("slug", e.target.value)} required /></div>
        </div>
        <div className="space-y-2"><Label>{t("posts.body")}</Label><Textarea value={form.body} onChange={(e) => setField("body", e.target.value)} rows={8} required /></div>
        <div className="space-y-2"><Label>{t("posts.tags")}</Label><Input value={form.tags?.join(", ") || ""} onChange={(e) => setField("tags", e.target.value.split(",").map((t) => t.trim()).filter(Boolean))} /></div>
        <div className="space-y-2"><Label>{t("thoughts.mood")}</Label><Input value={form.mood || ""} onChange={(e) => setField("mood", e.target.value)} placeholder={t("thoughts.moodPlaceholder")} /></div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>{t("posts.status")}</Label>
            <Select value={form.status} onValueChange={(v) => setField("status", v)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="draft">{t("posts.draft")}</SelectItem><SelectItem value="published">{t("posts.published")}</SelectItem></SelectContent></Select>
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
