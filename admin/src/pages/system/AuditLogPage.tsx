import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getListAuditLogsApiV1AdminSystemAuditLogsGetQueryKey,
  useListAuditLogsApiV1AdminSystemAuditLogsGet,
} from "@serino/api-client/admin";
import type { AuditLogRead } from "@serino/api-client/models";
import { toast } from "sonner";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { AdminSectionTabs } from "@/components/ui/AdminSectionTabs";
import { Tabs, TabsContent } from "@/components/ui/Tabs";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { ChevronDown, ChevronRight, History, Shield } from "lucide-react";
import {
  type ConfigDiffLine,
  type ConfigRevisionListItem,
  getConfigRevisionDetail,
  listConfigRevisions,
  restoreConfigRevision,
} from "@/pages/system/api";

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function getPathSegments(path: string): string[] {
  const segments: string[] = [];
  let token = "";

  for (let index = 0; index < path.length; index += 1) {
    const char = path[index];
    if (char === ".") {
      if (token) segments.push(token);
      token = "";
      continue;
    }
    if (char === "[") {
      if (token) segments.push(token);
      token = "";
      const closeIndex = path.indexOf("]", index);
      if (closeIndex === -1) {
        token += char;
        continue;
      }
      segments.push(path.slice(index, closeIndex + 1));
      index = closeIndex;
      continue;
    }
    token += char;
  }

  if (token) segments.push(token);
  return segments;
}

function parseIndexSegment(segment: string): number | null {
  if (!segment.startsWith("[") || !segment.endsWith("]")) {
    return null;
  }

  const index = Number(segment.slice(1, -1));
  return Number.isInteger(index) ? index : null;
}

function buildChildPath(parentPath: string, segment: string): string {
  if (!parentPath) return segment;
  return segment.startsWith("[") ? `${parentPath}${segment}` : `${parentPath}.${segment}`;
}

function joinPathSegments(segments: string[]): string {
  let currentPath = "";
  segments.forEach((segment) => {
    currentPath = buildChildPath(currentPath, segment);
  });
  return currentPath;
}

function getValueAtPath(root: unknown, path: string): unknown {
  if (!path) return root;

  let current: unknown = root;
  for (const segment of getPathSegments(path)) {
    const index = parseIndexSegment(segment);
    if (index !== null) {
      if (!Array.isArray(current)) {
        return undefined;
      }
      current = current[index];
      continue;
    }

    if (!isPlainObject(current)) {
      return undefined;
    }
    current = current[segment];
  }

  return current;
}

function formatValueText(value: unknown): string {
  if (value === undefined) return "undefined";
  if (value === null) return "null";
  if (typeof value === "string") return value === "" ? '""' : value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value, null, 2);
}

function parseDiffValue(raw: string): unknown {
  const value = raw.trim();

  if (
    (value.startsWith("{") && value.endsWith("}")) ||
    (value.startsWith("[") && value.endsWith("]"))
  ) {
    try {
      return JSON.parse(value) as unknown;
    } catch {
      return raw;
    }
  }

  return raw;
}

function formatDiffValue(raw: string): string {
  return formatValueText(parseDiffValue(raw));
}

function formatInlineDiffValue(raw: string): string {
  const text = formatDiffValue(raw);
  return text.length > 64 ? `${text.slice(0, 64)}...` : text;
}

function readStringField(value: unknown, key: string): string | null {
  if (!isPlainObject(value)) return null;
  const field = value[key];
  return typeof field === "string" && field.trim() ? field.trim() : null;
}

function formatIdentity(value: unknown): string | null {
  if (!isPlainObject(value)) return null;

  const parts = [
    readStringField(value, "page_key"),
    readStringField(value, "title"),
    readStringField(value, "nav_label"),
    readStringField(value, "label"),
    readStringField(value, "name"),
    readStringField(value, "key"),
    readStringField(value, "resource_key"),
  ].filter((part, index, list): part is string => Boolean(part) && list.indexOf(part) === index);

  if (parts.length > 0) {
    return parts.join(" · ");
  }

  const id = readStringField(value, "id");
  return id ? `id=${id}` : null;
}

