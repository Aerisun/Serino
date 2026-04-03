import {
  useGetPosts,
  useCreatePosts,
  useUpdatePosts,
  useDeletePosts,
  getListPostsQueryKey,
  getGetPostsQueryKey,
} from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { ContentEditorHeaderActions } from "@/components/content/ContentEditorHeaderActions";
import { ContentCategoryField } from "@/components/content/ContentCategoryField";
import { PublishTimeFooter } from "@/components/content/PublishTimeFooter";
import { Label } from "@/components/ui/Label";
import { Trash2, Eye } from "lucide-react";
import { useContentEditor, buildServerToForm } from "@/hooks/useContentEditor";

const editorConfig = {
  contentType: "posts" as const,
  hooks: {
    useGet: useGetPosts,
    useCreate: useCreatePosts,
    useUpdate: useUpdatePosts,
    useDelete: useDeletePosts,
    getListQueryKey: getListPostsQueryKey,
    getDetailQueryKey: getGetPostsQueryKey,
  },
  listRoute: "/posts",
  defaultForm: {
    slug: "", title: "", summary: "", body: "", tags: [],
    status: "draft", visibility: "private", published_at: null,
    category: "",
  },
  serverToForm: buildServerToForm((item) => ({
    category: item.category || "",
  })),
  i18nKeys: {
    newTitle: "posts.newPost",
    editTitle: "posts.editPost",
    deleteConfirm: "posts.deleteConfirm",
  },
};

export default function PostEditPage() {
  const editor = useContentEditor(editorConfig);
  const { form, setField, isSaving, isPublishedAtManual, setIsPublishedAtManual, isNew, t } = editor;

  return (
    <div>
      <PageHeader
        title={editor.pageTitle}
        actions={
          <ContentEditorHeaderActions
            visibility={form.visibility}
            isSaving={isSaving}
            onToggleVisibility={() =>
              setField("visibility", form.visibility === "public" ? "private" : "public")
            }
            onExit={() => void editor.exitEditor()}
            onConfirm={() => void editor.save("confirm")}
            extraActions={
              <Button type="button" variant="outline" className="preview-glow-button" onClick={editor.openPreview} disabled={!form.body}>
                <Eye className="h-4 w-4 mr-2" /> {t("common.preview")}
              </Button>
            }
          />
        }
      />

      <form onSubmit={editor.handleSubmit} className="space-y-6 max-w-3xl mx-auto">
        <div className="space-y-2">
          <Label>{t("posts.postTitle")}</Label>
          <Input value={form.title} onChange={(e) => setField("title", e.target.value)} required />
        </div>

        <div className="space-y-2">
          <Label>{t("posts.summary")}</Label>
          <Textarea value={form.summary || ""} onChange={(e) => setField("summary", e.target.value)} rows={2} />
        </div>

        <div className="space-y-2">
          <Label>{t("posts.body")}</Label>
          <MarkdownEditor value={form.body} onChange={(v) => setField("body", v)} minHeight="400px" />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>{t("posts.tagsHint")}</Label>
            <Input
              value={form.tags?.join(", ") || ""}
              onChange={(e) => setField("tags", e.target.value.split(",").map((t) => t.trim()).filter(Boolean))}
            />
          </div>
          <ContentCategoryField
            contentType="posts"
            label={t("contentCategories.fieldLabel")}
            value={form.category || ""}
            placeholder={t("contentCategories.postPlaceholder")}
            onChange={(nextValue) => setField("category", nextValue)}
          />
        </div>

        <div className="pt-6 border-t border-border">
          <PublishTimeFooter
            value={form.published_at}
            onChange={(value) => setField("published_at", value)}
            isCustom={isPublishedAtManual}
            onCustomChange={setIsPublishedAtManual}
            label={t("posts.publishedAt")}
            deleteButton={
              !isNew && (
                <Button
                  variant="destructive" type="button"
                  className="h-9 rounded-lg px-3 text-sm shadow-sm shadow-destructive/25"
                  onClick={editor.confirmDelete}
                >
                  <Trash2 className="h-4 w-4 mr-2" /> {t("common.delete")}
                </Button>
              )
            }
          />
        </div>
      </form>
    </div>
  );
}
