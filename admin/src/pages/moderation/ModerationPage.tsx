import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listCommentsApiV1AdminModerationCommentsGet,
  listGuestbookApiV1AdminModerationGuestbookGet,
  moderateCommentEndpointApiV1AdminModerationCommentsCommentIdModeratePost as moderateCommentApiV1AdminModerationCommentsCommentIdModeratePost,
  moderateGuestbookEndpointApiV1AdminModerationGuestbookEntryIdModeratePost as moderateGuestbookApiV1AdminModerationGuestbookEntryIdModeratePost,
  getListCommentsApiV1AdminModerationCommentsGetQueryKey,
  getListGuestbookApiV1AdminModerationGuestbookGetQueryKey,
} from "@/api/generated/admin/admin";
import type {
  ListCommentsApiV1AdminModerationCommentsGetParams,
  ListGuestbookApiV1AdminModerationGuestbookGetParams,
  CommentAdminRead,
  GuestbookAdminRead,
  ModerateAction,
} from "@/api/generated/model";
import { listPosts, listDiary, listThoughts, listExcerpts } from "@/api/generated/admin/admin";
import { PageHeader } from "@/components/PageHeader";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/Tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { formatDate } from "@/lib/utils";
import {
  Check,
  ChevronDown,
  History,
  RotateCcw,
  Search,
  SlidersHorizontal,
  Trash2,
  X,
} from "lucide-react";
import { useI18n } from "@/i18n";
import { toast } from "sonner";

import { PAGE_KEY_LABELS, optionLabel } from "@/pages/site-config/constants";

type ModerationRecord = CommentAdminRead | GuestbookAdminRead;
type ModerationKind = "comments" | "guestbook";
type ModerationListParams = ListCommentsApiV1AdminModerationCommentsGetParams & ListGuestbookApiV1AdminModerationGuestbookGetParams;

/* slug → title cache, populated by useContentTitles */
type TitleMap = Map<string, string>;

const contentListFns: Record<
  string,
  (p: {
    search: string;
    page_size: number;
  }) => Promise<any>
> = {
  posts: (p) => listPosts(p) as any,
  diary: (p) => listDiary(p) as any,
  thoughts: (p) => listThoughts(p) as any,
  excerpts: (p) => listExcerpts(p) as any,
};

/** Fetch titles for all unique (type, slug) pairs in the current page of items. */
function useContentTitles(items: ModerationRecord[]): TitleMap {
  const [titles, setTitles] = useState<TitleMap>(new Map());
  const cacheRef = useRef<TitleMap>(new Map());

  useEffect(() => {
    const pairs = new Map<string, Set<string>>();
    for (const item of items) {
      const type = "content_type" in item ? item.content_type : null;
      const slug = "content_slug" in item ? item.content_slug : null;
      if (!type || !slug || cacheRef.current.has(`${type}/${slug}`)) continue;
      const set = pairs.get(type) ?? new Set();
      set.add(slug);
      pairs.set(type, set);
    }
    if (pairs.size === 0) return;

    let cancelled = false;
    (async () => {
      for (const [type, slugs] of pairs) {
        const listFn = contentListFns[type];
        if (!listFn) continue;
        for (const slug of slugs) {
          try {
            const res = await listFn({ search: slug, page_size: 5 });
            const match = res.items.find((c) => c.slug === slug);
            if (match) cacheRef.current.set(`${type}/${slug}`, match.title);
          } catch {
            /* ignore */
          }
        }
      }
      if (!cancelled) setTitles(new Map(cacheRef.current));
    })();
    return () => {
      cancelled = true;
    };
  }, [items]);

  return titles;
}

interface ModerationFilters {
  keyword: string;
  author: string;
  email: string;
  path: string;
  surface: string;
  status: string;
  sort: string;
}

interface ThreadNode {
  item: ModerationRecord;
  children: ThreadNode[];
}

const DEFAULT_FILTERS: ModerationFilters = {
  keyword: "",
  author: "",
  email: "",
  path: "",
  surface: "",
  status: "",
  sort: "created_desc",
};

