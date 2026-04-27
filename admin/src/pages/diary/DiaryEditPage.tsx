import { useState } from "react";
import {
  postGenerateDiaryPoemApiV1AdminDiaryGeneratePoemPost,
  useGetDiary,
  useCreateDiary,
  useUpdateDiary,
  useDeleteDiary,
  getListDiaryQueryKey,
  getGetDiaryQueryKey,
} from "@serino/api-client/admin";
import type { PoemGenerationRequest, PoemGenerationResponse } from "@serino/api-client/models";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { ContentEditorHeaderActions } from "@/components/content/ContentEditorHeaderActions";
import { AutoTitleField } from "@/components/content/AutoTitleField";
import { PublishTimeFooter } from "@/components/content/PublishTimeFooter";
import { AiActionCluster } from "@/components/ui/AiActionCluster";
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
import { MOOD_OPTIONS, WEATHER_OPTIONS } from "@/lib/contentOptions";
import { toast } from "sonner";

async function requestDiaryPoem(payload: PoemGenerationRequest) {
  return postGenerateDiaryPoemApiV1AdminDiaryGeneratePoemPost(payload).then(
    (response) => response.data as PoemGenerationResponse,
  );
}

const editorConfig = {
  contentType: "diary" as const,
  hooks: {
    useGet: useGetDiary,
    useCreate: useCreateDiary,
    useUpdate: useUpdateDiary,
    useDelete: useDeleteDiary,
    getListQueryKey: getListDiaryQueryKey,
    getDetailQueryKey: getGetDiaryQueryKey,
  },
  listRoute: "/diary",
  defaultForm: {
    slug: "", title: "", summary: "", body: "", tags: [],
    status: "draft", visibility: "private", published_at: null,
    mood: "", weather: "", poem: "",
  },
  serverToForm: buildServerToForm((item) => ({
    mood: item.mood || "",
    weather: item.weather || "",
    poem: item.poem || "",
  })),
  i18nKeys: {
    newTitle: "diary.newEntry",
    editTitle: "diary.editEntry",
    deleteConfirm: "diary.deleteConfirm",
  },
};

export default function DiaryEditPage() {
  const editor = useContentEditor(editorConfig);
  const {
    form,
    setField,
    isSaving,
    isNew,
    isPublishedAtManual,
    setIsPublishedAtManual,
    isAutoTitleEnabled,
    setIsAutoTitleEnabled,
    t,
  } = editor;
  const [isGeneratingPoem, setIsGeneratingPoem] = useState(false);
  const [poemCustomRequirement, setPoemCustomRequirement] = useState("");

  const generatePoem = async (customRequirement?: string) => {
    if (!form.body.trim()) {
      toast.error(t("diary.poemAiNeedDraft"));
      return;
    }

    setIsGeneratingPoem(true);
    try {
      const response = await requestDiaryPoem({
        body: form.body,
        title: form.title || null,
        summary: form.summary || null,
        tags: form.tags || [],
        mood: form.mood || null,
        weather: form.weather || null,
        custom_requirement: customRequirement?.trim() || poemCustomRequirement.trim() || null,
      });
      setField("poem", response.poem);
      toast.success(t("diary.poemAiSuccess"));
    } catch (error) {
      const message = error instanceof Error && error.message.trim()
        ? error.message
        : t("common.operationFailed");
      toast.error(message);
    } finally {
      setIsGeneratingPoem(false);
    }
  };

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
          <Label>{t("posts.summary")}</Label>
          <Textarea value={form.summary || ""} onChange={(e) => setField("summary", e.target.value)} rows={2} />
        </div>
        <div className="space-y-2">
          <Label>{t("posts.body")}</Label>
          <MarkdownEditor value={form.body} onChange={(v) => setField("body", v)} minHeight="350px" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-2">
            <Label>{t("diary.mood")}</Label>
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
          <div className="space-y-2">
            <Label>{t("diary.weather")}</Label>
            <Select
              value={form.weather || "__empty"}
              onValueChange={(value) =>
                setField("weather", value === "__empty" ? "" : value)
              }
            >
              <SelectTrigger className="min-h-10 rounded-md px-3 py-2 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__empty">{t("common.empty")}</SelectItem>
                {WEATHER_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {t(option.labelKey)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="col-span-1 md:col-span-2 space-y-2">
            <div className="flex items-center justify-between gap-3">
              <Label>{t("diary.poem")}</Label>
              <AiActionCluster
                actionLabel={t("diary.poemAiGenerate")}
                detailLabel={t("diary.poemAiPromptLabel")}
                loading={isGeneratingPoem}
                onAction={(detail) => generatePoem(detail)}
                showDetailTrigger
                detailValue={poemCustomRequirement}
                onDetailChange={setPoemCustomRequirement}
                detailTitle={t("diary.poemAiPanelTitle")}
                detailDescription={t("diary.poemAiPromptHint")}
                detailPlaceholder={t("diary.poemAiPromptPlaceholder")}
                submitLabel={t("diary.poemAiPanelAction")}
                clearLabel={t("common.clear")}
                closeLabel={t("common.cancel")}
                responseTitle={t("diary.poemAiResponseTitle")}
                responseValue={form.poem || ""}
                responsePlaceholder={t("diary.poemPlaceholder")}
                responseEditable
                showResponseWhenEmpty
                onResponseChange={(value) => setField("poem", value)}
              />
            </div>
            <Input
              value={form.poem || ""}
              onChange={(e) => setField("poem", e.target.value)}
              placeholder={t("diary.poemPlaceholder")}
            />
          </div>
        </div>
        <div className="border-t border-border pt-6">
          <AutoTitleField
            value={form.title}
            onChange={(value) => setField("title", value)}
            isAuto={isAutoTitleEnabled}
            onAutoChange={setIsAutoTitleEnabled}
            switchLabel={t("common.autoTitle")}
            inputLabel={t("common.title")}
            required
          />
        </div>
        <div className="pt-6">
          <PublishTimeFooter
            value={form.published_at}
            onChange={(value) => setField("published_at", value)}
            isCustom={isPublishedAtManual}
            onCustomChange={setIsPublishedAtManual}
            label={t("posts.publishedAt")}
            deleteButton={
              !isNew && (
                <Button
                  variant="destructive"
                  type="button"
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
