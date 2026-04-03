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
    status: "draft", visibility: "private", published_at: null,
    category: "", mood: "",
  },
  serverToForm: buildServerToForm((item) => ({
    category: item.category || "",
    mood: item.mood || "",
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
        <div className="space-y-2"><Label>{t("posts.body")}</Label><MarkdownEditor value={form.body} onChange={(v) => setField("body", v)} minHeight="200px" /></div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <ContentCategoryField contentType="thoughts" label={t("contentCategories.fieldLabel")} value={form.category || ""} placeholder={t("contentCategories.thoughtPlaceholder")} onChange={(nextValue) => setField("category", nextValue)} />
          <div className="space-y-2">
            <Label>{t("thoughts.mood")}</Label>
            <Select value={form.mood || undefined} onValueChange={(value) => setField("mood", value === "__empty" ? "" : value)}>
              <SelectTrigger className="h-auto min-h-12 rounded-lg border-input bg-background px-3 py-2">
                <SelectValue placeholder="" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__empty">{t("common.empty")}</SelectItem>
                {MOOD_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    <span className="text-lg leading-none">{option.value}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
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
