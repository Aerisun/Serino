import { useRef, useState } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";
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
  const [statusFilter, setStatusFilter] = useState(
    () => searchParams.get("status") || "",
  );
  const [visibilityFilter, setVisibilityFilter] = useState(
    () => searchParams.get("visibility") || "",
  );
  const initialFilterMode = (() => {
    if (searchParams.get("status") === "draft") return "draft";
    if (
      searchParams.get("status") === "published" &&
      searchParams.get("visibility") === "public"
    )
      return "public_publish";
    if (
      searchParams.get("status") === "archived" &&
      searchParams.get("visibility") === "private"
    )
      return "private_archive";
    return "";
  })();
  const [filterMode, setFilterMode] = useState(initialFilterMode);
  const [search, setSearch] = useState(() => searchParams.get("q") || "");
  const [searchDebounced, setSearchDebounced] = useState(
    () => searchParams.get("q") || "",
  );
  const [sort, setSort] = useState("updated_at:desc");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [filterActionsExpanded, setFilterActionsExpanded] = useState(false);

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
      syncUrl(1, statusFilter, visibilityFilter, value);
    }, 300);
  };

  const syncUrl = (
    p: number,
    status: string,
    visibility: string,
    q: string,
  ) => {
    const params: Record<string, string> = {};
    if (p > 1) params.page = String(p);
    if (status) params.status = status;
    if (visibility) params.visibility = visibility;
    if (q) params.q = q;
    setSearchParams(params, { replace: true });
  };

  const handlePageChange = (p: number) => {
    setPage(p);
    syncUrl(p, statusFilter, visibilityFilter, searchDebounced);
  };

  const handleStatusChange = (v: string) => {
    let nextStatus = "";
    let nextVisibility = "";
    if (v === "draft") {
      nextStatus = "draft";
    } else if (v === "public_publish") {
      nextStatus = "published";
      nextVisibility = "public";
    } else if (v === "private_archive") {
      nextStatus = "archived";
      nextVisibility = "private";
    }
    setFilterMode(v);
    setStatusFilter(nextStatus);
    setVisibilityFilter(nextVisibility);
    setPage(1);
    syncUrl(1, nextStatus, nextVisibility, searchDebounced);
  };

  const params = {
    page,
    status: statusFilter || undefined,
    visibility: visibilityFilter || undefined,
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
          queryClient.invalidateQueries({
            queryKey: [...config.getQueryKey()],
          });
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
      toast.success(t("common.operationSuccess") + ` (${res.data.affected})`);
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
      toast.success(t("common.operationSuccess") + ` (${res.data.affected})`);
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

      <div className="mb-4 flex flex-wrap items-center gap-4">
        <div className="flex min-w-0 items-center gap-2">
          <Button
            variant={filterMode === "" ? "default" : "outline"}
            onClick={() => handleStatusChange("")}
          >
            {t("common.all")}
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="shrink-0"
            aria-label={filterActionsExpanded ? "收起筛选选项" : "展开筛选选项"}
            aria-expanded={filterActionsExpanded}
            onClick={() => setFilterActionsExpanded((open) => !open)}
          >
            {filterActionsExpanded ? (
              <ChevronLeft className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </Button>
          <div
            className={cn(
              "flex items-center gap-2 overflow-hidden whitespace-nowrap transition-[max-width,opacity,transform] duration-200 ease-out",
              filterActionsExpanded
                ? "max-w-[520px] opacity-100 translate-x-0"
                : "max-w-0 opacity-0 -translate-x-2 pointer-events-none",
            )}
          >
            {statusTabs.map((tab) => (
              <Button
                key={tab}
                type="button"
                size="sm"
                variant="outline"
                className="shrink-0"
                onClick={() => handleStatusChange(tab)}
              >
                {tab === "public_publish"
                  ? t("posts.published")
                  : tab === "private_archive"
                    ? t("posts.archived")
                    : t(`posts.${tab}`)}
              </Button>
            ))}
          </div>
        </div>
        <Select
          value={sort}
          onValueChange={(value) => {
            setSort(value);
            setPage(1);
          }}
        >
          <SelectTrigger className="h-9 w-[220px] shrink-0 rounded-md px-3 text-sm">
            <SelectValue placeholder={t("common.sortBy")} />
          </SelectTrigger>
          <SelectContent>
            {sortOptions.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {t(opt.labelKey)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          placeholder={t("common.searchPlaceholder")}
          className="max-w-xs flex-1 min-w-[220px]"
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
        />
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
            label: t("posts.archived"),
            onClick: () => handleBulkStatus("archived"),
            variant: "outline",
          },
          {
            label: t("common.bulkDraft"),
            onClick: () => handleBulkStatus("draft"),
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
