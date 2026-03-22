import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useResourceList } from "@/hooks/useResource";
import { listThoughts, createThought, updateThought, deleteThought, bulkDeleteThoughts, bulkStatusThoughts } from "@/api/endpoints/thoughts";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { BulkActionBar } from "@/components/BulkActionBar";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { Plus } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import type { ContentItem } from "@/types/models";

const SORT_OPTIONS = [
  { value: "created_at:desc", labelKey: "common.sortNewest" },
  { value: "created_at:asc", labelKey: "common.sortOldest" },
  { value: "updated_at:desc", labelKey: "common.sortUpdated" },
  { value: "title:asc", labelKey: "common.sortTitle" },
];

export default function ThoughtListPage() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  const [searchDebounced, setSearchDebounced] = useState("");
  const [sort, setSort] = useState("created_at:desc");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);

  const [sort_by, sort_order] = sort.split(":");

  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleSearch = (value: string) => {
    setSearch(value);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => { setSearchDebounced(value); setPage(1); }, 300);
  };

  const { items, total, pageSize, isLoading, bulkDelete, bulkStatus, isBulkDeleting } = useResourceList(
    {
      queryKey: "thoughts",
      listFn: listThoughts,
      createFn: createThought,
      updateFn: updateThought,
      deleteFn: deleteThought,
      bulkDeleteFn: bulkDeleteThoughts,
      bulkStatusFn: bulkStatusThoughts,
    },
    { page, status: statusFilter || undefined, search: searchDebounced || undefined, sort_by, sort_order }
  );

  const handleBulkDelete = async () => {
    try {
      const res = await bulkDelete(Array.from(selectedIds));
      toast.success(t("common.operationSuccess") + ` (${res.affected})`);
      setSelectedIds(new Set());
      setBulkDeleteOpen(false);
    } catch { toast.error(t("common.operationFailed")); }
  };

  const handleBulkStatus = async (status: string) => {
    try {
      const res = await bulkStatus(Array.from(selectedIds), status);
      toast.success(t("common.operationSuccess") + ` (${res.affected})`);
      setSelectedIds(new Set());
    } catch { toast.error(t("common.operationFailed")); }
  };

  return (
    <div>
      <PageHeader
        title={t("thoughts.title")}
        description={t("thoughts.description")}
        actions={<Button onClick={() => navigate("/thoughts/new")}><Plus className="h-4 w-4 mr-2" /> {t("thoughts.newThought")}</Button>}
      />

      <div className="flex items-center gap-4 mb-4">
        <Tabs value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
          <TabsList>
            <TabsTrigger value="">{t("common.all")}</TabsTrigger>
            <TabsTrigger value="draft">{t("posts.draft")}</TabsTrigger>
            <TabsTrigger value="published">{t("posts.published")}</TabsTrigger>
            <TabsTrigger value="archived">{t("posts.archived")}</TabsTrigger>
          </TabsList>
        </Tabs>
        <Input placeholder={t("common.searchPlaceholder")} className="max-w-xs" value={search} onChange={(e) => handleSearch(e.target.value)} />
        <select className="h-9 rounded-md border border-input bg-transparent px-3 text-sm" value={sort} onChange={(e) => { setSort(e.target.value); setPage(1); }}>
          {SORT_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{t(opt.labelKey)}</option>)}
        </select>
      </div>

      <BulkActionBar
        selectedCount={selectedIds.size}
        onClearSelection={() => setSelectedIds(new Set())}
        actions={[
          { label: t("common.bulkPublish"), onClick: () => handleBulkStatus("published") },
          { label: t("common.bulkDraft"), onClick: () => handleBulkStatus("draft"), variant: "outline" },
          { label: t("common.bulkArchive"), onClick: () => handleBulkStatus("archived"), variant: "outline" },
          { label: t("common.bulkDelete"), onClick: () => setBulkDeleteOpen(true), variant: "destructive" },
        ]}
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
          selectable
          selectedIds={selectedIds}
          onSelectionChange={setSelectedIds}
        />
      </div>

      <ConfirmDialog
        open={bulkDeleteOpen}
        onConfirm={handleBulkDelete}
        onCancel={() => setBulkDeleteOpen(false)}
        title={t("common.deleteConfirm")}
        description={t("common.confirmBulkDelete").replace("{count}", String(selectedIds.size))}
        variant="destructive"
        confirmLabel={t("common.bulkDelete")}
        isPending={isBulkDeleting}
      />
    </div>
  );
}
