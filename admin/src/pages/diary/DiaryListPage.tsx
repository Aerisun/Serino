import {
  useListDiary,
  useBulkDeleteDiary,
  useBulkVisibilityDiary,
  getListDiaryQueryKey,
} from "@serino/api-client/admin";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import ContentListPage from "@/pages/common/ContentListPage";
import type { ContentListConfig } from "@/pages/common/types";

function useDiaryListConfig(): ContentListConfig {
  const { t } = useI18n();
  return {
    resourceKey: "diary",
    titleKey: "diary.title",
    descriptionKey: "diary.description",
    newButtonLabelKey: "diary.newEntry",
    newPath: "/diary/new",
    editPath: (id) => `/diary/${id}`,
    columns: [
      { header: t("common.title"), accessor: "title" },
      {
        header: t("posts.visibility"),
        accessor: (row) => <StatusBadge status={String(row.visibility || "")} />,
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
    useList: useListDiary as ContentListConfig["useList"],
    useBulkDelete: useBulkDeleteDiary as ContentListConfig["useBulkDelete"],
    useBulkVisibility: useBulkVisibilityDiary as ContentListConfig["useBulkVisibility"],
    getQueryKey: getListDiaryQueryKey,
  };
}

export default function DiaryListPage() {
  const config = useDiaryListConfig();
  return <ContentListPage config={config} />;
}
