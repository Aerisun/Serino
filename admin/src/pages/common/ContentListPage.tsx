import { useState, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import type { ContentAdminRead } from "@serino/api-client/models";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { BulkActionBar } from "@/components/BulkActionBar";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { Plus } from "lucide-react";
import { useI18n } from "@/i18n";
import type { ContentListConfig } from "./types";
import { DEFAULT_SORT_OPTIONS, DEFAULT_STATUS_TABS } from "./types";

interface ContentListPageProps {
  config: ContentListConfig;
}

export default function ContentListPage({ config }: ContentListPageProps) {
  const navigate = useNavigate();
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const [page, setPage] = useState(() => Number(searchParams.get("page")) || 1);
  const [statusFilter, setStatusFilter] = useState(() => searchParams.get("status") || "");
  const [search, setSearch] = useState(() => searchParams.get("q") || "");
  const [searchDebounced, setSearchDebounced] = useState(() => searchParams.get("q") || "");
  const [sort, setSort] = useState("created_at:desc");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);

  const [sort_by, sort_order] = sort.split(":");
  const sortOptions = config.sortOptions ?? DEFAULT_SORT_OPTIONS;
  const statusTabs = config.statusTabs ?? DEFAULT_STATUS_TABS;

  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleSearch = (value: string) => {
    setSearch(value);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setSearchDebounced(value);
      setPage(1);
      syncUrl(1, statusFilter, value);
    }, 300);
  };

  const syncUrl = (p: number, status: string, q: string) => {
    const params: Record<string, string> = {};
    if (p > 1) params.page = String(p);
    if (status) params.status = status;
    if (q) params.q = q;
    setSearchParams(params, { replace: true });
  };

  const handlePageChange = (p: number) => {
    setPage(p);
    syncUrl(p, statusFilter, searchDebounced);
  };

  const handleStatusChange = (v: string) => {
    setStatusFilter(v);
    setPage(1);
    syncUrl(1, v, searchDebounced);
  };

  const params = {
    page,
    status: statusFilter || undefined,
    search: searchDebounced || undefined,
    sort_by,
    sort_order,
  };
  const { data: listData, isLoading } = config.useList(params);
  const items = (listData?.data?.items ?? []) as ContentAdminRead[];
  const total = listData?.data?.total ?? 0;
  const pageSize = listData?.data?.page_size ?? 20;

  const { mutateAsync: bulkDelete, isPending: isBulkDeleting } =
    config.useBulkDelete({
      mutation: {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: [...config.getQueryKey()] });
        },
      },
    });

  const { mutateAsync: bulkStatus } = config.useBulkStatus({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: [...config.getQueryKey()] });
      },
    },
  });

  const handleBulkDelete = async () => {
    try {
      const res = await bulkDelete({
        data: { ids: Array.from(selectedIds) },
      });
      toast.success(
        t("common.operationSuccess") + ` (${res.data.affected})`,
      );
      setSelectedIds(new Set());
      setBulkDeleteOpen(false);
    } catch {
      toast.error(t("common.operationFailed"));
    }
  };

  const handleBulkStatus = async (status: string) => {
    try {
      const res = await bulkStatus({
        data: { ids: Array.from(selectedIds), status },
      });
      toast.success(
        t("common.operationSuccess") + ` (${res.data.affected})`,
      );
      setSelectedIds(new Set());
    } catch {
      toast.error(t("common.operationFailed"));
    }
  };

  return (
    <div>
      <PageHeader
        title={t(config.titleKey)}
        description={t(config.descriptionKey)}
        actions={
          <Button onClick={() => navigate(config.newPath)}>
            <Plus className="h-4 w-4 mr-2" /> {t(config.newButtonLabelKey)}
          </Button>
        }
      />

      <div className="flex items-center gap-4 mb-4">
        <Tabs value={statusFilter} onValueChange={handleStatusChange}>
          <TabsList>
            <TabsTrigger value="">{t("common.all")}</TabsTrigger>
            {statusTabs.map((tab) => (
              <TabsTrigger key={tab} value={tab}>
                {t(`posts.${tab}`)}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <Input
          placeholder={t("common.searchPlaceholder")}
          className="max-w-xs"
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
        />
        <select
          className="h-9 rounded-md admin-glass-input px-3 text-sm"
          value={sort}
          onChange={(e) => {
            setSort(e.target.value);
            setPage(1);
          }}
        >
          {sortOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {t(opt.labelKey)}
            </option>
          ))}
        </select>
      </div>

      <BulkActionBar
        selectedCount={selectedIds.size}
        onClearSelection={() => setSelectedIds(new Set())}
        actions={[
          {
            label: t("common.bulkPublish"),
            onClick: () => handleBulkStatus("published"),
          },
          {
            label: t("common.bulkDraft"),
            onClick: () => handleBulkStatus("draft"),
            variant: "outline",
          },
          {
            label: t("common.bulkArchive"),
            onClick: () => handleBulkStatus("archived"),
            variant: "outline",
          },
          {
            label: t("common.bulkDelete"),
            onClick: () => setBulkDeleteOpen(true),
            variant: "destructive",
          },
        ]}
      />

      <div className="rounded-lg admin-glass overflow-hidden">
        <DataTable<ContentAdminRead>
          columns={config.columns}
          data={items}
          total={total}
          page={page}
          pageSize={pageSize}
          onPageChange={handlePageChange}
          isLoading={isLoading}
          onRowClick={(row) => navigate(config.editPath(row.id))}
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
        description={t("common.confirmBulkDelete").replace(
          "{count}",
          String(selectedIds.size),
        )}
        variant="destructive"
        confirmLabel={t("common.bulkDelete")}
        isPending={isBulkDeleting}
      />
    </div>
  );
}
