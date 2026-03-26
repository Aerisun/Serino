import { useState, useEffect, useMemo, useRef, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  PREVIEW_DATA_MESSAGE,
  isPreviewRequestMessage,
} from "@serino/utils";
import {
  useGetDiary,
  useCreateDiary,
  useUpdateDiary,
  useDeleteDiary,
  getListDiaryQueryKey,
  getGetDiaryQueryKey,
  useSystemInfoApiV1AdminSystemInfoGet,
} from "@serino/api-client/admin";
import type { ContentCreate, ContentUpdate } from "@serino/api-client/models";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { Label } from "@/components/ui/Label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { StatusVisibilityPills } from "@/components/StatusVisibilityPills";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import { Trash2, LogOut, ExternalLink, Eye, Check } from "lucide-react";

const WEATHER_OPTIONS = [
  { value: "sunny", label: "晴" },
  { value: "cloudy", label: "多云" },
  { value: "fog", label: "雾" },
  { value: "haze", label: "霾" },
  { value: "light_rain", label: "小雨" },
  { value: "shower", label: "阵雨" },
  { value: "heavy_rain", label: "大雨" },
  { value: "light_snow", label: "小雪" },
  { value: "heavy_snow", label: "大雪" },
  { value: "sleet", label: "雨夹雪" },
  { value: "stormy", label: "雷阵雨" },
  { value: "windy", label: "大风" },
] as const;

const MOOD_OPTIONS = [
  { value: "☀️", label: "晴朗" },
  { value: "🌤️", label: "和煦" },
  { value: "🌞", label: "明亮" },
  { value: "🌈", label: "彩虹" },
  { value: "🌧️", label: "雨天" },
  { value: "🌦️", label: "微雨" },
  { value: "🌩️", label: "雷鸣" },
  { value: "🌨️", label: "雪意" },
  { value: "❄️", label: "初雪" },
  { value: "🍃", label: "微风" },
  { value: "🍂", label: "秋意" },
  { value: "🍁", label: "枫色" },
  { value: "🌇", label: "黄昏" },
  { value: "🌙", label: "夜晚" },
  { value: "🌝", label: "月明" },
  { value: "🌫️", label: "雾感" },
  { value: "😶‍🌫️", label: "朦胧" },
  { value: "🧺", label: "整理" },
  { value: "🪴", label: "生长" },
  { value: "🍵", label: "热茶" },
  { value: "📚", label: "阅读" },
  { value: "🎨", label: "创作" },
  { value: "💡", label: "灵感" },
  { value: "💭", label: "思考" },
  { value: "☕", label: "咖啡" },
  { value: "✂️", label: "打磨" },
  { value: "🧩", label: "拼合" },
  { value: "✨", label: "轻盈" },
  { value: "🫧", label: "柔和" },
  { value: "🤍", label: "安静" },
  { value: "😊", label: "愉悦" },
  { value: "🙂", label: "平静" },
  { value: "😌", label: "松弛" },
  { value: "😎", label: "自信" },
  { value: "🤗", label: "期待" },
  { value: "🥰", label: "温柔" },
  { value: "😍", label: "喜欢" },
  { value: "🤔", label: "沉思" },
  { value: "🙃", label: "轻松" },
  { value: "😴", label: "困倦" },
  { value: "😭", label: "感动" },
  { value: "😤", label: "坚定" },
  { value: "🤪", label: "跳脱" },
  { value: "😵", label: "发散" },
  { value: "🫶", label: "温暖" },
  { value: "🪄", label: "魔法" },
  { value: "🪁", label: "自在" },
  { value: "🛠️", label: "调试" },
] as const;

