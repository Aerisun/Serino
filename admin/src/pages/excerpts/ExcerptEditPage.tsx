import {
  useGetExcerpts,
  useCreateExcerpts,
  useUpdateExcerpts,
  useDeleteExcerpts,
  getListExcerptsQueryKey,
  getGetExcerptsQueryKey,
} from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { ContentEditorHeaderActions } from "@/components/content/ContentEditorHeaderActions";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { ContentCategoryField } from "@/components/content/ContentCategoryField";
import { PublishTimeFooter } from "@/components/content/PublishTimeFooter";
import { Label } from "@/components/ui/Label";
import { Trash2, Eye } from "lucide-react";
import { useContentEditor, buildServerToForm } from "@/hooks/useContentEditor";

const editorConfig = {
  contentType: "excerpts" as const,
  hooks: {
    useGet: useGetExcerpts,
    useCreate: useCreateExcerpts,
    useUpdate: useUpdateExcerpts,
    useDelete: useDeleteExcerpts,
    getListQueryKey: getListExcerptsQueryKey,
    getDetailQueryKey: getGetExcerptsQueryKey,
  },
  listRoute: "/excerpts",
  defaultForm: {
    slug: "", title: "", summary: "", body: "", tags: [],
    status: "draft", visibility: "private", published_at: null,
    category: "", author_name: "", source: "",
  },
  serverToForm: buildServerToForm((item) => ({
    category: item.category || "",
    author_name: item.author_name || "",
    source: item.source || "",
  })),
  i18nKeys: {
    newTitle: "excerpts.newExcerpt",
    editTitle: "excerpts.editExcerpt",
    deleteConfirm: "excerpts.deleteConfirm",
  },
  buildPreviewPath: (_slug: string, storageKey: string) =>
    `/excerpts?previewStorageKey=${encodeURIComponent(storageKey)}`,
};

export default function ExcerptEditPage() {
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
        <div className="space-y-2"><Label>{t("posts.body")}</Label><MarkdownEditor value={form.body} onChange={(v) => setField("body", v)} minHeight="250px" /></div>
        <ContentCategoryField contentType="excerpts" label={t("contentCategories.fieldLabel")} value={form.category || ""} placeholder={t("contentCategories.excerptPlaceholder")} onChange={(nextValue) => setField("category", nextValue)} />
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2"><Label>{t("excerpts.authorName")}</Label><Input value={form.author_name || ""} onChange={(e) => setField("author_name", e.target.value)} placeholder={t("excerpts.authorPlaceholder")} /></div>
          <div className="space-y-2"><Label>{t("excerpts.source")}</Label><Input value={form.source || ""} onChange={(e) => setField("source", e.target.value)} placeholder={t("excerpts.sourcePlaceholder")} /></div>
        </div>
        <div className="space-y-2">
          <Label>{t("common.title")}</Label>
          <Input
            value={form.title}
            onChange={(event) => setField("title", event.target.value)}
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
                <Button variant="destructive" type="button" className="h-9 rounded-lg px-3 text-sm shadow-sm shadow-destructive/25" onClick={editor.confirmDelete}>
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
