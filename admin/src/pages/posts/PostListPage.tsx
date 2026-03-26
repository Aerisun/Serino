import {
  useListPosts,
  useBulkDeletePosts,
  useBulkStatusPosts,
  getListPostsQueryKey,
} from "@serino/api-client/admin";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import ContentListPage from "@/pages/common/ContentListPage";
import type { ContentListConfig } from "@/pages/common/types";

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
      { header: t("posts.slug"), accessor: "slug" },
      {
        header: t("posts.status"),
        accessor: (row) => <StatusBadge status={row.status} />,
      },
      {
        header: t("posts.visibility"),
        accessor: (row) => <StatusBadge status={row.visibility} />,
      },
      {
        header: t("common.recordedAt"),
        accessor: (row) => formatDate(row.published_at),
      },
      {
        header: t("common.lastUpdated"),
        accessor: (row) => formatDate(row.updated_at),
      },
    ],
    useList: useListPosts as ContentListConfig["useList"],
    useBulkDelete: useBulkDeletePosts as ContentListConfig["useBulkDelete"],
    useBulkStatus: useBulkStatusPosts as ContentListConfig["useBulkStatus"],
    getQueryKey: getListPostsQueryKey,
  };
}

export default function PostListPage() {
  const config = usePostListConfig();
  return <ContentListPage config={config} />;
}
