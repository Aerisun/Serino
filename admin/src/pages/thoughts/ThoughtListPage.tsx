import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useResourceList } from "@/hooks/useResource";
import { listThoughts, createThought, updateThought, deleteThought } from "@/api/endpoints/thoughts";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Plus } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import type { ContentItem } from "@/types/models";

export default function ThoughtListPage() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [page, setPage] = useState(1);

  const { items, total, pageSize, isLoading } = useResourceList(
    { queryKey: "thoughts", listFn: listThoughts, createFn: createThought, updateFn: updateThought, deleteFn: deleteThought },
    { page }
  );

  return (
    <div>
      <PageHeader
        title={t("thoughts.title")}
        description={t("thoughts.description")}
        actions={<Button onClick={() => navigate("/thoughts/new")}><Plus className="h-4 w-4 mr-2" /> {t("thoughts.newThought")}</Button>}
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
          onRowClick={(row) => navigate(`/thoughts/${row.id}`)}
        />
      </div>
    </div>
  );
}
