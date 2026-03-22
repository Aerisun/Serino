import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getPost, createPost, updatePost, deletePost } from "@/api/endpoints/posts";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { Label } from "@/components/ui/Label";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/Select";
import { useI18n } from "@/i18n";
import type { ContentCreate, ContentUpdate } from "@/types/models";
import { Trash2, Save } from "lucide-react";

export default function PostEditPage() {
  const { id } = useParams();
  const isNew = id === "new";
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useI18n();

  const { data: post } = useQuery({
    queryKey: ["posts", id],
    queryFn: () => getPost(id!),
    enabled: !isNew && !!id,
  });

  const [form, setForm] = useState<ContentCreate>({
    slug: "",
    title: "",
    summary: "",
    body: "",
    tags: [],
    status: "draft",
    visibility: "public",
    published_at: null,
    category: "",
    view_count: 0,
  });

  useEffect(() => {
    if (post) {
      setForm({
        slug: post.slug,
        title: post.title,
        summary: post.summary || "",
        body: post.body,
        tags: post.tags,
        status: post.status,
        visibility: post.visibility,
        published_at: post.published_at,
        category: (post as any).category || "",
        view_count: (post as any).view_count || 0,
      });
    }
  }, [post]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (isNew) {
        return createPost(form);
      }
      const update: ContentUpdate = { ...form };
      return updatePost(id!, update);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["posts"] });
      if (isNew) navigate(`/posts/${data.id}`, { replace: true });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deletePost(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["posts"] });
      navigate("/posts");
    },
  });

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    saveMutation.mutate();
  };

  const setField = (key: string, value: any) => setForm((prev) => ({ ...prev, [key]: value }));

  return (
    <div>
      <PageHeader
        title={isNew ? t("posts.newPost") : t("posts.editPost")}
        actions={
          <div className="flex gap-2">
            {!isNew && (
              <Button variant="destructive" onClick={() => { if (confirm(t("posts.deleteConfirm"))) deleteMutation.mutate(); }}>
                <Trash2 className="h-4 w-4 mr-2" /> {t("common.delete")}
              </Button>
            )}
            <Button onClick={handleSubmit} disabled={saveMutation.isPending}>
              <Save className="h-4 w-4 mr-2" /> {saveMutation.isPending ? t("common.saving") : t("common.save")}
            </Button>
          </div>
        }
      />

      <form onSubmit={handleSubmit} className="space-y-6 max-w-3xl">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>{t("posts.postTitle")}</Label>
            <Input value={form.title} onChange={(e) => setField("title", e.target.value)} required />
          </div>
          <div className="space-y-2">
            <Label>{t("posts.slug")}</Label>
            <Input value={form.slug} onChange={(e) => setField("slug", e.target.value)} required />
          </div>
        </div>

        <div className="space-y-2">
          <Label>{t("posts.summary")}</Label>
          <Textarea value={form.summary || ""} onChange={(e) => setField("summary", e.target.value)} rows={2} />
        </div>

        <div className="space-y-2">
          <Label>{t("posts.body")}</Label>
          <MarkdownEditor value={form.body} onChange={(v) => setField("body", v)} minHeight="400px" />
        </div>

        <div className="space-y-2">
          <Label>{t("posts.tagsHint")}</Label>
          <Input
            value={form.tags?.join(", ") || ""}
            onChange={(e) => setField("tags", e.target.value.split(",").map((t) => t.trim()).filter(Boolean))}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>分类</Label>
            <Input value={form.category || ""} onChange={(e) => setField("category", e.target.value)} placeholder="文章分类" />
          </div>
          <div className="space-y-2">
            <Label>浏览量</Label>
            <Input type="number" value={form.view_count || 0} onChange={(e) => setField("view_count", parseInt(e.target.value) || 0)} />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-2">
            <Label>{t("posts.status")}</Label>
            <Select value={form.status} onValueChange={(v) => setField("status", v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="draft">{t("posts.draft")}</SelectItem>
                <SelectItem value="published">{t("posts.published")}</SelectItem>
                <SelectItem value="archived">{t("posts.archived")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>{t("posts.visibility")}</Label>
            <Select value={form.visibility} onValueChange={(v) => setField("visibility", v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="public">{t("posts.public")}</SelectItem>
                <SelectItem value="private">{t("posts.private")}</SelectItem>
                <SelectItem value="unlisted">{t("posts.unlisted")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>{t("posts.publishedAt")}</Label>
            <Input
              type="datetime-local"
              value={form.published_at ? new Date(form.published_at).toISOString().slice(0, 16) : ""}
              onChange={(e) => setField("published_at", e.target.value ? new Date(e.target.value).toISOString() : null)}
            />
          </div>
        </div>
      </form>
    </div>
  );
}
