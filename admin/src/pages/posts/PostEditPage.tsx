import {
  useGetPosts,
  useCreatePosts,
  useUpdatePosts,
  useDeletePosts,
  useGetProfileApiV1AdminSiteConfigProfileGet,
  getListPostsQueryKey,
  getGetPostsQueryKey,
} from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { ContentEditorHeaderActions } from "@/components/content/ContentEditorHeaderActions";
import { ContentCategoryField } from "@/components/content/ContentCategoryField";
import { PublishTimeFooter } from "@/components/content/PublishTimeFooter";
import { Label } from "@/components/ui/Label";
import { NativeSelect } from "@/components/ui/NativeSelect";
import { Trash2, Eye } from "lucide-react";
import { useContentEditor, buildServerToForm } from "@/hooks/useContentEditor";

const editorConfig = {
  contentType: "posts" as const,
  hooks: {
    useGet: useGetPosts,
    useCreate: useCreatePosts,
    useUpdate: useUpdatePosts,
    useDelete: useDeletePosts,
    getListQueryKey: getListPostsQueryKey,
    getDetailQueryKey: getGetPostsQueryKey,
  },
  listRoute: "/posts",
  defaultForm: {
    slug: "", title: "", summary: "", body: "", tags: [],
    visibility: "private", published_at: null,
    category: "", kind: "manuscript", exclude_from_rss: false, requires_approval: false,
  },
  serverToForm: buildServerToForm((item) => ({
    category: item.category || "",
    kind: item.kind === "note" ? "note" : "manuscript",
    exclude_from_rss: Boolean(item.exclude_from_rss),
    requires_approval: Boolean(item.requires_approval),
  })),
  i18nKeys: {
    newTitle: "posts.newPost",
    editTitle: "posts.editPost",
    deleteConfirm: "posts.deleteConfirm",
  },
};

export default function PostEditPage() {
  const editor = useContentEditor(editorConfig);
  const { form, setField, isSaving, isPublishedAtManual, setIsPublishedAtManual, isNew, t } = editor;
  const { data: profileRaw } = useGetProfileApiV1AdminSiteConfigProfileGet();
  const excludeFromRss = Boolean((form as { exclude_from_rss?: boolean }).exclude_from_rss);
  const requiresApproval = Boolean((form as { requires_approval?: boolean }).requires_approval);
  const postKind = (form as { kind?: string }).kind === "note" ? "note" : "manuscript";
  const featureFlags = (profileRaw?.data as { feature_flags?: Record<string, unknown> } | undefined)
    ?.feature_flags;
  const postApprovalEnabled = featureFlags?.post_access_approval_enabled !== false;
  const showPublicPostSettings = form.visibility === "public";

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
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="post-title">{t("posts.postTitle")}</Label>
            <Input
              id="post-title"
              value={form.title}
              onChange={(e) => setField("title", e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="post-slug">{t("posts.slug")}</Label>
            <Input
              id="post-slug"
              value={form.slug || ""}
              onChange={(e) => setField("slug", e.target.value)}
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label>{t("posts.summary")}</Label>
          <Textarea value={form.summary || ""} onChange={(e) => setField("summary", e.target.value)} rows={2} />
        </div>

        <div className="space-y-2">
          <Label>{t("posts.body")}</Label>
          <MarkdownEditor
            assetCategory="post"
            value={form.body}
            onChange={(v) => setField("body", v)}
            minHeight="400px"
            mobileFullscreen
          />
        </div>

        <div data-post-metadata-fields className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <Label>{t("posts.tagsHint")}</Label>
            <Input
              value={form.tags?.join(", ") || ""}
              onChange={(e) => setField("tags", e.target.value.split(",").map((t) => t.trim()).filter(Boolean))}
            />
          </div>
          <ContentCategoryField
            contentType={postKind === "note" ? "notes" : "posts"}
            label={t("contentCategories.fieldLabel")}
            value={form.category || ""}
            placeholder={t(postKind === "note" ? "contentCategories.notePlaceholder" : "contentCategories.postPlaceholder")}
            onChange={(nextValue) => setField("category", nextValue)}
          />
          <div className="space-y-2">
            <Label htmlFor="post-kind">{t("posts.kind")}</Label>
            <NativeSelect
              id="post-kind"
              aria-label={t("posts.kind")}
              value={postKind}
              onChange={(event) => {
                const nextKind = event.target.value === "note" ? "note" : "manuscript";
                if (nextKind !== postKind) {
                  setField("category", "");
                }
                setField("kind", nextKind);
              }}
              className="h-11 rounded-xl border-border/50 bg-background/70"
            >
              <option value="manuscript">{t("posts.kindManuscript")}</option>
              <option value="note">{t("posts.kindNote")}</option>
            </NativeSelect>
          </div>
        </div>

        <div className="pt-6 border-t border-border">
          <PublishTimeFooter
            value={form.published_at}
            onChange={(value) => setField("published_at", value)}
            isCustom={isPublishedAtManual}
            onCustomChange={setIsPublishedAtManual}
            label={t("posts.publishedAt")}
            rssExclusion={
              showPublicPostSettings
                ? {
                    checked: excludeFromRss,
                    onCheckedChange: (checked) => setField("exclude_from_rss", checked),
                    label: "不展示 RSS",
                    ariaLabel: "不展示 RSS",
                    helpDescription: "开启后，公开文章仍可在网站中访问，但不会出现在 RSS 订阅中。",
                  }
                : undefined
            }
            approvalRequirement={
              showPublicPostSettings && postApprovalEnabled
                ? {
                    checked: requiresApproval,
                    onCheckedChange: (checked) => setField("requires_approval", checked),
                    label: "查看需要审批",
                    ariaLabel: "查看需要审批",
                    helpDescription:
                      "开启后，访客需先登录并提交申请，经审核通过后才能查看这篇公开文章的完整内容。",
                  }
                : undefined
            }
            deleteButton={
              !isNew && (
                <Button
                  variant="destructive" type="button"
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
