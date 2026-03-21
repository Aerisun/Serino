import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useResourceList } from "@/hooks/useResource";
import { listExcerpts, createExcerpt, updateExcerpt, deleteExcerpt } from "@/api/endpoints/excerpts";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Plus } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import type { ContentItem } from "@/types/models";

export default function ExcerptListPage() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [page, setPage] = useState(1);

  const { items, total, pageSize, isLoading } = useResourceList(
    { queryKey: "excerpts", listFn: listExcerpts, createFn: createExcerpt, updateFn: updateExcerpt, deleteFn: deleteExcerpt },
    { page }
  );

  return (
    <div>
      <PageHeader
        title={t("excerpts.title")}
        description={t("excerpts.description")}
        actions={<Button onClick={() => navigate("/excerpts/new")}><Plus className="h-4 w-4 mr-2" /> {t("excerpts.newExcerpt")}</Button>}
      />
      <div className="border rounded-lg">
        <DataTable<ContentItem>
          columns={[
            { header: t("common.title"), accessor: "title" },
            { header: t("common.status"), accessor: (row) => <StatusBadge status={row.status} /> },
            { header: t("posts.visibility"), accessor: (row) => <StatusBadge status={row.visibility} /> },
            { header: t("diary.created"), accessor: (row) => formatDate(row.created_at) },
          ]}
          data={items}
          total={total}
          page={page}
          pageSize={pageSize}
          onPageChange={setPage}
          isLoading={isLoading}
          onRowClick={(row) => navigate(`/excerpts/${row.id}`)}
        />
      </div>
    </div>
  );
}
