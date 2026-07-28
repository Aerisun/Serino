import { type ReactNode, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import type { ContentAdminRead } from "@serino/api-client/models";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { BulkActionBar } from "@/components/BulkActionBar";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { NativeSelect } from "@/components/ui/NativeSelect";
import { ChevronLeft, ChevronRight, Clock3, Plus } from "lucide-react";
import { useI18n } from "@/i18n";
import { getBodySnippet } from "@/lib/content-snippets";
import { cn, formatDate } from "@/lib/utils";
import type { ContentListConfig } from "./types";
import { DEFAULT_SORT_OPTIONS, DEFAULT_VISIBILITY_TABS } from "./types";

interface ContentListPageProps {
  config: ContentListConfig;
}

function contentText(value: unknown): string {
  if (value == null) {
    return "";
  }

  return typeof value === "string" ? value : String(value);
}

function contentId(row: ContentAdminRead): string {
  return contentText(row.id);
}

function contentTitle(row: ContentAdminRead): string {
  const title = contentText(row.title).trim();
  if (title) {
    return title;
  }

  const bodySnippet = getBodySnippet(contentText(row.body));
  const slug = contentText(row.slug).trim();
  return bodySnippet || slug || contentId(row);
}

function contentSummary(row: ContentAdminRead, title: string): string {
  const summary = getBodySnippet(contentText(row.summary));
  const bodySnippet = getBodySnippet(contentText(row.body));
  const nextSummary = summary || bodySnippet;

  return nextSummary && nextSummary !== title ? nextSummary : "";
}

interface MobileContentListProps {
  resourceKey: string;
  items: ContentAdminRead[];
  isLoading?: boolean;
  total: number;
  page: number;
  pageSize: number;
  selectedIds: Set<string>;
  onSelectionChange: (ids: Set<string>) => void;
  onPageChange: (page: number) => void;
  onRowClick: (row: ContentAdminRead) => void;
  renderMobileVisibility?: (row: ContentAdminRead) => ReactNode;
}

function MobileContentList({
  resourceKey,
  items,
  isLoading,
  total,
  page,
  pageSize,
  selectedIds,
  onSelectionChange,
  onPageChange,
  onRowClick,
  renderMobileVisibility,
}: MobileContentListProps) {
  const { t } = useI18n();
  const totalPages = Math.ceil(total / pageSize);
  const showTitleSummary = resourceKey === "posts" || resourceKey === "diary";

  const toggleRow = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    onSelectionChange(next);
  };

  if (isLoading) {
    return (
      <div className="space-y-3 md:hidden">
        {Array.from({ length: 4 }).map((_, index) => (
          <div
            key={index}
            className="h-40 rounded-[var(--admin-radius-xl)] border border-[rgba(var(--admin-border-subtle)/0.5)] bg-[rgb(var(--admin-surface-1)/0.9)] p-4 shadow-[0_16px_36px_-30px_rgb(15_23_42/0.38)] dark:bg-white/[0.04]"
          >
            <div className="h-4 w-2/3 animate-pulse rounded-full bg-foreground/10" />
            <div className="mt-4 h-3 w-full animate-pulse rounded-full bg-foreground/10" />
            <div className="mt-2 h-3 w-4/5 animate-pulse rounded-full bg-foreground/10" />
            <div className="mt-5 flex gap-2">
              <div className="h-7 w-16 animate-pulse rounded-full bg-foreground/10" />
              <div className="h-7 w-16 animate-pulse rounded-full bg-foreground/10" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="rounded-[var(--admin-radius-xl)] admin-glass-strong px-5 py-12 text-center text-sm text-muted-foreground md:hidden">
        {t("common.noData")}
      </div>
    );
  }

  return (
    <div className="space-y-3 md:hidden">
      <div className="space-y-3">
        {items.map((row) => {
          const id = contentId(row);
          const title = contentTitle(row);
          const summary = contentSummary(row, title);
          const passage = getBodySnippet(contentText(row.body), title);
          const visibility = contentText(row.visibility);
          const visibilityBadge = renderMobileVisibility?.(row) ??
            (visibility ? <StatusBadge status={visibility} /> : null);
          const publishedAt = formatDate(
            contentText(row.published_at) || contentText(row.updated_at),
          );
          const selected = selectedIds.has(id);

          return (
            <article
              key={id}
              role="button"
              tabIndex={0}
              className={cn(
                "group rounded-[var(--admin-radius-xl)] border border-[rgba(var(--admin-border-subtle)/0.5)] bg-[rgb(var(--admin-surface-1)/0.9)] p-4 shadow-[0_16px_36px_-30px_rgb(15_23_42/0.38)] transition-[border-color,box-shadow,transform] active:translate-y-px dark:bg-white/[0.04]",
                selected &&
                  "ring-2 ring-[rgb(var(--admin-accent-rgb)/0.4)] shadow-[0_20px_48px_-30px_rgb(var(--admin-accent-rgb)/0.7)]",
              )}
              onClick={() => onRowClick(row)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onRowClick(row);
                }
              }}
            >
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  className="mt-1 h-5 w-5 shrink-0 rounded border-gray-300"
                  checked={selected}
                  aria-label={title}
                  onClick={(event) => event.stopPropagation()}
                  onChange={() => toggleRow(id)}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex min-w-0 items-start gap-2">
                    {showTitleSummary ? (
                      <h3 className="min-w-0 flex-1 break-words text-base font-semibold leading-6 text-foreground/95 line-clamp-2">
                        {title}
                      </h3>
                    ) : (
                      <p className="min-w-0 flex-1 break-words text-[13px] font-normal leading-5 text-foreground/90 line-clamp-3">
                        {passage}
                      </p>
                    )}
                    <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground/70 transition-transform group-active:translate-x-0.5" />
                  </div>

                  {showTitleSummary && summary ? (
                    <p className="mt-3 line-clamp-2 break-words text-sm leading-6 text-muted-foreground/95">
                      {summary}
                    </p>
                  ) : null}

                  <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    {visibilityBadge}
                    <span className="flex min-w-0 items-center gap-1.5">
                      <Clock3 className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate">{publishedAt}</span>
                    </span>
                  </div>
                </div>
              </div>
            </article>
          );
        })}
      </div>

      {totalPages > 1 ? (
        <div className="flex items-center justify-between rounded-[var(--admin-radius-lg)] admin-glass-strong px-3 py-3">
          <span className="text-xs text-muted-foreground">
            {t("common.itemsTotal").replace("{count}", String(total))}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="min-w-12 text-center text-sm">
              {page} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => onPageChange(page + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function ContentListPage({ config }: ContentListPageProps) {
  const navigate = useNavigate();
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const initialVisibilityParam = searchParams.get("visibility") || "";
  const [page, setPage] = useState(() => Number(searchParams.get("page")) || 1);
  const [visibilityFilter, setVisibilityFilter] = useState(() =>
    initialVisibilityParam === "public" || initialVisibilityParam === "private"
      ? initialVisibilityParam
      : "",
  );
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
  const visibilityTabs = config.visibilityTabs ?? DEFAULT_VISIBILITY_TABS;

  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleSearch = (value: string) => {
    setSearch(value);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setSearchDebounced(value);
      setPage(1);
      syncUrl(1, visibilityFilter, value);
    }, 300);
  };

  const syncUrl = (
    p: number,
    visibility: string,
    q: string,
  ) => {
    const params: Record<string, string> = {};
    if (p > 1) params.page = String(p);
    if (visibility) params.visibility = visibility;
    if (q) params.q = q;
    setSearchParams(params, { replace: true });
  };

  const handlePageChange = (p: number) => {
    setPage(p);
    syncUrl(p, visibilityFilter, searchDebounced);
  };

  const handleVisibilityChange = (nextVisibility: string) => {
    setVisibilityFilter(nextVisibility);
    setPage(1);
    syncUrl(1, nextVisibility, searchDebounced);
  };

  const params = {
    page,
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

  const { mutateAsync: bulkVisibility } = config.useBulkVisibility({
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

  const handleBulkVisibility = async (visibility: string) => {
    try {
      const res = await bulkVisibility({
        data: { ids: Array.from(selectedIds), visibility },
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
        inlineActionsOnMobile
        actions={
          <Button onClick={() => navigate(config.newPath)}>
            <Plus className="h-4 w-4 mr-2" /> {t(config.newButtonLabelKey)}
          </Button>
        }
      />

      <div
        role="toolbar"
        aria-label={t("common.contentFiltersAndSort")}
        className="mb-4 flex min-w-0 flex-col gap-3 md:flex-row md:items-start"
      >
        <Input
          placeholder={t("common.searchPlaceholder")}
          className="min-w-0 md:w-72 md:shrink-0"
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
        />
        <div className="flex min-w-0 items-start justify-between gap-2 md:flex-1">
          <div
            className={cn(
              "flex min-w-0 items-center gap-2",
              filterActionsExpanded && "w-full",
            )}
          >
            <div
              className={cn(
                "flex min-w-0 items-center gap-2",
                filterActionsExpanded
                  ? "-mx-1 -mb-9 -mt-4 overflow-x-auto px-1 pb-9 pt-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden md:overflow-visible"
                  : "overflow-visible",
              )}
            >
              <Button
                variant={visibilityFilter === "" ? "default" : "outline"}
                className="shrink-0 !shadow-none"
                onClick={() => handleVisibilityChange("")}
              >
                {t("common.all")}
              </Button>
              <Button
                variant="outline"
                size="icon"
                className="shrink-0 !shadow-none"
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
                    ? "-mx-1 -mb-9 -mt-4 max-w-[520px] translate-x-0 px-1 pb-9 pt-4 opacity-100"
                    : "max-w-0 opacity-0 -translate-x-2 pointer-events-none",
                )}
              >
                {visibilityTabs.map((tab) => (
                  <Button
                    key={tab}
                    type="button"
                    size="sm"
                    variant={visibilityFilter === tab ? "default" : "outline"}
                    className="shrink-0 !shadow-none"
                    onClick={() => handleVisibilityChange(tab)}
                  >
                    {t(`status.${tab}`)}
                  </Button>
                ))}
              </div>
            </div>
          </div>
          {!filterActionsExpanded ? (
            <NativeSelect
              value={sort}
              onChange={(event) => {
                setSort(event.target.value);
                setPage(1);
              }}
              aria-label={t("common.sortBy")}
              containerClassName="w-[clamp(8.75rem,42vw,12rem)] min-w-0 shrink-0 md:w-48"
              className="h-9 min-w-0 rounded-md px-3 text-sm"
            >
              {sortOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {t(opt.labelKey)}
                </option>
              ))}
            </NativeSelect>
          ) : null}
        </div>
      </div>

      <BulkActionBar
        selectedCount={selectedIds.size}
        onClearSelection={() => setSelectedIds(new Set())}
        actions={[
          {
            label: t("common.bulkPublish"),
            onClick: () => handleBulkVisibility("public"),
          },
          {
            label: t("status.private"),
            onClick: () => handleBulkVisibility("private"),
            variant: "outline",
          },
          {
            label: t("common.bulkDelete"),
            onClick: () => setBulkDeleteOpen(true),
            variant: "destructive",
          },
        ]}
      />

      <MobileContentList
        resourceKey={config.resourceKey}
        items={items}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={handlePageChange}
        isLoading={isLoading}
        onRowClick={(row) => navigate(config.editPath(contentId(row)))}
        renderMobileVisibility={config.renderMobileVisibility}
        selectedIds={selectedIds}
        onSelectionChange={setSelectedIds}
      />

      <div className="hidden md:block">
        <DataTable<ContentAdminRead>
          columns={config.columns}
          data={items}
          total={total}
          page={page}
          pageSize={pageSize}
          onPageChange={handlePageChange}
          isLoading={isLoading}
          onRowClick={(row) => navigate(config.editPath(contentId(row)))}
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
