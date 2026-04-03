import { Fragment, useState } from "react";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/Table";
import { Button } from "@/components/ui/Button";
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp } from "lucide-react";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";

interface Column<T> {
  header: string;
  accessor: keyof T | ((row: T) => React.ReactNode);
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  total?: number;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
  isLoading?: boolean;
  onRowClick?: (row: T) => void;
  selectable?: boolean;
  selectedIds?: Set<string>;
  onSelectionChange?: (ids: Set<string>) => void;
  renderExpandedRow?: (row: T) => React.ReactNode;
  getRowClassName?: (row: T) => string | undefined;
}

export function DataTable<T extends { id: string }>({
  columns,
  data,
  total = 0,
  page = 1,
  pageSize = 20,
  onPageChange,
  isLoading,
  onRowClick,
  selectable,
  selectedIds,
  onSelectionChange,
  renderExpandedRow,
  getRowClassName,
}: DataTableProps<T>) {
  const { t } = useI18n();
  const totalPages = Math.ceil(total / pageSize);
  const hasExpandedRow = Boolean(renderExpandedRow);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const allPageSelected =
    data.length > 0 && data.every((row) => selectedIds?.has(row.id));
  const somePageSelected = data.some((row) => selectedIds?.has(row.id));

  const toggleAll = () => {
    if (!onSelectionChange || !selectedIds) return;
    const next = new Set(selectedIds);
    if (allPageSelected) {
      data.forEach((row) => next.delete(row.id));
    } else {
      data.forEach((row) => next.add(row.id));
    }
    onSelectionChange(next);
  };

  const toggleRow = (id: string) => {
    if (!onSelectionChange || !selectedIds) return;
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    onSelectionChange(next);
  };

  const toggleExpanded = (id: string) => {
    if (!renderExpandedRow) return;
    setExpandedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const colSpan = columns.length + (selectable ? 1 : 0) + (hasExpandedRow ? 1 : 0);

  return (
    <div className="overflow-x-auto rounded-[var(--admin-radius-xl)] admin-glass-strong">
      <Table>
        <TableHeader>
          <TableRow>
            {hasExpandedRow && <TableHead className="w-10" />}
            {selectable && (
              <TableHead className="w-10">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-gray-300"
                  checked={allPageSelected}
                  ref={(el) => {
                    if (el)
                      el.indeterminate = somePageSelected && !allPageSelected;
                  }}
                  onChange={toggleAll}
                />
              </TableHead>
            )}
            {columns.map((col, i) => (
              <TableHead key={i} className={col.className}>
                {col.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow>
              <TableCell
                colSpan={colSpan}
                className="text-center py-8 text-muted-foreground"
              >
                {t("common.loading")}
              </TableCell>
            </TableRow>
          ) : data.length === 0 ? (
            <TableRow>
              <TableCell
                colSpan={colSpan}
                className="text-center py-8 text-muted-foreground"
              >
                {t("common.noData")}
              </TableCell>
            </TableRow>
          ) : (
            data.map((row) => (
              <Fragment key={row.id}>
                <TableRow
                  className={cn(onRowClick ? "cursor-pointer" : "", getRowClassName?.(row))}
                  onClick={() => onRowClick?.(row)}
                >
                  {hasExpandedRow && (
                    <TableCell
                      className="w-10"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => toggleExpanded(row.id)}
                        aria-label={expandedIds.has(row.id) ? t("common.collapse") : t("common.expand")}
                      >
                        {expandedIds.has(row.id) ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )}
                      </Button>
                    </TableCell>
                  )}
                  {selectable && (
                    <TableCell
                      className="w-10"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-gray-300"
                        checked={selectedIds?.has(row.id) ?? false}
                        onChange={() => toggleRow(row.id)}
                      />
                    </TableCell>
                  )}
                  {columns.map((col, i) => (
                    <TableCell key={i} className={col.className}>
                      {typeof col.accessor === "function"
                        ? col.accessor(row)
                        : (row[col.accessor] as React.ReactNode)}
                    </TableCell>
                  ))}
                </TableRow>
                {hasExpandedRow && expandedIds.has(row.id) ? (
                  <TableRow>
                    <TableCell colSpan={colSpan} className="bg-muted/20 px-4 py-0">
                      {renderExpandedRow(row)}
                    </TableCell>
                  </TableRow>
                ) : null}
              </Fragment>
            ))
          )}
        </TableBody>
      </Table>
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))]">
          <span className="text-sm text-muted-foreground">
            {t("common.itemsTotal").replace("{count}", String(total))}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => onPageChange?.(page - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm">
              {page} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => onPageChange?.(page + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
