import {
  useListThoughts,
  useBulkDeleteThoughts,
  useBulkStatusThoughts,
  getListThoughtsQueryKey,
} from "@serino/api-client/admin";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import ContentListPage from "@/pages/common/ContentListPage";
import type { ContentListConfig } from "@/pages/common/types";

function useThoughtListConfig(): ContentListConfig {
  const { t } = useI18n();
  return {
    resourceKey: "thoughts",
    titleKey: "thoughts.title",
    descriptionKey: "thoughts.description",
    newButtonLabelKey: "thoughts.newThought",
    newPath: "/thoughts/new",
    editPath: (id) => `/thoughts/${id}`,
    columns: [
      { header: t("common.title"), accessor: "title" },
      { header: t("common.status"), accessor: (row) => <StatusBadge status={row.status} /> },
      { header: t("posts.visibility"), accessor: (row) => <StatusBadge status={row.visibility} /> },
      { header: t("diary.created"), accessor: (row) => formatDate(row.created_at) },
    ],
    useList: useListThoughts as ContentListConfig["useList"],
    useBulkDelete: useBulkDeleteThoughts as ContentListConfig["useBulkDelete"],
    useBulkStatus: useBulkStatusThoughts as ContentListConfig["useBulkStatus"],
    getQueryKey: getListThoughtsQueryKey,
  };
}

export default function ThoughtListPage() {
  const config = useThoughtListConfig();
  return <ContentListPage config={config} />;
}