const PAGE_SIZE = 20;
const COMMENT_SURFACE_OPTIONS = [
  "",
  "posts",
  "diary",
  "thoughts",
  "excerpts",
] as const;
const GUESTBOOK_SURFACE_OPTIONS = ["", "guestbook"] as const;
const STATUS_OPTIONS = ["", "pending", "approved", "rejected"] as const;
const SORT_OPTIONS = ["created_desc", "created_asc", "status", "path"] as const;

function getModerationAuthor(
  item: ModerationRecord,
  fallback: string = "访客",
) {
  if ("author_name" in item && item.author_name) return item.author_name;
  if ("nickname" in item && item.nickname) return item.nickname;
  if ("name" in item && item.name) return item.name;
  return fallback;
}

function getModerationBody(item: ModerationRecord) {
  if ("body" in item && item.body) return item.body;
  return "";
}

function getModerationSource(item: ModerationRecord) {
  if ("source" in item && item.source) return item.source;
  if ("content_type" in item && item.content_type) return item.content_type;
  if ("website" in item) return "guestbook";
  return "-";
}

function getModerationPath(
  item: ModerationRecord,
  lang: "zh" | "en" = "zh",
  titleMap?: TitleMap,
) {
  let raw = "";
  let type = "";
  let slug = "";
  if ("content_type" in item && item.content_type && item.content_slug) {
    type = item.content_type;
    slug = item.content_slug;
    raw = `/${type}/${slug}`;
  } else if ("path" in item && item.path) {
    raw = item.path;
    const m = raw.match(/^\/?([^/]+)\/(.+)$/);
    if (m) {
      type = m[1];
      slug = m[2];
    }
  } else if ("website" in item) {
    raw = "/guestbook";
  }
  if (!raw) return "-";

  if (type && slug) {
    const category = optionLabel(PAGE_KEY_LABELS, type, lang);
    const title = titleMap?.get(`${type}/${slug}`);
    return `${category} / ${title ?? slug.replace(/-/g, " ")}`;
  }
  const single = raw.replace(/^\//, "");
  return optionLabel(PAGE_KEY_LABELS, single, lang);
}

function getModerationEmail(item: ModerationRecord) {
  if ("author_email" in item && item.author_email) return item.author_email;
  if ("mail" in item && item.mail) return item.mail;
  if ("email" in item && item.email) return item.email;
  return "-";
}

function getModerationSurface(item: ModerationRecord) {
  if ("page_key" in item && item.page_key) return item.page_key;
  if ("content_type" in item && item.content_type) return item.content_type;
  if ("website" in item) return "guestbook";
  return "-";
}

function normalizeModerationStatus(status: string) {
  if (status === "waiting") return "pending";
  if (status === "spam") return "rejected";
  return status;
}

function getModerationParentId(item: ModerationRecord) {
  return "parent_id" in item ? item.parent_id : null;
}

function buildThreadForest(items: ModerationRecord[]) {
  const byId = new Map(items.map((item) => [item.id, item] as const));
  const childrenByParent = new Map<string, ModerationRecord[]>();
  const roots: ModerationRecord[] = [];

  for (const item of items) {
    const parentId = getModerationParentId(item);
    if (parentId && byId.has(parentId)) {
      const children = childrenByParent.get(parentId) ?? [];
      children.push(item);
      childrenByParent.set(parentId, children);
    } else {
      roots.push(item);
    }
  }

  const sortByCreated = (a: ModerationRecord, b: ModerationRecord) =>
    new Date(a.created_at).getTime() - new Date(b.created_at).getTime();

  const buildNode = (item: ModerationRecord): ThreadNode => ({
    item,
    children: (childrenByParent.get(item.id) ?? [])
      .sort(sortByCreated)
      .map(buildNode),
  });

  return roots.sort(sortByCreated).map(buildNode);
}

/** Find the subtree containing `targetId`. Returns [] if the item is a lone root. */
function findThreadForItem(
  forest: ThreadNode[],
  targetId: string,
): ThreadNode[] {
  const findRoot = (nodes: ThreadNode[]): ThreadNode | null => {
    for (const node of nodes) {
      if (node.item.id === targetId) return node;
      const found = findRoot(node.children);
      if (found) return node; // return the top-level ancestor
    }
    return null;
  };
  const root = findRoot(forest);
  if (!root) return [];
  // Only show thread if there are actually replies
  if (root.children.length === 0 && root.item.id === targetId) return [];
  return [root];
}

function useReasonDialog() {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState<{
    id: string;
    action: ModerateAction["action"];
  } | null>(null);

  function prompt(id: string, action: ModerateAction["action"]) {
    setPending({ id, action });
    setReason("");
    setOpen(true);
  }

  function close() {
    setOpen(false);
    setPending(null);
    setReason("");
  }

  return { open, reason, setReason, pending, prompt, close };
}

function ReasonDialog({
  dialog,
  onConfirm,
  isPending,
}: {
  dialog: ReturnType<typeof useReasonDialog>;
  onConfirm: (
    id: string,
    action: ModerateAction["action"],
    reason: string,
  ) => void;
  isPending: boolean;
}) {
  const { t } = useI18n();
  return (
    <Dialog
      open={dialog.open}
      onOpenChange={(v) => {
        if (!v) dialog.close();
      }}
    >
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="capitalize">
            {dialog.pending?.action} Item
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label>{t("moderation.reason")}</Label>
            <Input
              value={dialog.reason}
              onChange={(e) => dialog.setReason(e.target.value)}
              placeholder={t("moderation.enterReason")}
            />
          </div>
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={() => dialog.close()}>
              {t("common.cancel")}
            </Button>
            <Button
              variant={
                dialog.pending?.action === "delete" ? "destructive" : "default"
              }
              onClick={() => {
                if (dialog.pending)
                  onConfirm(
                    dialog.pending.id,
                    dialog.pending.action,
                    dialog.reason,
                  );
              }}
              disabled={isPending}
            >
              {t("common.confirm")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ModerationHistory({
  item,
  titleMap,
}: {
  item: ModerationRecord;
  titleMap?: TitleMap;
}) {
  const { t, lang } = useI18n();
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <History className="h-3 w-3" />
        <span>{t("moderation.currentStatus")}</span>
        <StatusBadge status={normalizeModerationStatus(item.status)} />
      </div>
      <dl className="grid gap-x-4 gap-y-2 text-xs grid-cols-2">
        <div className="space-y-1">
          <dt className="text-muted-foreground">{t("moderation.source")}</dt>
          <dd>{getModerationSource(item)}</dd>
        </div>
        <div className="space-y-1">
          <dt className="text-muted-foreground">{t("moderation.path")}</dt>
          <dd className="break-all">
            {getModerationPath(item, lang, titleMap)}
          </dd>
        </div>
        <div className="space-y-1">
          <dt className="text-muted-foreground">{t("common.author")}</dt>
          <dd>{getModerationAuthor(item, t("moderation.guest"))}</dd>
        </div>
        <div className="space-y-1">
          <dt className="text-muted-foreground">{t("common.email")}</dt>
          <dd>{getModerationEmail(item)}</dd>
        </div>
        <div className="space-y-1">
          <dt className="text-muted-foreground">{t("moderation.updated")}</dt>
          <dd>{formatDate(item.updated_at)}</dd>
        </div>
      </dl>
      <div className="rounded-lg border bg-muted/40 p-3 text-sm whitespace-pre-wrap break-words">
        {getModerationBody(item) || t("common.noData")}
      </div>
    </div>
  );
}

function ThreadTree({
  nodes,
  activeId,
  onSelect,
  titleMap,
}: {
  nodes: ThreadNode[];
  activeId: string | null;
  onSelect: (id: string) => void;
  titleMap?: TitleMap;
}) {
  const { t, lang } = useI18n();

  if (!nodes.length) {
    return (
      <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
        {t("common.noData")}
      </div>
    );
  }

  const renderNode = (node: ThreadNode, depth: number) => (
    <div key={node.item.id} className="space-y-2">
      <button
        type="button"
        className={[
          "w-full rounded-lg border p-3 text-left transition-colors",
          activeId === node.item.id
            ? "border-primary bg-primary/5"
            : "hover:bg-muted/60",
        ].join(" ")}
        onClick={() => onSelect(node.item.id)}
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium">
            {getModerationAuthor(node.item, t("moderation.guest"))}
          </span>
          <StatusBadge status={normalizeModerationStatus(node.item.status)} />
          <Badge variant="outline">{getModerationSurface(node.item)}</Badge>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
          <span className="break-all">
            {getModerationPath(node.item, lang, titleMap)}
          </span>
          <span className="shrink-0 before:content-['·'] before:mr-1.5">
            {formatDate(node.item.created_at)}
          </span>
        </div>
        <div className="mt-2 line-clamp-3 text-sm text-foreground/90">
          {getModerationBody(node.item) || t("common.noData")}
        </div>
      </button>
      {node.children.length > 0 && (
        <div className="space-y-2 pl-4 border-l">
          {node.children.map((child) => renderNode(child, depth + 1))}
        </div>
      )}
      {depth === 0 && <div className="h-1" />}
    </div>
  );

  return (
    <div className="space-y-3">{nodes.map((node) => renderNode(node, 0))}</div>
  );
}

function ModerationStats({
  total,
  items,
}: {
  total: number;
  items: ModerationRecord[];
}) {
  const { t } = useI18n();
  const counts = useMemo(() => {
    const summary = { pending: 0, approved: 0, rejected: 0 };
    for (const item of items) {
      const status = normalizeModerationStatus(item.status);
      if (status === "pending") summary.pending += 1;
      if (status === "approved") summary.approved += 1;
      if (status === "rejected") summary.rejected += 1;
    }
    return summary;
  }, [items]);

  const cards = [
    {
      label: t("moderation.statTotal"),
      value: total,
      tone: "default" as const,
    },
    {
      label: t("moderation.statPending"),
      value: counts.pending,
      tone: "warning" as const,
    },
    {
      label: t("moderation.statApproved"),
      value: counts.approved,
      tone: "success" as const,
    },
    {
      label: t("moderation.statRejected"),
      value: counts.rejected,
      tone: "destructive" as const,
    },
  ];

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.label}>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm text-muted-foreground">{card.label}</p>
                <p className="mt-2 text-3xl font-semibold tracking-tight">
                  {card.value}
                </p>
              </div>
              <Badge variant={card.tone}>{card.label}</Badge>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

const SORT_LABELS: Record<string, string> = {
  created_desc: "最新优先",
  created_asc: "最早优先",
  status: "按状态",
  path: "按路径",
};

function FiltersBar({
  kind,
  filters,
  setFilters,
  onApply,
  onReset,
}: {
  kind: ModerationKind;
  filters: ModerationFilters;
  setFilters: (next: ModerationFilters) => void;
  onApply: () => void;
  onReset: () => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const surfaceOptions =
    kind === "comments" ? COMMENT_SURFACE_OPTIONS : GUESTBOOK_SURFACE_OPTIONS;

  const activeCount = [
    filters.keyword,
    filters.author,
    filters.email,
    filters.path,
    filters.surface,
    filters.status,
  ].filter(Boolean).length;

  const update = (key: keyof ModerationFilters, value: string) => {
    setFilters({ ...filters, [key]: value });
  };

  return (
    <div className="mt-4 space-y-2">
      <Button
        variant="outline"
        className="w-full justify-between"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4" />
          {t("moderation.searchTitle")}
          {activeCount > 0 && (
            <Badge variant="secondary" className="ml-1">
              {activeCount}
            </Badge>
          )}
        </span>
        <ChevronDown
          className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </Button>

      {open && (
        <Card>
          <CardContent className="pt-4">
            <form
              className="space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                onApply();
                setOpen(false);
              }}
            >
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <div className="space-y-1">
                  <Label>{t("moderation.searchKeyword")}</Label>
                  <Input
                    value={filters.keyword}
                    onChange={(e) => update("keyword", e.target.value)}
                    placeholder={t("common.search")}
                  />
                </div>
                <div className="space-y-1">
                  <Label>{t("moderation.searchAuthor")}</Label>
                  <Input
                    value={filters.author}
                    onChange={(e) => update("author", e.target.value)}
                    placeholder={t("common.author")}
                  />
                </div>
                <div className="space-y-1">
                  <Label>{t("moderation.searchEmail")}</Label>
                  <Input
                    value={filters.email}
                    onChange={(e) => update("email", e.target.value)}
                    placeholder="mail@example.com"
                  />
                </div>
                <div className="space-y-1">
                  <Label>{t("moderation.searchPath")}</Label>
                  <Input
                    value={filters.path}
                    onChange={(e) => update("path", e.target.value)}
                    placeholder="/posts/slug"
                  />
                </div>
                <div className="space-y-1">
                  <Label>{t("moderation.searchSurface")}</Label>
                  <select
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={filters.surface}
                    onChange={(e) => update("surface", e.target.value)}
                  >
                    {surfaceOptions.map((option) => (
                      <option key={option || "all"} value={option}>
                        {option || t("common.all")}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <Label>{t("moderation.searchStatus")}</Label>
                  <select
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={filters.status}
                    onChange={(e) => update("status", e.target.value)}
                  >
                    {STATUS_OPTIONS.map((option) => (
                      <option key={option || "all"} value={option}>
                        {option || t("common.all")}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <Label>{t("moderation.searchSort")}</Label>
                  <select
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={filters.sort}
                    onChange={(e) => update("sort", e.target.value)}
                  >
                    {SORT_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {SORT_LABELS[option] ?? option}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button type="submit" size="sm">
                  <Search className="mr-1.5 h-3.5 w-3.5" />
                  {t("moderation.searchApply")}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    onReset();
                    setOpen(false);
                  }}
                >
                  <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                  {t("moderation.searchReset")}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function ModerationQueue({
  kind,
  title,
  description,
  loadItems,
  moderateItem,
  queryKeyFn,
}: {
  kind: ModerationKind;
  title: string;
  description: string;
  loadItems: (
    params: ModerationListParams,
  ) => Promise<any>;
  moderateItem: (
    id: string,
    payload: ModerateAction,
  ) => Promise<any>;
  queryKeyFn: (params?: any) => readonly unknown[];
}) {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<ModerationFilters>(DEFAULT_FILTERS);
  const [draft, setDraft] = useState<ModerationFilters>(DEFAULT_FILTERS);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [bulkPending, setBulkPending] = useState(false);
  const dialog = useReasonDialog();

  const params = useMemo<ModerationListParams>(
    () => ({
      page,
      page_size: PAGE_SIZE,
      status: filters.status || undefined,
      path: filters.path || undefined,
      surface: filters.surface || undefined,
      keyword: filters.keyword || undefined,
      author: filters.author || undefined,
      email: filters.email || undefined,
      sort: filters.sort || undefined,
    }),
    [page, filters],
  );

  const { data: raw, isLoading } = useQuery({
    queryKey: queryKeyFn(params),
    queryFn: () => loadItems(params),
  });
  const data = raw?.data;

  const moderate = useMutation({
    mutationFn: ({
      id,
      action,
      reason,
    }: {
      id: string;
      action: ModerateAction["action"];
      reason?: string;
    }) => moderateItem(id, { action, reason: reason || null }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeyFn() });
      dialog.close();
      toast.success(t("common.operationSuccess"));
    },
    onError: (error: any) => {
      const msg = error?.response?.data?.detail || t("common.operationFailed");
      toast.error(msg);
    },
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const titleMap = useContentTitles(items);
  const selectedItem = items.find((item) => item.id === activeId) ?? null;
  const treeNodes = useMemo(() => buildThreadForest(items), [items]);
  const activeThread = useMemo(
    () => (activeId ? findThreadForItem(treeNodes, activeId) : []),
    [treeNodes, activeId],
  );

  useEffect(() => {
    setSelectedIds((current) =>
      current.filter((id) => items.some((item) => item.id === id)),
    );
    if (!items.some((item) => item.id === activeId)) {
      setActiveId(items[0]?.id ?? null);
    }
  }, [items, activeId]);

  const applyFilters = () => {
    setFilters({ ...draft });
    setPage(1);
    setSelectedIds([]);
    setActiveId(null);
  };

  const resetFilters = () => {
    setDraft(DEFAULT_FILTERS);
    setFilters(DEFAULT_FILTERS);
    setPage(1);
    setSelectedIds([]);
    setActiveId(null);
  };

  const toggleSelection = (id: string, checked: boolean) => {
    setSelectedIds((current) => {
      if (checked) {
        return current.includes(id) ? current : [...current, id];
      }
      return current.filter((itemId) => itemId !== id);
    });
  };

  const selectCurrentPage = () => {
    setSelectedIds(items.map((item) => item.id));
  };

  const runBulkAction = async (action: ModerateAction["action"]) => {
    if (!selectedIds.length || bulkPending) return;
    setBulkPending(true);
    try {
      for (const id of selectedIds) {
        // sequential by design: we reuse the existing single-item endpoint and keep the UI honest
        // until a batch endpoint exists on the backend.
        // eslint-disable-next-line no-await-in-loop
        await moderateItem(id, { action, reason: null });
      }
      await queryClient.invalidateQueries({ queryKey: queryKeyFn() });
      setSelectedIds([]);
    } finally {
      setBulkPending(false);
    }
  };

  return (
    <div className="mt-4 space-y-4">
      <div className="rounded-lg border bg-muted/20 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold">{title}</p>
            <p className="text-xs text-muted-foreground">{description}</p>
          </div>
          <Badge variant="outline">
            {t("moderation.currentPage")} {page}
          </Badge>
        </div>
        <div className="mt-3">
          <ModerationStats total={total} items={items} />
        </div>
      </div>

      <FiltersBar
        kind={kind}
        filters={draft}
        setFilters={setDraft}
        onApply={applyFilters}
        onReset={resetFilters}
      />

      <div className="flex flex-col gap-3 rounded-lg border bg-muted/30 p-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="secondary">
            {selectedIds.length} {t("common.items")}
          </Badge>
          <span className="text-xs text-muted-foreground hidden sm:inline">
            {t("moderation.bulkNote")}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Button variant="outline" size="sm" onClick={selectCurrentPage}>
            {t("moderation.selectCurrentPage")}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSelectedIds([])}
            disabled={!selectedIds.length}
          >
            {t("common.clear")}
          </Button>
          <Button
            size="sm"
            onClick={() => void runBulkAction("approve")}
            disabled={moderate.isPending || bulkPending || !selectedIds.length}
          >
            <Check className="mr-1 h-3.5 w-3.5" />
            {t("moderation.bulkApprove")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void runBulkAction("reject")}
            disabled={moderate.isPending || bulkPending || !selectedIds.length}
          >
            <X className="mr-1 h-3.5 w-3.5" />
            {t("moderation.bulkReject")}
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => void runBulkAction("delete")}
            disabled={moderate.isPending || bulkPending || !selectedIds.length}
          >
            <Trash2 className="mr-1 h-3.5 w-3.5" />
            {t("moderation.bulkDelete")}
          </Button>
        </div>
      </div>

      <div className="space-y-3">
        <ReasonDialog
          dialog={dialog}
          onConfirm={(id, action, reason) =>
            moderate.mutate({ id, action, reason })
          }
          isPending={moderate.isPending}
        />
        <div className="rounded-lg border">
          <DataTable<ModerationRecord>
            columns={[
              {
                header: "",
                accessor: (row) => (
                  <div onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-border"
                      checked={selectedIds.includes(row.id)}
                      onChange={(e) =>
                        toggleSelection(row.id, e.target.checked)
                      }
                    />
                  </div>
                ),
                className: "w-10",
              },
              {
                header: t("common.author"),
                accessor: (row) => (
                  <span className="whitespace-nowrap font-medium">
                    {getModerationAuthor(row, t("moderation.guest"))}
                  </span>
                ),
              },
              {
                header: t("moderation.source"),
                accessor: (row) => (
                  <Badge variant="outline">{getModerationSource(row)}</Badge>
                ),
                className: "hidden md:table-cell",
              },
              {
                header: t("common.body"),
                accessor: (row) => (
                  <span className="line-clamp-2 text-xs">
                    {getModerationBody(row)}
                  </span>
                ),
              },
              {
                header: t("common.status"),
                accessor: (row) => (
                  <StatusBadge status={normalizeModerationStatus(row.status)} />
                ),
              },
              {
                header: t("moderation.time"),
                accessor: (row) => (
                  <span className="whitespace-nowrap text-xs">
                    {formatDate(row.created_at)}
                  </span>
                ),
                className: "hidden sm:table-cell",
              },
              {
                header: t("common.actions"),
                accessor: (row) => (
                  <div className="flex gap-0.5">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => {
                        e.stopPropagation();
                        dialog.prompt(row.id, "approve");
                      }}
                      title={t("moderation.approve")}
                    >
                      <Check className="h-4 w-4 text-green-600" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => {
                        e.stopPropagation();
                        dialog.prompt(row.id, "reject");
                      }}
                      title={t("moderation.reject")}
                    >
                      <X className="h-4 w-4 text-orange-600" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => {
                        e.stopPropagation();
                        dialog.prompt(row.id, "delete");
                      }}
                      title={t("common.delete")}
                    >
                      <Trash2 className="h-4 w-4 text-red-600" />
                    </Button>
                  </div>
                ),
                className: "w-28",
              },
            ]}
            data={items}
            total={total}
            page={page}
            pageSize={data?.page_size ?? PAGE_SIZE}
            onPageChange={(nextPage) => {
              setPage(nextPage);
              setSelectedIds([]);
              setActiveId(null);
            }}
            isLoading={isLoading}
            onRowClick={(row) =>
              setActiveId((prev) => (prev === row.id ? null : row.id))
            }
          />
        </div>

        {selectedItem && (
          <Card>
            <CardContent className="pt-4 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-medium">
                    {getModerationAuthor(selectedItem, t("moderation.guest"))}
                  </span>
                  <StatusBadge
                    status={normalizeModerationStatus(selectedItem.status)}
                  />
                  <Badge variant="outline">
                    {getModerationSource(selectedItem)}
                  </Badge>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setActiveId(null)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div>
                  <dt className="text-muted-foreground">
                    {t("moderation.path")}
                  </dt>
                  <dd className="break-all mt-0.5">
                    {getModerationPath(selectedItem, lang, titleMap)}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">{t("common.email")}</dt>
                  <dd className="mt-0.5">{getModerationEmail(selectedItem)}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">
                    {t("moderation.updated")}
                  </dt>
                  <dd className="mt-0.5">
                    {formatDate(selectedItem.updated_at)}
                  </dd>
                </div>
              </div>

              <div className="rounded-lg border bg-muted/40 p-3 text-sm whitespace-pre-wrap break-words">
                {getModerationBody(selectedItem) || t("common.noData")}
              </div>

              {activeThread.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <History className="h-4 w-4" />
                    {t("moderation.thread")}
                  </div>
                  <ThreadTree
                    nodes={activeThread}
                    activeId={selectedItem.id}
                    onSelect={setActiveId}
                    titleMap={titleMap}
                  />
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

export default function ModerationPage() {
  const { t } = useI18n();
  return (
    <div>
      <PageHeader
        title={t("moderation.title")}
        description={t("moderation.description")}
      />
      <Card className="mt-4">
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold">
            {t("siteConfig.community")}
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          {t("moderation.unifiedNote")}
        </CardContent>
      </Card>
      <Tabs defaultValue="comments">
        <TabsList>
          <TabsTrigger value="comments">{t("moderation.comments")}</TabsTrigger>
          <TabsTrigger value="guestbook">
            {t("moderation.guestbook")}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="comments">
          <ModerationQueue
            kind="comments"
            title={t("moderation.comments")}
            description={t("moderation.unifiedNote")}
            loadItems={(params) =>
              listCommentsApiV1AdminModerationCommentsGet(params) as Promise<any>
            }
            moderateItem={(id, payload) =>
              moderateCommentApiV1AdminModerationCommentsCommentIdModeratePost(id, payload) as Promise<any>
            }
            queryKeyFn={(params?) => getListCommentsApiV1AdminModerationCommentsGetQueryKey(params)}
          />
        </TabsContent>
        <TabsContent value="guestbook">
          <ModerationQueue
            kind="guestbook"
            title={t("moderation.guestbook")}
            description={t("moderation.unifiedNote")}
            loadItems={(params) =>
              listGuestbookApiV1AdminModerationGuestbookGet(params) as Promise<any>
            }
            moderateItem={(id, payload) =>
              moderateGuestbookApiV1AdminModerationGuestbookEntryIdModeratePost(id, payload) as Promise<any>
            }
            queryKeyFn={(params?) => getListGuestbookApiV1AdminModerationGuestbookGetQueryKey(params)}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
