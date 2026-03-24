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
} from "@/api/generated/admin/admin";
import type { ContentCreate, ContentUpdate } from "@/api/generated/model";
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
    visibility: "public",
    published_at: null,
    category: "",
    view_count: 0,
  });

  useEffect(() => {
    if (post) {
      setForm({
        slug: post.slug,
        title: post.title,
        summary: post.summary || "",
        body: post.body,
        tags: post.tags,
        status: post.status,
        visibility: post.visibility,
        published_at: post.published_at,
        category: post.category || "",
        view_count: post.view_count || 0,
      });
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

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      if (isNew) {
        await createPost({ data: form });
      } else {
        const update: ContentUpdate = { ...form };
        await updatePost({ itemId: id!, data: update });
      }
    } finally {
      setIsSaving(false);
    }
  };

  const [previewOpen, setPreviewOpen] = useState(false);
  const previewWindowRef = useRef<Window | null>(null);

  const frontendUrl =
    import.meta.env.VITE_FRONTEND_URL || "http://localhost:8080";
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
          <div className="flex gap-2">
            {form.status === "published" && !isNew && form.slug ? (
              <Button
                variant="outline"
                onClick={() =>
                  window.open(`${frontendUrl}/posts/${form.slug}`, "_blank")
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
                  if (confirm(t("posts.deleteConfirm")))
                    deletePostMutate({ itemId: id! });
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
            minHeight="400px"
          />
        </div>

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

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>分类</Label>
            <Input
              value={form.category || ""}
              onChange={(e) => setField("category", e.target.value)}
              placeholder="文章分类"
            />
          </div>
          <div className="space-y-2">
            <Label>浏览量</Label>
            <Input
              type="number"
              value={form.view_count || 0}
              onChange={(e) =>
                setField("view_count", parseInt(e.target.value) || 0)
              }
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