function chooseScopePath(path: string, beforePreview: unknown, afterPreview: unknown): string {
  const segments = getPathSegments(path);
  const parentSegments = segments.slice(0, -1);
  let currentSegments: string[] = [];
  let bestIdentityPath = "";
  let lastIndexPath = "";

  parentSegments.forEach((segment) => {
    currentSegments = [...currentSegments, segment];
    const candidatePath = joinPathSegments(currentSegments);
    const candidateValue =
      getValueAtPath(afterPreview, candidatePath) ?? getValueAtPath(beforePreview, candidatePath);

    if (parseIndexSegment(segment) !== null) {
      lastIndexPath = candidatePath;
    }
    if (formatIdentity(candidateValue)) {
      bestIdentityPath = candidatePath;
    }
  });

  if (bestIdentityPath) return bestIdentityPath;
  if (lastIndexPath) return lastIndexPath;
  if (segments.length > 1) return joinPathSegments([segments[0]]);
  return path;
}

function buildLocationLabel(path: string, beforePreview: unknown, afterPreview: unknown, t: (key: string) => string): string {
  const segments = getPathSegments(path);
  const parentSegments = segments.slice(0, -1);
  let currentPath = "";

  return parentSegments
    .map((segment) => {
      currentPath = buildChildPath(currentPath, segment);
      const index = parseIndexSegment(segment);
      if (index === null) {
        return segment;
      }

      const itemValue =
        getValueAtPath(afterPreview, currentPath) ?? getValueAtPath(beforePreview, currentPath);
      const identity = formatIdentity(itemValue);
      const label = t("auditLog.indexItem").replace("{index}", String(index + 1));
      return identity ? `${label}（${identity}）` : label;
    })
    .join(" > ");
}

function buildContextSnippet(path: string, preview: unknown): { contextPath: string; snippet: unknown } {
  const segments = getPathSegments(path);
  if (segments.length <= 1) {
    return { contextPath: path, snippet: preview };
  }

  const contextSegments = segments.slice(0, -1);
  const contextPath = joinPathSegments(contextSegments);
  const contextValue = getValueAtPath(preview, contextPath);
  const changedLeaf = segments[segments.length - 1];
  const changedIndex = parseIndexSegment(changedLeaf);

  if (changedIndex !== null && Array.isArray(contextValue)) {
    return {
      contextPath,
      snippet: contextValue[changedIndex],
    };
  }

  if (isPlainObject(contextValue)) {
    const keys = Object.keys(contextValue);
    if (keys.length <= 12) {
      return { contextPath, snippet: contextValue };
    }

    const compactSnippet: Record<string, unknown> = {};
    ["page_key", "title", "nav_label", "label", "name", "id"].forEach((key) => {
      const value = contextValue[key];
      if (value !== undefined && typeof value !== "object") {
        compactSnippet[key] = value;
      }
    });
    if (changedLeaf in contextValue) {
      compactSnippet[changedLeaf] = contextValue[changedLeaf];
    }
    return {
      contextPath,
      snippet: Object.keys(compactSnippet).length > 0 ? compactSnippet : contextValue,
    };
  }

  return {
    contextPath,
    snippet: contextValue,
  };
}

interface ResolvedDiffLine {
  rawPath: string;
  scopeLabel: string;
  fieldLabel: string;
  locationLabel: string;
  beforeValue: string;
  afterValue: string;
  contextPath: string;
  beforeContext: unknown;
  afterContext: unknown;
}

