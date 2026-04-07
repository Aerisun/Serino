import {
  useListExcerpts,
  useBulkDeleteExcerpts,
  useBulkStatusExcerpts,
  getListExcerptsQueryKey,
} from "@serino/api-client/admin";
import type { ContentAdminRead } from "@serino/api-client/models";
import { StatusBadge } from "@/components/StatusBadge";
import { getBodySnippet } from "@/lib/content-snippets";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import ContentListPage from "@/pages/common/ContentListPage";
import type { ContentListConfig } from "@/pages/common/types";

function useExcerptListConfig(): ContentListConfig {
  const { t } = useI18n();
  return {
    resourceKey: "excerpts",
    titleKey: "excerpts.title",
    descriptionKey: "excerpts.description",
    newButtonLabelKey: "excerpts.newExcerpt",
    newPath: "/excerpts/new",
    editPath: (id) => `/excerpts/${id}`,
    columns: [
      {
        header: t("common.snippet"),
        accessor: (row: ContentAdminRead) => {
          const snippet = getBodySnippet(row.body, row.title || row.id);
          return (
            <div className="line-clamp-3 max-w-xl text-sm leading-6 text-foreground/90" title={snippet}>
              {snippet}
            </div>
          );
        },
      },
      { header: t("common.status"), accessor: (row) => <StatusBadge status={row.status} /> },
      { header: t("posts.visibility"), accessor: (row) => <StatusBadge status={row.visibility} /> },
      { header: t("posts.publishedAt"), accessor: (row) => formatDate(row.published_at || row.updated_at) },
      { header: t("diary.created"), accessor: (row) => formatDate(row.created_at) },
    ],
    useList: useListExcerpts as ContentListConfig["useList"],
    useBulkDelete: useBulkDeleteExcerpts as ContentListConfig["useBulkDelete"],
    useBulkStatus: useBulkStatusExcerpts as ContentListConfig["useBulkStatus"],
    getQueryKey: getListExcerptsQueryKey,
  };
}

export default function ExcerptListPage() {
  const config = useExcerptListConfig();
  return <ContentListPage config={config} />;
}
