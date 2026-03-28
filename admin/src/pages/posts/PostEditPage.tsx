import { useState, useEffect, useMemo, useRef, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  PREVIEW_DATA_MESSAGE,
  isPreviewRequestMessage,
} from "@serino/utils";
import {
  useGetPosts,
  useCreatePosts,
  useUpdatePosts,
  useDeletePosts,
  getListPostsQueryKey,
  getGetPostsQueryKey,
  useSystemInfoApiV1AdminSystemInfoGet,
} from "@serino/api-client/admin";
import type { ContentCreate, ContentUpdate } from "@serino/api-client/models";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { ContentEditorHeaderActions } from "@/components/content/ContentEditorHeaderActions";
import { ContentCategoryField } from "@/components/content/ContentCategoryField";
import { Label } from "@/components/ui/Label";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import { Trash2, ExternalLink, Eye } from "lucide-react";

export default function PostEditPage() {
  const { id } = useParams();
  const isNew = id === "new";
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useI18n();

  const { data: postData } = useGetPosts(id!, {
    query: { enabled: !isNew && !!id },
  });
  const post = postData?.data;

  const [form, setForm] = useState<ContentCreate>({
    slug: "",
    title: "",
    summary: "",
    body: "",
    tags: [],
    status: "draft",
    visibility: "private",
    published_at: null,
    category: "",
  });
  const [isPublishedAtManual, setIsPublishedAtManual] = useState(false);

  useEffect(() => {
    if (post) {
      const effectivePublishedAt = post.published_at || post.updated_at || null;
      const hasManualPublishedAt =
        Boolean(post.published_at) &&
        (!post.updated_at ||
          Math.abs(new Date(post.published_at!).getTime() - new Date(post.updated_at).getTime()) > 60_000);
      setForm({
        slug: post.slug,
        title: post.title,
        summary: post.summary || "",
        body: post.body,
        tags: post.tags,
        status: post.status,
        visibility: post.visibility,
        published_at: effectivePublishedAt,
        category: post.category || "",
      });
      setIsPublishedAtManual(hasManualPublishedAt);
    }
  }, [post]);

  const invalidateQueries = () => {
    queryClient.invalidateQueries({ queryKey: getListPostsQueryKey() });
    if (id && !isNew) {
      queryClient.invalidateQueries({ queryKey: getGetPostsQueryKey(id) });
    }
  };

  const { mutateAsync: createPost } = useCreatePosts({
    mutation: {
      onSuccess: (data) => {
        invalidateQueries();
        toast.success(t("common.operationSuccess"));
        navigate(`/posts/${data.data.id}`, { replace: true });
      },
      onError: (error: any) => {
        const msg = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  const { mutateAsync: updatePost } = useUpdatePosts({
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

  const { mutate: deletePostMutate } = useDeletePosts({
    mutation: {
      onSuccess: () => {
        invalidateQueries();
        toast.success(t("common.operationSuccess"));
        navigate("/posts");
      },
      onError: (error: any) => {
        const msg = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  const [isSaving, setIsSaving] = useState(false);

  const savePost = async (mode: "draft" | "confirm") => {
    const nextStatus = mode === "draft" ? "draft" : form.visibility === "public" ? "published" : "archived";
    const nextPublishedAt =
      isPublishedAtManual && form.published_at
        ? form.published_at
        : new Date().toISOString();
    const nextForm = { ...form, status: nextStatus, published_at: nextPublishedAt };

    setIsSaving(true);
    try {
      if (isNew) {
        await createPost({ data: nextForm });
      } else {
        const update: ContentUpdate = { ...nextForm };
        await updatePost({ itemId: id!, data: update });
      }
      setForm((prev) => ({ ...prev, status: nextStatus, published_at: nextPublishedAt }));
    } finally {
      setIsSaving(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    await savePost("confirm");
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
    () => ({ type: "posts" as const, ...form }),
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

  const setField = (key: string, value: any) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  return (
    <div>
      <PageHeader
        title={isNew ? t("posts.newPost") : t("posts.editPost")}
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
            onSaveDraft={() => void savePost("draft")}
            onConfirm={() => void savePost("confirm")}
            extraActions={
              form.status === "published" && form.visibility === "public" && !isNew && form.slug ? (
                <Button
                  type="button"
                  variant="outline"
                  className="preview-glow-button"
                  onClick={() =>
                    window.open(`${frontendUrl}/posts/${form.slug}`, "_blank")
                  }
                >
                  <ExternalLink className="h-4 w-4 mr-2" /> {t("common.preview")}
                </Button>
              ) : (
                <Button
                  type="button"
                  variant="outline"
                  className="preview-glow-button"
                  onClick={openPreview}
                  disabled={!form.body}
                >
                  <Eye className="h-4 w-4 mr-2" /> {t("common.preview")}
                </Button>
              )
            }
          />
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
            minHeight="400px"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>{t("posts.tagsHint")}</Label>
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
          <ContentCategoryField
            contentType="posts"
            label={t("contentCategories.fieldLabel")}
            value={form.category || ""}
            placeholder={t("contentCategories.postPlaceholder")}
            onChange={(nextValue) => setField("category", nextValue)}
          />
        </div>

        <div className="pt-6 border-t border-border">
          <div className="rounded-2xl border border-border/60 bg-muted/20 px-4 py-4 sm:px-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
              {!isNew && (
                <Button
                  variant="destructive"
                  type="button"
                  className="h-11 rounded-xl px-5 shadow-sm shadow-destructive/25"
                  onClick={() => {
                    if (confirm(t("posts.deleteConfirm"))) {
                      deletePostMutate({ itemId: id! });
                    }
                  }}
                >
                  <Trash2 className="h-4 w-4 mr-2" /> {t("common.delete")}
                </Button>
              )}
              <div className="space-y-2 w-full sm:w-80 sm:ml-auto">
                <Label className="text-sm font-medium">{t("posts.publishedAt")}</Label>
                <Input
                  className="h-11 rounded-xl border-border/60 bg-background/90 shadow-sm"
                  type="datetime-local"
                  value={
                    form.published_at
                      ? new Date(form.published_at).toISOString().slice(0, 16)
                      : ""
                  }
                  onChange={(e) => {
                    const nextPublishedAt = e.target.value
                      ? new Date(e.target.value).toISOString()
                      : null;
                    setIsPublishedAtManual(Boolean(nextPublishedAt));
                    setField("published_at", nextPublishedAt);
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}
