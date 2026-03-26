import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import type { Components } from "react-markdown";
import {
  listCommentsApiV1AdminModerationCommentsGet,
  listGuestbookApiV1AdminModerationGuestbookGet,
  moderateCommentEndpointApiV1AdminModerationCommentsCommentIdModeratePost as moderateCommentApiV1AdminModerationCommentsCommentIdModeratePost,
  moderateGuestbookEndpointApiV1AdminModerationGuestbookEntryIdModeratePost as moderateGuestbookApiV1AdminModerationGuestbookEntryIdModeratePost,
  getListCommentsApiV1AdminModerationCommentsGetQueryKey,
  getListGuestbookApiV1AdminModerationGuestbookGetQueryKey,
  listPosts,
  listDiary,
  listThoughts,
  listExcerpts,
} from "@serino/api-client/admin";
import type {
  ListCommentsApiV1AdminModerationCommentsGetParams,
  ListGuestbookApiV1AdminModerationGuestbookGetParams,
  CommentAdminRead,
  GuestbookAdminRead,
  ModerateAction,
} from "@serino/api-client/models";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/Tabs";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { cn, formatDate } from "@/lib/utils";
import {
  Check,
  History,
  RotateCcw,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { useI18n } from "@/i18n";
import { toast } from "sonner";

import { PAGE_KEY_LABELS, optionLabel } from "@/pages/site-config/constants";

type ModerationRecord = CommentAdminRead | GuestbookAdminRead;
type ModerationKind = "comments" | "guestbook";
type ModerationListParams = ListCommentsApiV1AdminModerationCommentsGetParams & ListGuestbookApiV1AdminModerationGuestbookGetParams;

const envApiBaseUrl =
  (typeof __AERISUN_API_BASE_URL__ === "string" ? __AERISUN_API_BASE_URL__ : "").replace(
    /\/+$/,
    "",
  );

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

const EMPTY_MODERATION_ITEMS: ModerationRecord[] = [];

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

function resolveModerationMediaSrc(src?: string) {
  if (!src) return src;
  if (!src.startsWith("/")) return src;
  if (!envApiBaseUrl) return src;

  try {
    return new URL(src, envApiBaseUrl).toString();
  } catch {
    return src;
  }
}

const moderationPreviewComponents: Components = {
  a: ({ children, href, ...props }) => (
    <a
      href={href}
      className="font-medium text-foreground underline decoration-border underline-offset-4 transition-colors hover:text-primary"
      target={href?.startsWith("http") ? "_blank" : undefined}
      rel={href?.startsWith("http") ? "noopener noreferrer" : undefined}
      {...props}
    >
      {children}
    </a>
  ),
  img: ({ src, alt, ...props }) => (
    <img
      src={resolveModerationMediaSrc(src)}
      alt={alt}
      className="my-4 block h-auto max-w-full rounded-2xl border border-white/10 shadow-[0_18px_40px_rgba(15,23,42,0.18)]"
      style={{ width: "auto", maxWidth: "min(100%, 28rem)" }}
      loading="lazy"
      {...props}
    />
  ),
  pre: ({ children, ...props }) => (
    <pre
      className="my-4 overflow-x-auto rounded-2xl border border-white/10 bg-background/70 px-4 py-3 text-[13px]"
      {...props}
    >
      {children}
    </pre>
  ),
  code: ({ inline, children, ...props }: any) =>
    inline ? (
      <code
        className="rounded-md bg-background/80 px-1.5 py-0.5 text-[0.9em] text-foreground"
        {...props}
      >
        {children}
      </code>
    ) : (
      <code {...props}>{children}</code>
    ),
  blockquote: ({ children, ...props }) => (
    <blockquote
      className="my-4 rounded-r-xl border-l-2 border-primary/30 bg-background/45 px-4 py-3 text-foreground/80"
      {...props}
    >
      {children}
    </blockquote>
  ),
};

function ModerationBodyPreview({ content }: { content: string }) {
  const { t } = useI18n();

  if (!content.trim()) {
    return (
      <div className="rounded-xl border border-dashed bg-muted/20 px-4 py-5 text-sm text-muted-foreground">
        {t("common.noData")}
      </div>
    );
  }

  return (
    <div className="rounded-2xl border bg-muted/35 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          {t("common.preview")}
        </span>
      </div>
      <div className="prose prose-sm dark:prose-invert max-w-none text-foreground/85 [&>:first-child]:mt-0 [&>:last-child]:mb-0">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeHighlight]}
          components={moderationPreviewComponents}
        >
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
}

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

