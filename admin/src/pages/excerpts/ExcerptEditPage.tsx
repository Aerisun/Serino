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
import { AutoTitleField } from "@/components/content/AutoTitleField";
import { ContentCategoryField } from "@/components/content/ContentCategoryField";
import { PublishTimeFooter } from "@/components/content/PublishTimeFooter";
import { Label } from "@/components/ui/Label";
import { Trash2, Eye } from "lucide-react";
import { useContentEditor, buildServerToForm } from "@/hooks/useContentEditor";
import { normalizeServerTextField } from "@/lib/content-editor";

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
    visibility: "private", published_at: null,
    category: "", author_name: "", source: "",
  },
  serverToForm: buildServerToForm((item) => ({
    category: normalizeServerTextField(item.category),
    author_name: normalizeServerTextField(item.author_name),
    source: normalizeServerTextField(item.source),
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
  const {
    form,
    setField,
    isSaving,
    isPublishedAtManual,
    setIsPublishedAtManual,
    isAutoTitleEnabled,
    setIsAutoTitleEnabled,
    isNew,
    t,
  } = editor;

  return (
    <div>
      <PageHeader
        title={editor.pageTitle}
        actions={
          <ContentEditorHeaderActions
            visibility={form.visibility === "public" ? "public" : "private"}
            isSaving={isSaving}
            onToggleVisibility={() =>
              setField("visibility", form.visibility === "public" ? "private" : "public")
            }
            onExit={() => void editor.exitEditor()}
            onConfirm={() => void editor.save()}
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
          <Label>{t("posts.body")}</Label>
          <MarkdownEditor
            value={form.body}
            onChange={(v) => setField("body", v)}
            minHeight="250px"
            imageLayout="attachments"
            mobileFullscreen
          />
        </div>
        <ContentCategoryField contentType="excerpts" label={t("contentCategories.fieldLabel")} value={form.category || ""} placeholder={t("contentCategories.excerptPlaceholder")} onChange={(nextValue) => setField("category", nextValue)} />
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2"><Label>{t("excerpts.authorName")}</Label><Input value={form.author_name || ""} onChange={(e) => setField("author_name", e.target.value)} placeholder={t("excerpts.authorPlaceholder")} /></div>
          <div className="space-y-2"><Label>{t("excerpts.source")}</Label><Input value={form.source || ""} onChange={(e) => setField("source", e.target.value)} placeholder={t("excerpts.sourcePlaceholder")} /></div>
        </div>
        <div className="space-y-3 border-t border-border pt-4 sm:pt-6 md:grid md:grid-cols-2 md:items-start md:gap-5 md:space-y-0">
          <AutoTitleField
            value={form.title}
            onChange={(value) => setField("title", value)}
            isAuto={isAutoTitleEnabled}
            onAutoChange={setIsAutoTitleEnabled}
            switchLabel={t("common.autoTitle")}
            inputLabel={t("common.title")}
            required
            className="md:min-w-0"
          />
          <PublishTimeFooter
            value={form.published_at}
            onChange={(value) => setField("published_at", value)}
            isCustom={isPublishedAtManual}
            onCustomChange={setIsPublishedAtManual}
            label={t("posts.publishedAt")}
            className="md:min-w-0"
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
