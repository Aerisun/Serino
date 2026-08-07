import {
  useGetThoughts,
  useCreateThoughts,
  useUpdateThoughts,
  useDeleteThoughts,
  getListThoughtsQueryKey,
  getGetThoughtsQueryKey,
} from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { ContentEditorHeaderActions } from "@/components/content/ContentEditorHeaderActions";
import { Button } from "@/components/ui/Button";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { AutoTitleField } from "@/components/content/AutoTitleField";
import { ContentCategoryField } from "@/components/content/ContentCategoryField";
import { PublishTimeFooter } from "@/components/content/PublishTimeFooter";
import { Label } from "@/components/ui/Label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Trash2, Eye } from "lucide-react";
import { useContentEditor, buildServerToForm } from "@/hooks/useContentEditor";
import { normalizeServerTextField } from "@/lib/content-editor";
import { MOOD_OPTIONS } from "@/lib/contentOptions";

const editorConfig = {
  contentType: "thoughts" as const,
  hooks: {
    useGet: useGetThoughts,
    useCreate: useCreateThoughts,
    useUpdate: useUpdateThoughts,
    useDelete: useDeleteThoughts,
    getListQueryKey: getListThoughtsQueryKey,
    getDetailQueryKey: getGetThoughtsQueryKey,
  },
  listRoute: "/thoughts",
  defaultForm: {
    slug: "", title: "", summary: "", body: "", tags: [],
    visibility: "private", published_at: null,
    category: "", mood: "",
  },
  serverToForm: buildServerToForm((item) => ({
    category: normalizeServerTextField(item.category),
    mood: normalizeServerTextField(item.mood),
  })),
  i18nKeys: {
    newTitle: "thoughts.newThought",
    editTitle: "thoughts.editThought",
    deleteConfirm: "thoughts.deleteConfirm",
  },
  buildPreviewPath: (_slug: string, storageKey: string) =>
    `/thoughts?previewStorageKey=${encodeURIComponent(storageKey)}`,
};

export default function ThoughtEditPage() {
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
            assetCategory="thought"
            value={form.body}
            onChange={(v) => setField("body", v)}
            minHeight="200px"
            imageLayout="attachments"
            mobileFullscreen
          />
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <ContentCategoryField contentType="thoughts" label={t("contentCategories.fieldLabel")} value={form.category || ""} placeholder={t("contentCategories.thoughtPlaceholder")} onChange={(nextValue) => setField("category", nextValue)} />
          <div className="space-y-2">
            <Label>{t("thoughts.mood")}</Label>
            <Select
              value={form.mood || "__empty"}
              onValueChange={(value) =>
                setField("mood", value === "__empty" ? "" : value)
              }
            >
              <SelectTrigger className="min-h-12 rounded-lg px-3 py-2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__empty">{t("common.empty")}</SelectItem>
                {MOOD_OPTIONS.map((option) => (
                  <SelectItem
                    key={option.value}
                    value={option.value}
                    className="text-lg leading-none"
                  >
                    {option.value}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
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
