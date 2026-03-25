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
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/Select";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import { Trash2, Save, ExternalLink, Eye } from "lucide-react";

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
    visibility: "public",
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

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      if (isNew) {
        await createDiary({ data: form });
      } else {
        await updateDiary({ itemId: id!, data: form as ContentUpdate });
      }
    } finally {
      setIsSaving(false);
    }
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
  const setField = (k: string, v: any) => setForm((p) => ({ ...p, [k]: v }));

  return (
    <div>
      <PageHeader
        title={isNew ? t("diary.newEntry") : t("diary.editEntry")}
        actions={
          <div className="flex gap-2">
            {form.status === "published" && !isNew && form.slug ? (
              <Button
                variant="outline"
                onClick={() =>
                  window.open(`${frontendUrl}/diary/${form.slug}`, "_blank")
                }
              >
                <ExternalLink className="h-4 w-4 mr-2" /> {t("common.preview")}
              </Button>
            ) : (
              <Button
                variant="outline"
                onClick={openPreview}
                disabled={!form.body}
              >
                <Eye className="h-4 w-4 mr-2" /> {t("common.preview")}
              </Button>
            )}
            {!isNew && (
              <Button
                variant="destructive"
                onClick={() => {
                  if (confirm(t("diary.deleteConfirm"))) deleteDiaryMutate({ itemId: id! });
                }}
              >
                <Trash2 className="h-4 w-4 mr-2" /> {t("common.delete")}
              </Button>
            )}
            <Button onClick={handleSubmit} disabled={isSaving}>
              <Save className="h-4 w-4 mr-2" />{" "}
              {isSaving ? t("common.saving") : t("common.save")}
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
            <Input
              value={form.mood || ""}
              onChange={(e) => setField("mood", e.target.value)}
              placeholder={t("diary.moodPlaceholder")}
            />
          </div>
          <div className="space-y-2">
            <Label>{t("diary.weather")}</Label>
            <Input
              value={form.weather || ""}
              onChange={(e) => setField("weather", e.target.value)}
              placeholder={t("diary.weatherPlaceholder")}
            />
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
        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-2">
            <Label>{t("posts.status")}</Label>
            <Select
              value={form.status}
              onValueChange={(v) => setField("status", v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="draft">{t("posts.draft")}</SelectItem>
                <SelectItem value="published">
                  {t("posts.published")}
                </SelectItem>
                <SelectItem value="archived">{t("posts.archived")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>{t("posts.visibility")}</Label>
            <Select
              value={form.visibility}
              onValueChange={(v) => setField("visibility", v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
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
        </div>
      </form>
    </div>
  );
}
