import { useEffect, useMemo, useRef, useState, type ComponentProps, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
  CommentAdminRead,
  ContentAdminRead,
  GuestbookAdminRead,
  ListCommentsApiV1AdminModerationCommentsGetParams,
  ListGuestbookApiV1AdminModerationGuestbookGetParams,
  ModerateAction,
  PaginatedResponseCommentAdminRead,
  PaginatedResponseGuestbookAdminRead,
} from "@serino/api-client/models";
import { cn, formatDate } from "@/lib/utils";
import {
  formatContentTypeTitleLabel,
  getContentPathType,
  getContentSlugSearchTerms,
  normalizeContentSlugForMatch,
  type ContentPathType,
} from "@/lib/contentPathLabel";
import { Tabs, TabsContent } from "@/components/ui/Tabs";
import { AdminSegmentedFilter } from "@/components/ui/AdminSegmentedFilter";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { DataTable } from "@/components/DataTable";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { StatusBadge } from "@/components/StatusBadge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/Select";
import {
  Check,
  History,
  RotateCcw,
  Search,
  SlidersHorizontal,
  Trash2,
  X,
} from "lucide-react";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { toast } from "sonner";

import { PAGE_KEY_LABELS, optionLabel } from "@/pages/site-config/constants";

type ModerationRecord = CommentAdminRead | GuestbookAdminRead;
type ModerationKind = "comments" | "guestbook";
type ModerationListParams = ListCommentsApiV1AdminModerationCommentsGetParams & ListGuestbookApiV1AdminModerationGuestbookGetParams;
type ModerationAuthProvider = "email" | "google" | "github";

const envApiBaseUrl =
  (typeof __AERISUN_API_BASE_URL__ === "string" ? __AERISUN_API_BASE_URL__ : "").replace(
    /\/+$/,
    "",
  );

/* slug → title cache, populated by useContentTitles */
type TitleMap = Map<string, string>;

function normalizeModerationSlugForMatch(slug: string) {
  return normalizeContentSlugForMatch(slug);
}

function getModerationSlugSearchTerms(slug: string) {
  return getContentSlugSearchTerms(slug);
}

function getTitleCacheKey(contentType: ContentPathType, slug: string) {
  return `${contentType}/${normalizeModerationSlugForMatch(slug)}`;
}

function getModerationContentTarget(item: ModerationRecord) {
  if (!("content_type" in item) || !item.content_type || !item.content_slug) {
    return null;
  }

  const contentType = getContentPathType(item.content_type);
  if (!contentType) {
    return null;
  }

  return {
    contentType,
    slug: item.content_slug,
  };
}

const contentListFns: Record<
  ContentPathType,
  (p: {
    search: string;
    page_size: number;
  }) => Promise<{ data?: { items?: ContentAdminRead[] } }>
> = {
  posts: (p) => listPosts(p) as Promise<{ data?: { items?: ContentAdminRead[] } }>,
  diary: (p) => listDiary(p) as Promise<{ data?: { items?: ContentAdminRead[] } }>,
  thoughts: (p) => listThoughts(p) as Promise<{ data?: { items?: ContentAdminRead[] } }>,
  excerpts: (p) => listExcerpts(p) as Promise<{ data?: { items?: ContentAdminRead[] } }>,
};

