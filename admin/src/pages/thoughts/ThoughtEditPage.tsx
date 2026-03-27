import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  useGetThoughts,
  useCreateThoughts,
  useUpdateThoughts,
  useDeleteThoughts,
  getListThoughtsQueryKey,
  getGetThoughtsQueryKey,
} from "@serino/api-client/admin";
import type { ContentCreate, ContentUpdate } from "@serino/api-client/models";
import { PageHeader } from "@/components/PageHeader";
import { ContentEditorHeaderActions } from "@/components/content/ContentEditorHeaderActions";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { ContentCategoryField } from "@/components/content/ContentCategoryField";
import { Label } from "@/components/ui/Label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";

const MOOD_OPTIONS = [
  { value: "☀️" },
  { value: "🌤️" },
  { value: "🌞" },
  { value: "🌈" },
  { value: "🌧️" },
  { value: "🌦️" },
  { value: "🌩️" },
  { value: "🌨️" },
  { value: "❄️" },
  { value: "🍃" },
  { value: "🍂" },
  { value: "🍁" },
  { value: "🌇" },
  { value: "🌙" },
  { value: "🌝" },
  { value: "🌫️" },
  { value: "😶‍🌫️" },
  { value: "🧺" },
  { value: "🪴" },
  { value: "🍵" },
  { value: "📚" },
  { value: "🎨" },
  { value: "💡" },
  { value: "💭" },
  { value: "☕" },
  { value: "✂️" },
  { value: "🧩" },
  { value: "✨" },
  { value: "🫧" },
  { value: "🤍" },
  { value: "😊" },
  { value: "🙂" },
  { value: "😌" },
  { value: "😎" },
  { value: "🤗" },
  { value: "🥰" },
  { value: "😍" },
  { value: "🤔" },
  { value: "🙃" },
  { value: "😴" },
  { value: "😭" },
  { value: "😤" },
  { value: "🤪" },
  { value: "😵" },
  { value: "🫶" },
  { value: "🪄" },
  { value: "🪁" },
  { value: "🛠️" },
] as const;

export default function ThoughtEditPage() {
  const { id } = useParams();
  const isNew = id === "new";
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useI18n();

  const { data: itemData } = useGetThoughts(id!, {
    query: { enabled: !isNew && !!id },
  });
  const item = itemData?.data;

  const [form, setForm] = useState<ContentCreate>({
    slug: "", title: "", summary: "", body: "", tags: [], status: "draft", visibility: "private", published_at: null,
    category: "",
    mood: "",
  });

  useEffect(() => {
    if (item) setForm({ slug: item.slug, title: item.title, summary: item.summary || "", body: item.body, tags: item.tags, status: item.status, visibility: item.visibility, published_at: item.published_at, category: item.category || "", mood: item.mood || "" });
  }, [item]);

  const invalidateQueries = () => {
    queryClient.invalidateQueries({ queryKey: getListThoughtsQueryKey() });
    if (id && !isNew) {
      queryClient.invalidateQueries({ queryKey: getGetThoughtsQueryKey(id) });
    }
  };

  const { mutateAsync: createThought } = useCreateThoughts({
    mutation: {
      onSuccess: (data) => {
        invalidateQueries();
        toast.success(t("common.operationSuccess"));
        navigate(`/thoughts/${data.data.id}`, { replace: true });
      },
      onError: (error: any) => { const msg = error?.response?.data?.detail || t("common.operationFailed"); toast.error(msg); },
    },
  });

  const { mutateAsync: updateThought } = useUpdateThoughts({
    mutation: {
      onSuccess: () => {
        invalidateQueries();
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => { const msg = error?.response?.data?.detail || t("common.operationFailed"); toast.error(msg); },
    },
  });

  const { mutate: deleteThoughtMutate } = useDeleteThoughts({
    mutation: {
      onSuccess: () => {
        invalidateQueries();
        toast.success(t("common.operationSuccess"));
        navigate("/thoughts");
      },
      onError: (error: any) => { const msg = error?.response?.data?.detail || t("common.operationFailed"); toast.error(msg); },
    },
  });

  const [isSaving, setIsSaving] = useState(false);

  const saveThought = async (mode: "draft" | "confirm") => {
    const nextStatus = mode === "draft" ? "draft" : form.visibility === "public" ? "published" : "archived";
    const nextForm = { ...form, status: nextStatus };

    setIsSaving(true);
    try {
      if (isNew) {
        await createThought({ data: nextForm });
      } else {
        await updateThought({ itemId: id!, data: nextForm as ContentUpdate });
      }
      setForm((prev) => ({ ...prev, status: nextStatus }));
    } finally {
      setIsSaving(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    await saveThought("confirm");
  };

  const setField = (k: string, v: any) => setForm((p) => ({ ...p, [k]: v }));

  return (
    <div>
      <PageHeader
        title={isNew ? t("thoughts.newThought") : t("thoughts.editThought")}
        actions={
          <ContentEditorHeaderActions
            visibility={form.visibility}
            isSaving={isSaving}
            onToggleVisibility={() =>
              setField(
                "visibility",
                form.visibility === "public" ? "private" : "public",
              )
            }
            onSaveDraft={() => void saveThought("draft")}
            onConfirm={() => void saveThought("confirm")}
          />
        }
      />
      <form onSubmit={handleSubmit} className="space-y-6 max-w-3xl">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2"><Label>{t("posts.postTitle")}</Label><Input value={form.title} onChange={(e) => setField("title", e.target.value)} required /></div>
          <div className="space-y-2"><Label>{t("posts.slug")}</Label><Input value={form.slug} onChange={(e) => setField("slug", e.target.value)} required /></div>
        </div>
        <div className="space-y-2"><Label>{t("posts.body")}</Label><MarkdownEditor value={form.body} onChange={(v) => setField("body", v)} minHeight="200px" /></div>
        <div className="space-y-2"><Label>{t("posts.tags")}</Label><Input value={form.tags?.join(", ") || ""} onChange={(e) => setField("tags", e.target.value.split(",").map((t) => t.trim()).filter(Boolean))} /></div>
        <ContentCategoryField contentType="thoughts" label={t("contentCategories.fieldLabel")} value={form.category || ""} placeholder={t("contentCategories.thoughtPlaceholder")} onChange={(nextValue) => setField("category", nextValue)} />
        <div className="space-y-2">
          <Label>{t("thoughts.mood")}</Label>
          <Select value={form.mood || undefined} onValueChange={(value) => setField("mood", value === "__empty" ? "" : value)}>
            <SelectTrigger className="h-auto min-h-12 rounded-lg border-input bg-background px-3 py-2">
              <SelectValue placeholder="" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__empty">留空</SelectItem>
              {MOOD_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  <span className="text-lg leading-none">{option.value}</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {!isNew && (
          <div className="pt-6 border-t border-border flex justify-start">
            <Button
              variant="destructive"
              type="button"
              onClick={() => {
                if (confirm(t("thoughts.deleteConfirm"))) {
                  deleteThoughtMutate({ itemId: id! });
                }
              }}
            >
              <Trash2 className="h-4 w-4 mr-2" /> {t("common.delete")}
            </Button>
          </div>
        )}
      </form>
    </div>
  );
}