export default function DiaryEditPage() {
  const { id } = useParams();
  const isNew = id === "new";
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useI18n();

  const { data: itemData } = useGetDiary(id!, {
    query: { enabled: !isNew && !!id },
  });
  const item = itemData?.data;

  const [form, setForm] = useState<ContentCreate>({
    slug: "",
    title: "",
    summary: "",
    body: "",
    tags: [],
    status: "draft",
    visibility: "private",
    published_at: null,
    mood: "",
    weather: "",
    poem: "",
  });

  useEffect(() => {
    if (item)
      setForm({
        slug: item.slug,
        title: item.title,
        summary: item.summary || "",
        body: item.body,
        tags: item.tags,
        status: item.status,
        visibility: item.visibility,
        published_at: item.published_at,
        mood: item.mood || "",
        weather: item.weather || "",
        poem: item.poem || "",
      });
  }, [item]);

  const invalidateQueries = () => {
    queryClient.invalidateQueries({ queryKey: getListDiaryQueryKey() });
    if (id && !isNew) {
      queryClient.invalidateQueries({ queryKey: getGetDiaryQueryKey(id) });
    }
  };

  const { mutateAsync: createDiary } = useCreateDiary({
    mutation: {
      onSuccess: (data) => {
        invalidateQueries();
        toast.success(t("common.operationSuccess"));
        navigate(`/diary/${data.data.id}`, { replace: true });
      },
      onError: (error: any) => {
        const msg = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  const { mutateAsync: updateDiary } = useUpdateDiary({
    mutation: {
      onSuccess: () => {
        invalidateQueries();
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        const msg = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  const { mutate: deleteDiaryMutate } = useDeleteDiary({
    mutation: {
      onSuccess: () => {
        invalidateQueries();
        toast.success(t("common.operationSuccess"));
        navigate("/diary");
      },
      onError: (error: any) => {
        const msg = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  const [isSaving, setIsSaving] = useState(false);

  const saveDiary = async (mode: "draft" | "confirm") => {
    const nextStatus = mode === "draft" ? "draft" : form.visibility === "public" ? "published" : "archived";
    const nextForm = { ...form, status: nextStatus };

    setIsSaving(true);
    try {
      if (isNew) {
        await createDiary({ data: nextForm });
      } else {
        await updateDiary({ itemId: id!, data: nextForm as ContentUpdate });
      }
      setForm((prev) => ({ ...prev, status: nextStatus }));
    } finally {
      setIsSaving(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    await saveDiary("confirm");
  };

  const [previewOpen, setPreviewOpen] = useState(false);
  const previewWindowRef = useRef<Window | null>(null);
  const { data: systemInfo } = useSystemInfoApiV1AdminSystemInfoGet();
  const frontendUrl = (systemInfo?.site_url || "http://localhost:8080").replace(
    /\/+$/,
    "",
  );
  const frontendOrigin = new URL(frontendUrl, window.location.origin).origin;
  const storageKey = `aerisun-preview-${id ?? "new"}`;
  const previewPayload = useMemo(
    () => ({ type: "diary" as const, ...form }),
    [form],
  );

  useEffect(() => {
    if (!previewOpen) return;

    const previewWindow = previewWindowRef.current;
    if (!previewWindow || previewWindow.closed) {
      setPreviewOpen(false);
      return;
    }

    localStorage.setItem(storageKey, JSON.stringify(previewPayload));
    previewWindow.postMessage(
      {
        type: PREVIEW_DATA_MESSAGE,
        storageKey,
        payload: previewPayload,
      },
      frontendOrigin,
    );
  }, [form, frontendOrigin, previewOpen, previewPayload, storageKey]);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== frontendOrigin) return;
      if (!isPreviewRequestMessage(event.data)) return;
      if (event.data.storageKey !== storageKey) return;
      if (!event.source) return;

      localStorage.setItem(storageKey, JSON.stringify(previewPayload));
      (event.source as WindowProxy).postMessage(
        {
          type: PREVIEW_DATA_MESSAGE,
          storageKey,
          payload: previewPayload,
        },
        event.origin,
      );
    };

    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [frontendOrigin, previewPayload, storageKey]);

  const openPreview = () => {
    const existingWindow = previewWindowRef.current;
    if (existingWindow && !existingWindow.closed) {
      localStorage.setItem(storageKey, JSON.stringify(previewPayload));
      existingWindow.postMessage(
        {
          type: PREVIEW_DATA_MESSAGE,
          storageKey,
          payload: previewPayload,
        },
        frontendOrigin,
      );
      existingWindow.focus();
      setPreviewOpen(true);
      return;
    }

    localStorage.setItem(storageKey, JSON.stringify(previewPayload));
    const previewWindow = window.open(
      `${frontendUrl}/preview?storageKey=${encodeURIComponent(storageKey)}`,
      "_blank",
    );
    previewWindowRef.current = previewWindow;
    setPreviewOpen(Boolean(previewWindow));

    if (previewWindow) {
      window.setTimeout(() => {
        if (previewWindow.closed) {
          setPreviewOpen(false);
          return;
        }

        previewWindow.postMessage(
          {
            type: PREVIEW_DATA_MESSAGE,
            storageKey,
            payload: previewPayload,
          },
          frontendOrigin,
        );
      }, 250);
    }
  };
  const setField = (k: string, v: any) =>
    setForm((p) => ({ ...p, [k]: v }));

  return (
    <div>
      <PageHeader
        title={isNew ? t("diary.newEntry") : t("diary.editEntry")}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <StatusVisibilityPills visibility={form.visibility} onToggleVisibility={() => setField("visibility", form.visibility === "public" ? "private" : "public")} />
            {form.status === "published" && form.visibility === "public" && !isNew && form.slug ? (
              <Button
                variant="outline"
                className="preview-glow-button"
                onClick={() =>
                  window.open(`${frontendUrl}/diary/${form.slug}`, "_blank")
                }
              >
                <ExternalLink className="h-4 w-4 mr-2" /> {t("common.preview")}
              </Button>
            ) : (
              <Button
                variant="outline"
                className="preview-glow-button"
                onClick={openPreview}
                disabled={!form.body}
              >
                <Eye className="h-4 w-4 mr-2" /> {t("common.preview")}
              </Button>
            )}
            <Button variant="secondary" className="bg-slate-100 text-slate-900 border-slate-200 shadow-none backdrop-blur-0 ring-0 hover:bg-slate-200 hover:text-slate-950 dark:bg-slate-800/80 dark:text-slate-100 dark:border-slate-700 dark:hover:bg-slate-800" onClick={() => void saveDiary("draft")} disabled={isSaving}>
              <LogOut className="h-4 w-4 mr-2" /> {" "}
              {isSaving ? t("common.saving") : t("common.saveDraft")}
            </Button>
            <Button variant="secondary" className="bg-emerald-600 text-white border-emerald-600 hover:bg-emerald-700 hover:text-white dark:bg-emerald-500 dark:text-white dark:hover:bg-emerald-400" onClick={() => void saveDiary("confirm")} disabled={isSaving}>
              <Check className="h-4 w-4 mr-2" /> {" "}
              {isSaving ? t("common.saving") : t("common.confirm")}
            </Button>
          </div>
        }
      />
      <form onSubmit={handleSubmit} className="space-y-6 max-w-3xl">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>{t("posts.postTitle")}</Label>
            <Input
              value={form.title}
              onChange={(e) => setField("title", e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label>{t("posts.slug")}</Label>
            <Input
              value={form.slug}
              onChange={(e) => setField("slug", e.target.value)}
              required
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label>{t("posts.summary")}</Label>
          <Textarea
            value={form.summary || ""}
            onChange={(e) => setField("summary", e.target.value)}
            rows={2}
          />
        </div>
        <div className="space-y-2">
          <Label>{t("posts.body")}</Label>
          <MarkdownEditor
            value={form.body}
            onChange={(v) => setField("body", v)}
            minHeight="350px"
          />
        </div>
        <div className="space-y-2">
          <Label>{t("posts.tags")}</Label>
          <Input
            value={form.tags?.join(", ") || ""}
            onChange={(e) =>
              setField(
                "tags",
                e.target.value
                  .split(",")
                  .map((t) => t.trim())
                  .filter(Boolean),
              )
            }
          />
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-2">
            <Label>{t("diary.mood")}</Label>
            <Select
              value={form.mood || undefined}
              onValueChange={(value) => setField("mood", value === "__empty" ? "" : value)}
            >
              <SelectTrigger className="h-auto min-h-12 rounded-lg border-input bg-background px-3 py-2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="max-w-[320px]">
                <SelectItem value="__empty">留空</SelectItem>
                {MOOD_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    <span className="text-lg leading-none">{option.value}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>{t("diary.weather")}</Label>
            <Select
              value={form.weather || undefined}
              onValueChange={(value) => setField("weather", value === "__empty" ? "" : value)}
            >
              <SelectTrigger className="h-auto min-h-10 rounded-md border-input bg-background px-3 py-2 text-sm">
                <SelectValue placeholder="" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__empty">留空</SelectItem>
                {WEATHER_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>{t("diary.poem")}</Label>
            <Input
              value={form.poem || ""}
              onChange={(e) => setField("poem", e.target.value)}
              placeholder={t("diary.poemPlaceholder")}
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label>{t("posts.publishedAt")}</Label>
          <Input
            type="datetime-local"
            value={
              form.published_at
                ? new Date(form.published_at).toISOString().slice(0, 16)
                : ""
            }
            onChange={(e) =>
              setField(
                "published_at",
                e.target.value
                  ? new Date(e.target.value).toISOString()
                  : null,
              )
            }
          />
        </div>

        {!isNew && (
          <div className="pt-6 border-t border-border flex justify-start">
            <Button
              variant="destructive"
              type="button"
              onClick={() => {
                if (confirm(t("diary.deleteConfirm"))) {
                  deleteDiaryMutate({ itemId: id! });
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
