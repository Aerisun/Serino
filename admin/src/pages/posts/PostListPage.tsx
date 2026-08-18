import {
  useListPosts,
  useBulkDeletePosts,
  useBulkVisibilityPosts,
  getListPostsQueryKey,
} from "@serino/api-client/admin";
import type { ContentAdminRead } from "@serino/api-client/models";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import ContentListPage from "@/pages/common/ContentListPage";
import type { ContentListConfig } from "@/pages/common/types";

function postVisibilityBadge(row: ContentAdminRead) {
  const visibility = String(row.visibility || "");
  const excludeFromRss = Boolean(
    (row as { exclude_from_rss?: unknown }).exclude_from_rss,
  );
  const requiresApproval = Boolean(
    (row as { requires_approval?: unknown }).requires_approval,
  );
  const status =
    visibility === "public" && requiresApproval
      ? excludeFromRss
        ? "approvalNoRss"
        : "approval"
      : visibility === "public" && excludeFromRss
        ? "publicNoRss"
        : visibility;

  return <StatusBadge status={status} />;
}

function usePostListConfig(): ContentListConfig {
  const { t } = useI18n();
  return {
    resourceKey: "posts",
    titleKey: "posts.title",
    descriptionKey: "posts.description",
    newButtonLabelKey: "posts.newPost",
    newPath: "/posts/new",
    editPath: (id) => `/posts/${id}`,
    columns: [
      { header: t("posts.postTitle"), accessor: "title" },
      {
        header: t("posts.kind"),
        accessor: (row) => {
          const isNote = (row as { kind?: string }).kind === "note";
          return (
            <span className={isNote ? "text-pink-400 dark:text-pink-300" : "text-cyan-600 dark:text-cyan-300"}>
              {isNote ? t("posts.kindNote") : t("posts.kindManuscript")}
            </span>
          );
        },
      },
      {
        header: t("posts.visibility"),
        accessor: postVisibilityBadge,
        className: "text-center",
      },
      {
        header: t("posts.publishedAt"),
        accessor: (row) => formatDate(row.published_at || row.updated_at),
      },
      {
        header: t("diary.created"),
        accessor: (row) => formatDate(row.created_at),
      },
    ],
    useList: useListPosts as ContentListConfig["useList"],
    useBulkDelete: useBulkDeletePosts as ContentListConfig["useBulkDelete"],
    useBulkVisibility: useBulkVisibilityPosts as ContentListConfig["useBulkVisibility"],
    getQueryKey: getListPostsQueryKey,
    renderMobileVisibility: postVisibilityBadge,
  };
}

export default function PostListPage() {
  const config = usePostListConfig();
  return <ContentListPage config={config} />;
}