function resolveDiffLine(
  line: ConfigDiffLine,
  beforePreview: unknown,
  afterPreview: unknown,
  t: (key: string) => string,
): ResolvedDiffLine {
  const scopePath = chooseScopePath(line.path, beforePreview, afterPreview);
  const scopeValue = getValueAtPath(afterPreview, scopePath) ?? getValueAtPath(beforePreview, scopePath);
  const fieldSegments = getPathSegments(line.path).slice(getPathSegments(scopePath).length);
  const beforeContext = buildContextSnippet(line.path, beforePreview);
  const afterContext = buildContextSnippet(line.path, afterPreview);

  return {
    rawPath: line.path,
    scopeLabel: formatIdentity(scopeValue) ? `${scopePath}（${formatIdentity(scopeValue)}）` : scopePath,
    fieldLabel: fieldSegments.length > 0 ? joinPathSegments(fieldSegments) : t("auditLog.wholeObject"),
    locationLabel: buildLocationLabel(line.path, beforePreview, afterPreview, t),
    beforeValue: formatDiffValue(line.before),
    afterValue: formatDiffValue(line.after),
    contextPath: beforeContext.contextPath || afterContext.contextPath || line.path,
    beforeContext: beforeContext.snippet,
    afterContext: afterContext.snippet,
  };
}