function getModerationSource(item: ModerationRecord, lang: "zh" | "en" = "zh") {
  if ("source" in item && item.source) return item.source;
  if ("content_type" in item && item.content_type) {
    return optionLabel(PAGE_KEY_LABELS, item.content_type, lang);
  }
  if ("website" in item) return optionLabel(PAGE_KEY_LABELS, "guestbook", lang);
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
          <dd>{getModerationSource(item, lang)}</dd>
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
      <ModerationBodyPreview content={getModerationBody(item)} />
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
    <div className="grid gap-2.5 grid-cols-2 xl:grid-cols-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className={cn(
            "rounded-2xl border border-border/45 bg-background/45 px-4 py-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)] backdrop-blur-sm",
            card.tone === "success" && "border-emerald-500/20 bg-emerald-500/[0.05]",
            card.tone === "warning" && "border-amber-500/20 bg-amber-500/[0.05]",
            card.tone === "destructive" && "border-rose-500/20 bg-rose-500/[0.05]",
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground/85">
                {card.label}
              </p>
              <p className="mt-3 text-3xl font-semibold tracking-tight">
                {card.value}
              </p>
            </div>
            <Badge variant={card.tone} className="shrink-0">
              {card.label}
            </Badge>
          </div>
        </div>
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

  const renderSelect = (
    label: string,
    value: string,
    onChange: (nextValue: string) => void,
    options: Array<{ value: string; label: string }>,
  ) => (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Select value={value || "__all"} onValueChange={(nextValue) => onChange(nextValue === "__all" ? "" : nextValue)}>
        <SelectTrigger className="h-10 rounded-xl border-border/45 bg-background/70 px-3 text-sm">
          <SelectValue placeholder={t("common.all")} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__all">{t("common.all")}</SelectItem>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );

  return (
    <CollapsibleSection
      title={t("moderation.searchTitle")}
      defaultOpen={false}
      badge={activeCount > 0 ? `${activeCount}` : undefined}
      className="rounded-2xl border border-border/40 bg-muted/[0.16] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]"
    >
      <div className="space-y-4">
        <p className="text-xs text-muted-foreground">
          只保留真正需要的筛选条件，避免审核页过重。
        </p>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            onApply();
          }}
        >
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div className="space-y-1.5">
              <Label>{t("moderation.searchKeyword")}</Label>
              <Input
                value={filters.keyword}
                onChange={(e) => update("keyword", e.target.value)}
                placeholder={t("common.search")}
                className="border-border/45 bg-background/70"
              />
            </div>
            <div className="space-y-1.5">
              <Label>{t("moderation.searchAuthor")}</Label>
              <Input
                value={filters.author}
                onChange={(e) => update("author", e.target.value)}
                placeholder={t("common.author")}
                className="border-border/45 bg-background/70"
              />
            </div>
            <div className="space-y-1.5">
              <Label>{t("moderation.searchEmail")}</Label>
              <Input
                value={filters.email}
                onChange={(e) => update("email", e.target.value)}
                placeholder="mail@example.com"
                className="border-border/45 bg-background/70"
              />
            </div>
            <div className="space-y-1.5">
              <Label>{t("moderation.searchPath")}</Label>
              <Input
                value={filters.path}
                onChange={(e) => update("path", e.target.value)}
                placeholder="/posts/slug"
                className="border-border/45 bg-background/70"
              />
            </div>
            {renderSelect(
              t("moderation.searchSurface"),
              filters.surface,
              (nextValue) => update("surface", nextValue),
              surfaceOptions.filter(Boolean).map((option) => ({
                value: option,
                label: option || t("common.all"),
              })),
            )}
            {renderSelect(
              t("moderation.searchStatus"),
              filters.status,
              (nextValue) => update("status", nextValue),
              STATUS_OPTIONS.filter(Boolean).map((option) => ({
                value: option,
                label: option || t("common.all"),
              })),
            )}
            {renderSelect(
              t("moderation.searchSort"),
              filters.sort,
              (nextValue) => update("sort", nextValue),
              SORT_OPTIONS.map((option) => ({
                value: option,
                label: SORT_LABELS[option] ?? option,
              })),
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button type="submit" size="sm" className="rounded-xl">
              <Search className="mr-1.5 h-3.5 w-3.5" />
              {t("moderation.searchApply")}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="rounded-xl border-border/45 bg-background/50"
              onClick={onReset}
            >
              <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
              {t("moderation.searchReset")}
            </Button>
          </div>
        </form>
      </div>
    </CollapsibleSection>
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
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

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
      setDeleteTargetId(null);
      toast.success(t("common.operationSuccess"));
    },
    onError: (error: any) => {
      const msg = error?.response?.data?.detail || t("common.operationFailed");
      toast.error(msg);
    },
  });

  const items = data?.items ?? EMPTY_MODERATION_ITEMS;
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
        await moderateItem(id, { action, reason: null });
      }
      await queryClient.invalidateQueries({ queryKey: queryKeyFn() });
      setSelectedIds([]);
    } finally {
      setBulkPending(false);
    }
  };

  return (
    <div className="mt-4 space-y-5">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <p className="text-sm font-semibold tracking-[0.01em]">{title}</p>
            <p className="text-xs text-muted-foreground">
              {t("moderation.currentPage")} {page}
            </p>
          </div>
        </div>
        <ModerationStats total={total} items={items} />
      </div>

      <div className="grid gap-4 xl:grid-cols-2 xl:items-start">
        <div className="space-y-4">
          <FiltersBar
            kind={kind}
            filters={draft}
            setFilters={setDraft}
            onApply={applyFilters}
            onReset={resetFilters}
          />

          <ConfirmDialog
            open={deleteTargetId !== null}
            onConfirm={() => {
              if (deleteTargetId) {
                moderate.mutate({ id: deleteTargetId, action: "delete" });
              }
            }}
            onCancel={() => setDeleteTargetId(null)}
            title={t("moderation.deleteConfirm")}
            description={t("common.deleteConfirmDesc")}
            confirmLabel={t("common.delete")}
            variant="destructive"
            isPending={moderate.isPending}
          />

          <div className="overflow-hidden rounded-3xl border border-border/35 bg-background/55 shadow-[0_20px_50px_-44px_rgba(15,23,42,0.55)] ring-1 ring-white/5">
            <div className="flex flex-col gap-3 border-b border-border/25 px-4 py-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="rounded-full">
                  {selectedIds.length} {t("common.items")}
                </Badge>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-xl border-border/45 bg-background/50"
                  onClick={selectCurrentPage}
                >
                  {t("moderation.selectCurrentPage")}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="rounded-xl"
                  onClick={() => setSelectedIds([])}
                  disabled={!selectedIds.length}
                >
                  {t("common.clear")}
                </Button>
                <Button
                  size="sm"
                  className="rounded-xl"
                  onClick={() => void runBulkAction("approve")}
                  disabled={moderate.isPending || bulkPending || !selectedIds.length}
                >
                  <Check className="mr-1 h-3.5 w-3.5" />
                  {t("moderation.bulkApprove")}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-xl border-border/45 bg-background/50"
                  onClick={() => void runBulkAction("reject")}
                  disabled={moderate.isPending || bulkPending || !selectedIds.length}
                >
                  <X className="mr-1 h-3.5 w-3.5" />
                  {t("moderation.bulkReject")}
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  className="rounded-xl"
                  onClick={() => void runBulkAction("delete")}
                  disabled={moderate.isPending || bulkPending || !selectedIds.length}
                >
                  <Trash2 className="mr-1 h-3.5 w-3.5" />
                  {t("moderation.bulkDelete")}
                </Button>
              </div>
            </div>

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
                    <Badge variant="outline">{getModerationSource(row, lang)}</Badge>
                  ),
                  className: "hidden md:table-cell",
                },
                {
                  header: t("common.status"),
                  accessor: (row) => (
                    <StatusBadge status={normalizeModerationStatus(row.status)} />
                  ),
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
                          moderate.mutate({ id: row.id, action: "approve" });
                        }}
                        title={t("moderation.approve")}
                        disabled={moderate.isPending}
                      >
                        <Check className="h-4 w-4 text-green-600" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={(e) => {
                          e.stopPropagation();
                          moderate.mutate({ id: row.id, action: "reject" });
                        }}
                        title={t("moderation.reject")}
                        disabled={moderate.isPending}
                      >
                        <X className="h-4 w-4 text-orange-600" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteTargetId(row.id);
                        }}
                        title={t("common.delete")}
                        disabled={moderate.isPending}
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
        </div>

        <div className="xl:sticky xl:top-6">
          <Card className="rounded-3xl border border-border/35 bg-gradient-to-b from-background via-background to-muted/20 shadow-[0_22px_54px_-40px_rgba(15,23,42,0.6)] backdrop-blur-sm">
            <CardContent className="space-y-4 pt-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground/70">
                    {t("moderation.detail")}
                  </p>
                  <h3 className="mt-1 text-base font-semibold tracking-tight">
                    {selectedItem
                      ? getModerationAuthor(selectedItem, t("moderation.guest"))
                      : t("moderation.noSelection")}
                  </h3>
                </div>
                {selectedItem ? null : (
                  <Badge variant="secondary" className="rounded-full">
                    {t("common.noData")}
                  </Badge>
                )}
              </div>

              {selectedItem ? (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">
                      {getModerationAuthor(selectedItem, t("moderation.guest"))}
                    </span>
                    <StatusBadge
                      status={normalizeModerationStatus(selectedItem.status)}
                    />
                    <Badge variant="outline">
                      {getModerationSource(selectedItem, lang)}
                    </Badge>
                  </div>

                  <div className="grid grid-cols-1 gap-3 text-xs sm:grid-cols-2">
                    <div className="rounded-2xl border border-border/30 bg-background/65 px-3 py-3">
                      <dt className="text-muted-foreground">
                        {t("moderation.path")}
                      </dt>
                      <dd className="mt-1 break-all text-foreground/90">
                        {getModerationPath(selectedItem, lang, titleMap)}
                      </dd>
                    </div>
                    <div className="rounded-2xl border border-border/30 bg-background/65 px-3 py-3">
                      <dt className="text-muted-foreground">{t("common.email")}</dt>
                      <dd className="mt-1 text-foreground/90">
                        {getModerationEmail(selectedItem)}
                      </dd>
                    </div>
                    <div className="rounded-2xl border border-border/30 bg-background/65 px-3 py-3 sm:col-span-2">
                      <dt className="text-muted-foreground">
                        {t("moderation.updated")}
                      </dt>
                      <dd className="mt-1 text-foreground/90">
                        {formatDate(selectedItem.updated_at)}
                      </dd>
                    </div>
                  </div>

                  <ModerationBodyPreview content={getModerationBody(selectedItem)} />

                  {activeThread.length > 0 && (
                    <div className="space-y-2 pt-1">
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
                </>
              ) : (
                <div className="rounded-2xl border border-dashed border-border/45 bg-background/60 px-4 py-8 text-sm text-muted-foreground">
                  {t("moderation.noSelection")}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

export default function ModerationPage() {
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState<ModerationKind>("comments");

  return (
    <Tabs
      value={activeTab}
      onValueChange={(value) =>
        setActiveTab(value === "guestbook" ? "guestbook" : "comments")
      }
      className="space-y-0"
    >
      <div className="mb-6 rounded-3xl border border-border/35 bg-gradient-to-br from-muted/25 via-background to-background px-5 py-5 shadow-[0_22px_60px_-46px_rgba(15,23,42,0.55)]">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="space-y-1.5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-muted-foreground/70">
              {t("moderation.title")}
            </p>
            <h1 className="text-[2.15rem] font-semibold tracking-tight">
              {t("moderation.title")}
            </h1>
            <p className="text-sm text-muted-foreground">
              {t("moderation.description")}
            </p>
          </div>
          <TabsList className="inline-flex h-12 items-center self-start rounded-2xl border border-border/45 bg-background/75 p-1.5 text-muted-foreground shadow-[0_16px_40px_-26px_rgba(15,23,42,0.55)] backdrop-blur-sm md:self-auto">
            <TabsTrigger
              value="comments"
              className="group h-9 rounded-xl border border-transparent px-4 text-sm font-medium tracking-[0.01em] transition-all data-[state=active]:border-transparent data-[state=active]:bg-foreground data-[state=active]:text-background data-[state=active]:shadow-[0_10px_24px_rgba(15,23,42,0.18),0_0_0_1px_rgba(56,189,248,0.38),0_0_0_3px_rgba(45,212,191,0.18)]"
            >
              <span className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-current/70 opacity-70 group-data-[state=active]:opacity-100" />
                {t("moderation.comments")}
              </span>
            </TabsTrigger>
            <TabsTrigger
              value="guestbook"
              className="group h-9 rounded-xl border border-transparent px-4 text-sm font-medium tracking-[0.01em] transition-all data-[state=active]:border-transparent data-[state=active]:bg-foreground data-[state=active]:text-background data-[state=active]:shadow-[0_10px_24px_rgba(15,23,42,0.18),0_0_0_1px_rgba(56,189,248,0.38),0_0_0_3px_rgba(45,212,191,0.18)]"
            >
              <span className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-current/70 opacity-70 group-data-[state=active]:opacity-100" />
                {t("moderation.guestbook")}
              </span>
            </TabsTrigger>
          </TabsList>
        </div>
      </div>
      <TabsContent value="comments">
        <ModerationQueue
          kind="comments"
          title={t("moderation.comments")}
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
  );
}