/** Fetch titles for all unique (type, slug) pairs in the current page of items. */
function useContentTitles(items: ModerationRecord[]): TitleMap {
  const [titles, setTitles] = useState<TitleMap>(new Map());
  const cacheRef = useRef<TitleMap>(new Map());

  useEffect(() => {
    const targetsByType = new Map<ContentPathType, Map<string, string>>();

    for (const item of items) {
      const target = getModerationContentTarget(item);
      if (!target) continue;

      const cacheKey = getTitleCacheKey(target.contentType, target.slug);
      if (cacheRef.current.has(cacheKey)) continue;

      const bucket = targetsByType.get(target.contentType) ?? new Map<string, string>();
      bucket.set(cacheKey, target.slug);
      targetsByType.set(target.contentType, bucket);
    }

    if (targetsByType.size === 0) return;

    let cancelled = false;
    (async () => {
      for (const [type, targets] of targetsByType) {
        const listFn = contentListFns[type];
        for (const [cacheKey, slug] of targets) {
          const searchTerms = getModerationSlugSearchTerms(slug);

          for (const term of searchTerms) {
            try {
              const response = await listFn({ search: term, page_size: 10 });
              const entries = response.data?.items ?? [];
              const match = entries.find(
                (entry) => getTitleCacheKey(type, entry.slug) === cacheKey,
              );
              if (match?.title) {
                cacheRef.current.set(cacheKey, match.title);
                break;
              }
            } catch {
              /* ignore */
            }
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
const SORT_OPTIONS = ["created_desc", "created_asc"] as const;

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
  code: ({
    inline,
    children,
    ...props
  }: ComponentProps<"code"> & { inline?: boolean; children?: ReactNode }) =>
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
  const target = getModerationContentTarget(item);
  if (target) {
    return optionLabel(PAGE_KEY_LABELS, target.contentType, lang);
  }
  if ("website" in item) return optionLabel(PAGE_KEY_LABELS, "guestbook", lang);
  return "-";
}

function getModerationPath(
  item: ModerationRecord,
  lang: "zh" | "en" = "zh",
  titleMap?: TitleMap,
) {
  const target = getModerationContentTarget(item);
  if (target) {
    const category = optionLabel(PAGE_KEY_LABELS, target.contentType, lang);
    const title = titleMap?.get(getTitleCacheKey(target.contentType, target.slug));
    return formatContentTypeTitleLabel({
      contentType: target.contentType,
      contentTypeLabel: category,
      title,
      slug: target.slug,
      separator: " / ",
    });
  }

  if ("website" in item) {
    return optionLabel(PAGE_KEY_LABELS, "guestbook", lang);
  }

  return "-";
}

function getModerationEmail(item: ModerationRecord) {
  if ("author_email" in item && item.author_email) return item.author_email;
  if ("mail" in item && item.mail) return item.mail;
  if ("email" in item && item.email) return item.email;
  return "-";
}

function getModerationAuthProvider(item: ModerationRecord): ModerationAuthProvider | null {
  const provider = "auth_provider" in item ? item.auth_provider : null;
  if (provider === "email" || provider === "google" || provider === "github") {
    return provider;
  }
  return getModerationEmail(item) === "-" ? null : "email";
}

function getModerationAuthFieldLabel(lang: "zh" | "en" = "zh") {
  return lang === "en" ? "Authentication" : "认证方式";
}

function getModerationAuthProviderLabel(
  provider: ModerationAuthProvider | null,
  lang: "zh" | "en" = "zh",
) {
  if (provider === "google") return "Google";
  if (provider === "github") return "GitHub";
  if (provider === "email") return lang === "en" ? "Email" : "邮箱";
  return "-";
}

function getModerationAuthDisplay(
  item: ModerationRecord,
  lang: "zh" | "en" = "zh",
) {
  const email = getModerationEmail(item);
  const provider = getModerationAuthProvider(item);
  if (!provider && email === "-") return "-";

  const providerLabel = getModerationAuthProviderLabel(provider, lang);
  if (email === "-") return providerLabel;
  return `${providerLabel} · ${email}`;
}

function getModerationSurface(item: ModerationRecord) {
  if ("page_key" in item && item.page_key) return item.page_key;
  const target = getModerationContentTarget(item);
  if (target) return target.contentType;
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
      className: "border-border/35 bg-background/70 text-foreground",
    },
    {
      label: t("moderation.statPending"),
      value: counts.pending,
      className: "border-amber-500/18 bg-amber-500/[0.08] text-amber-700 dark:text-amber-200",
    },
    {
      label: t("moderation.statApproved"),
      value: counts.approved,
      className: "border-emerald-500/18 bg-emerald-500/[0.08] text-emerald-700 dark:text-emerald-200",
    },
    {
      label: t("moderation.statRejected"),
      value: counts.rejected,
      className: "border-rose-500/18 bg-rose-500/[0.08] text-rose-700 dark:text-rose-200",
    },
  ];

  return (
    <div className="flex max-w-full items-center justify-start gap-2 overflow-x-auto whitespace-nowrap pb-0.5 xl:ml-auto xl:justify-end">
      {cards.map((card) => (
        <span
          key={card.label}
          className={cn(
            "inline-flex shrink-0 items-center gap-2 rounded-full border px-3.5 py-2 text-sm shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]",
            card.className,
          )}
        >
          <span className="text-muted-foreground/95">{card.label}</span>
          <span className="text-base font-semibold tabular-nums">{card.value}</span>
        </span>
      ))}
    </div>
  );
}

const SORT_LABELS: Record<string, string> = {
  created_desc: "最新优先",
  created_asc: "最早优先",
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
  const { t, lang } = useI18n();
  const surfaceOptions =
    kind === "comments" ? COMMENT_SURFACE_OPTIONS : GUESTBOOK_SURFACE_OPTIONS;
  const [open, setOpen] = useState(false);

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

  const summaryItems = [
    filters.keyword
      ? { label: t("moderation.searchKeyword"), value: filters.keyword }
      : null,
    filters.author
      ? { label: t("moderation.searchAuthor"), value: filters.author }
      : null,
    filters.email
      ? { label: t("moderation.searchEmail"), value: filters.email }
      : null,
    filters.path
      ? { label: t("moderation.searchPath"), value: filters.path }
      : null,
    filters.surface
      ? {
          label: t("moderation.searchSurface"),
          value: optionLabel(PAGE_KEY_LABELS, filters.surface, lang),
        }
      : null,
    filters.status
      ? {
          label: t("moderation.searchStatus"),
          value: t(`status.${filters.status}`),
        }
      : null,
  ].filter(Boolean) as Array<{ label: string; value: string }>;

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
    <Dialog open={open} onOpenChange={setOpen}>
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => setOpen(true)}
          className="h-9 rounded-full border-border/45 bg-background/70 px-3.5 shadow-none"
        >
          <SlidersHorizontal className="mr-1.5 h-3.5 w-3.5" />
          {t("moderation.searchTitle")}
          {activeCount > 0 ? (
            <span className="ml-2 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary/12 px-1.5 text-[11px] font-semibold text-primary">
              {activeCount}
            </span>
          ) : null}
        </Button>

        {summaryItems.length > 0 ? (
          summaryItems.map((item) => (
            <span
              key={`${item.label}-${item.value}`}
              className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-border/35 bg-background/70 px-3 py-1.5 text-xs text-foreground/88"
            >
              <span className="text-muted-foreground/75">{item.label}</span>
              <span className="truncate font-medium">{item.value}</span>
            </span>
          ))
        ) : (
          <span className="inline-flex items-center rounded-full border border-dashed border-border/45 bg-background/56 px-3 py-1.5 text-xs text-muted-foreground">
            当前显示全部项目
          </span>
        )}

        <span className="inline-flex items-center rounded-full border border-border/35 bg-background/56 px-3 py-1.5 text-xs text-muted-foreground">
          排序 · {SORT_LABELS[filters.sort] ?? filters.sort}
        </span>

        {activeCount > 0 ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 rounded-full px-3 text-xs"
            onClick={onReset}
          >
            <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
            {t("moderation.searchReset")}
          </Button>
        ) : null}
      </div>

      <DialogContent className="max-w-4xl rounded-[28px] border border-border/35 p-0">
        <div className="border-b border-border/25 px-6 py-5">
          <DialogHeader className="text-left">
            <DialogTitle className="text-xl font-semibold tracking-tight">
              {t("moderation.searchTitle")}
            </DialogTitle>
            <DialogDescription className="text-sm leading-6">
              只保留关键词、作者、邮箱、路径、评论面、状态和排序。
            </DialogDescription>
          </DialogHeader>
        </div>

        <div className="overflow-hidden">
          <form
            className="space-y-6 px-6 py-6"
            onSubmit={(e) => {
              e.preventDefault();
              onApply();
              setOpen(false);
            }}
          >
            <div className="grid gap-6 xl:grid-cols-[1.35fr_0.9fr]">
              <div className="grid gap-4 md:grid-cols-2">
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
              </div>

              <div className="space-y-4">
                {renderSelect(
                  t("moderation.searchSurface"),
                  filters.surface,
                  (nextValue) => update("surface", nextValue),
                  surfaceOptions.filter(Boolean).map((option) => ({
                    value: option,
                    label: optionLabel(PAGE_KEY_LABELS, option, lang),
                  })),
                )}
                {renderSelect(
                  t("moderation.searchStatus"),
                  filters.status,
                  (nextValue) => update("status", nextValue),
                  STATUS_OPTIONS.filter(Boolean).map((option) => ({
                    value: option,
                    label: t(`status.${option}`),
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
            </div>

            <div className="flex flex-col gap-3 border-t border-border/25 pt-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-muted-foreground">
                当前排序:
                <span className="ml-1 font-medium text-foreground">
                  {SORT_LABELS[filters.sort] ?? filters.sort}
                </span>
              </p>

              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="rounded-full border-border/45 bg-background/50 px-4"
                  onClick={() => {
                    onReset();
                    setOpen(false);
                  }}
                >
                  <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                  {t("moderation.searchReset")}
                </Button>
                <Button type="submit" size="sm" className="rounded-full px-4">
                  <Search className="mr-1.5 h-3.5 w-3.5" />
                  {t("moderation.searchApply")}
                </Button>
              </div>
            </div>
          </form>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ModerationQueue({
  kind,
  _description,
  loadItems,
  moderateItem,
  queryKeyFn,
}: {
  kind: ModerationKind;
  loadItems: (
    params: ModerationListParams,
  ) => Promise<{ data?: PaginatedResponseCommentAdminRead | PaginatedResponseGuestbookAdminRead }>;
  moderateItem: (
    id: string,
    payload: ModerateAction,
  ) => Promise<{ data?: ModerationRecord }>;
  queryKeyFn: (params?: ModerationListParams) => readonly unknown[];
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
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
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
        <div className="rounded-2xl border border-border/30 bg-background/55 px-3 py-3 backdrop-blur-sm">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <FiltersBar
              kind={kind}
              filters={draft}
              setFilters={setDraft}
              onApply={applyFilters}
              onReset={resetFilters}
            />
            <ModerationStats total={total} items={items} />
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2 xl:items-start">
        <div className="space-y-4">
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
          <Card className="overflow-hidden rounded-3xl border border-border/35 bg-gradient-to-b from-background via-background to-muted/20 shadow-[0_22px_54px_-40px_rgba(15,23,42,0.6)] backdrop-blur-sm">
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

                  <div className="rounded-2xl border border-border/30 bg-background/65 p-4 text-sm">
                    <dl className="grid gap-3 sm:grid-cols-2">
                      <div className="space-y-1">
                        <dt className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground/80">
                          {t("moderation.path")}
                        </dt>
                        <dd className="break-all text-foreground/90">
                          {getModerationPath(selectedItem, lang, titleMap)}
                        </dd>
                      </div>
                      <div className="space-y-1">
                        <dt className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground/80">
                          {getModerationAuthFieldLabel(lang)}
                        </dt>
                        <dd className="text-foreground/90">
                          {getModerationAuthDisplay(selectedItem, lang)}
                        </dd>
                      </div>
                      <div className="space-y-1 sm:col-span-2">
                        <dt className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground/80">
                          {t("moderation.updated")}
                        </dt>
                        <dd className="text-foreground/90">
                          {formatDate(selectedItem.updated_at)}
                        </dd>
                      </div>
                    </dl>
                  </div>

                  <div className="rounded-2xl border border-border/30 bg-background/65 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground/70">
                      真实页面预览
                    </p>
                    <div className="mt-3">
                      <ModerationBodyPreview content={getModerationBody(selectedItem)} />
                    </div>
                  </div>

                  {activeThread.length > 0 && (
                    <div className="space-y-2 rounded-2xl border border-border/30 bg-background/65 p-4">
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
      </div>

      <div className="mb-6">
        <AdminSegmentedFilter
          value={activeTab}
          onValueChange={(value) =>
            setActiveTab(value === "guestbook" ? "guestbook" : "comments")
          }
          items={[
            { value: "comments", label: t("moderation.comments") },
            { value: "guestbook", label: t("moderation.guestbook") },
          ]}
          placement="below-header"
        />
      </div>
      <TabsContent value="comments">
        <ModerationQueue
          kind="comments"
          loadItems={(params) =>
            listCommentsApiV1AdminModerationCommentsGet(params) as Promise<{
              data?: PaginatedResponseCommentAdminRead;
            }>
          }
          moderateItem={(id, payload) =>
            moderateCommentApiV1AdminModerationCommentsCommentIdModeratePost(id, payload) as Promise<{
              data?: CommentAdminRead;
            }>
          }
          queryKeyFn={(params?) => getListCommentsApiV1AdminModerationCommentsGetQueryKey(params)}
        />
      </TabsContent>
      <TabsContent value="guestbook">
        <ModerationQueue
          kind="guestbook"
          loadItems={(params) =>
            listGuestbookApiV1AdminModerationGuestbookGet(params) as Promise<{
              data?: PaginatedResponseGuestbookAdminRead;
            }>
          }
          moderateItem={(id, payload) =>
            moderateGuestbookApiV1AdminModerationGuestbookEntryIdModeratePost(id, payload) as Promise<{
              data?: GuestbookAdminRead;
            }>
          }
          queryKeyFn={(params?) => getListGuestbookApiV1AdminModerationGuestbookGetQueryKey(params)}
        />
      </TabsContent>
    </Tabs>
  );
}