function ConfigRevisionExpandedRow({ revisionId }: { revisionId: string }) {
  const { t } = useI18n();
  const [expandedDiffKeys, setExpandedDiffKeys] = useState<Set<string>>(new Set());
  const { data, isLoading } = useQuery({
    queryKey: ["system", "config-revision-detail", revisionId],
    queryFn: () => getConfigRevisionDetail(revisionId),
  });

  if (isLoading || !data) {
    return <div className="py-4 text-sm text-muted-foreground">{t("common.loading")}</div>;
  }

  const resolvedDiffLines = data.diff_lines.map((line) =>
    resolveDiffLine(line, data.before_preview, data.after_preview, t),
  );

  const toggleDiffExpanded = (diffKey: string) => {
    setExpandedDiffKeys((current) => {
      const next = new Set(current);
      if (next.has(diffKey)) {
        next.delete(diffKey);
      } else {
        next.add(diffKey);
      }
      return next;
    });
  };

  return (
    <div className="space-y-4 py-4">
      <div className="space-y-2">
        <div className="text-sm font-medium">{t("auditLog.diffLines")}</div>
        {resolvedDiffLines.length === 0 ? (
          <div className="text-sm text-muted-foreground">{t("auditLog.noDiff")}</div>
        ) : (
          <>
            <div className="text-xs text-muted-foreground">
              {t("auditLog.changedItemsSummary").replace("{count}", String(resolvedDiffLines.length))}
            </div>
            <div className="overflow-hidden rounded-md border border-border/70">
              <table className="w-full text-sm">
                <thead className="bg-muted/30">
                  <tr>
                    <th className="w-10 px-1 py-2" />
                    <th className="px-3 py-2 text-left font-medium">{t("auditLog.objectColumn")}</th>
                    <th className="px-3 py-2 text-left font-medium">{t("auditLog.fieldColumn")}</th>
                    <th className="px-3 py-2 text-left font-medium">{t("auditLog.beforePreview")}</th>
                    <th className="px-3 py-2 text-left font-medium">{t("auditLog.afterPreview")}</th>
                  </tr>
                </thead>
                {resolvedDiffLines.map((line, index) => {
                  const diffKey = `${line.rawPath}::${index}`;
                  const isExpanded = expandedDiffKeys.has(diffKey);

                  return (
                    <tbody key={diffKey}>
                      <tr className="border-t border-border/50 align-top">
                        <td className="w-10 px-1 py-3 text-center">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => toggleDiffExpanded(diffKey)}
                            aria-label={isExpanded ? t("common.collapse") : t("common.expand")}
                          >
                            {isExpanded ? (
                              <ChevronDown className="h-4 w-4" />
                            ) : (
                              <ChevronRight className="h-4 w-4" />
                            )}
                          </Button>
                        </td>
                        <td className="px-3 py-3">
                          <div className="font-medium">{line.scopeLabel}</div>
                          <div className="mt-1 text-xs text-muted-foreground">{line.locationLabel}</div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {t("auditLog.rawPathLabel")}:{" "}
                            <code className="font-mono">{line.rawPath}</code>
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          <code className="whitespace-pre-wrap break-all text-xs">{line.fieldLabel}</code>
                        </td>
                        <td className="px-3 py-3">
                          <code className="block whitespace-pre-wrap break-all rounded-md border border-border/50 bg-muted/10 px-2 py-1.5 text-xs leading-5">
                            {formatInlineDiffValue(line.beforeValue)}
                          </code>
                        </td>
                        <td className="px-3 py-3">
                          <code className="block whitespace-pre-wrap break-all rounded-md border border-border/50 bg-muted/10 px-2 py-1.5 text-xs leading-5">
                            {formatInlineDiffValue(line.afterValue)}
                          </code>
                        </td>
                      </tr>
                      {isExpanded ? (
                        <tr className="border-t border-border/30 bg-muted/10">
                          <td colSpan={5} className="px-3 py-3">
                            <div className="mb-2 font-mono text-xs text-muted-foreground">{line.contextPath}</div>
                            <div className="grid gap-3 xl:grid-cols-2">
                              <div>
                                <div className="mb-1 text-xs text-muted-foreground">{t("auditLog.contextBefore")}</div>
                                <pre className="max-h-56 overflow-auto rounded-md border border-border/50 bg-background p-3 text-xs leading-5">
                                  {formatValueText(line.beforeContext)}
                                </pre>
                              </div>
                              <div>
                                <div className="mb-1 text-xs text-muted-foreground">{t("auditLog.contextAfter")}</div>
                                <pre className="max-h-56 overflow-auto rounded-md border border-border/50 bg-background p-3 text-xs leading-5">
                                  {formatValueText(line.afterContext)}
                                </pre>
                              </div>
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </tbody>
                  );
                })}
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function AuditLogPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [view, setView] = useState<"config" | "audit">("config");
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState("");
  const [resourceFilter, setResourceFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const auditParams = useMemo(
    () => ({
      page,
      action: actionFilter || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    }),
    [actionFilter, dateFrom, dateTo, page],
  );

  const { data: rawAudit, isLoading: isAuditLoading } = useListAuditLogsApiV1AdminSystemAuditLogsGet(
    auditParams,
    {
      query: {
        enabled: view === "audit",
      },
    },
  );
  const auditData = rawAudit?.data;

  const { data: configData, isLoading: isConfigLoading } = useQuery({
    queryKey: ["system", "config-revisions", page, resourceFilter, dateFrom, dateTo],
    queryFn: () =>
      listConfigRevisions({
        page,
        resource_key: resourceFilter || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      }),
    enabled: view === "config",
  });

  const restoreMutation = useMutation({
    mutationFn: (revisionId: string) => restoreConfigRevision(revisionId, { target: "before" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["system", "config-revisions"] });
      queryClient.invalidateQueries({ queryKey: ["system", "config-revision-detail"] });
      queryClient.invalidateQueries({ queryKey: getListAuditLogsApiV1AdminSystemAuditLogsGetQueryKey() });
      toast.success(t("common.operationSuccess"));
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : t("common.operationFailed"));
    },
  });

  const handleFilter = () => {
    setPage(1);
  };

  const handleClear = () => {
    setActionFilter("");
    setResourceFilter("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
  };

  const handleRestore = (revisionId: string) => {
    if (!window.confirm(t("auditLog.restoreConfigConfirm"))) {
      return;
    }
    restoreMutation.mutate(revisionId);
  };

  return (
    <div>
      <PageHeader 
        title={t("system.auditLog")} 
        description={t("system.auditLogDescription")}
        secondary={
          <AdminSectionTabs
            value={view}
            onValueChange={(next) => {
              setView(next as "config" | "audit");
              setPage(1);
            }}
            items={[
              {
                value: "config",
                label: t("auditLog.viewConfigHistory"),
                icon: History,
              },
              {
                value: "audit",
                label: t("auditLog.viewAuditLog"),
                icon: Shield,
              },
            ]}
          />
        }
      />

      <Tabs
        value={view}
        onValueChange={(next) => {
          setView(next as "config" | "audit");
          setPage(1);
        }}
      >

        <div className="mb-4 flex flex-wrap items-end gap-3">
          {view === "config" ? (
            <div className="flex flex-col gap-1">
              <label className="text-sm text-muted-foreground">{t("auditLog.filterByResource")}</label>
              <input
                type="text"
                value={resourceFilter}
                onChange={(e) => setResourceFilter(e.target.value)}
                placeholder={t("auditLog.filterByResource")}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              />
            </div>
          ) : (
            <div className="flex flex-col gap-1">
              <label className="text-sm text-muted-foreground">{t("auditLog.filterByAction")}</label>
              <input
                type="text"
                value={actionFilter}
                onChange={(e) => setActionFilter(e.target.value)}
                placeholder={t("auditLog.filterByAction")}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              />
            </div>
          )}
          <div className="flex flex-col gap-1">
            <label className="text-sm text-muted-foreground">{t("auditLog.dateFrom")}</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-sm text-muted-foreground">{t("auditLog.dateTo")}</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            />
          </div>
          <Button size="sm" onClick={handleFilter}>
            {t("auditLog.filter")}
          </Button>
          <Button size="sm" variant="outline" onClick={handleClear}>
            {t("auditLog.clearFilter")}
          </Button>
        </div>

        <TabsContent value="config">
          <div className="border rounded-lg">
            <DataTable<ConfigRevisionListItem>
              columns={[
                { header: t("auditLog.resource"), accessor: (row) => <Badge variant="outline">{row.resource_label}</Badge> },
                { header: t("system.action"), accessor: (row) => <Badge variant="secondary">{row.operation}</Badge> },
                { header: t("auditLog.summary"), accessor: "summary" },
                { header: t("auditLog.changedFields"), accessor: (row) => row.changed_fields.length },
                { header: t("common.date"), accessor: (row) => formatDate(row.created_at) },
                {
                  header: t("common.actions"),
                  accessor: (row) => (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={restoreMutation.isPending}
                      onClick={(event) => {
                        event.stopPropagation();
                        handleRestore(row.id);
                      }}
                    >
                      {t("system.restore")}
                    </Button>
                  ),
                },
              ]}
              data={configData?.items ?? []}
              total={configData?.total ?? 0}
              page={page}
              pageSize={configData?.page_size ?? 20}
              onPageChange={setPage}
              isLoading={isConfigLoading}
              renderExpandedRow={(row) => <ConfigRevisionExpandedRow revisionId={row.id} />}
            />
          </div>
        </TabsContent>

        <TabsContent value="audit">
          <div className="border rounded-lg">
            <DataTable<AuditLogRead>
              columns={[
                { header: t("system.action"), accessor: (row) => <Badge variant="outline">{row.action}</Badge> },
                {
                  header: t("system.target"),
                  accessor: (row) => (row.target_type ? `${row.target_type}:${row.target_id || ""}` : "-"),
                },
                {
                  header: t("common.payload"),
                  accessor: (row) => <code className="text-xs max-w-xs truncate block">{JSON.stringify(row.payload)}</code>,
                },
                { header: t("common.date"), accessor: (row) => formatDate(row.created_at) },
              ]}
              data={auditData?.items ?? []}
              total={auditData?.total ?? 0}
              page={page}
              pageSize={auditData?.page_size ?? 20}
              onPageChange={setPage}
              isLoading={isAuditLoading}
            />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
