import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { init, type WalineInstance } from "@waline/client";
import "@waline/client/style";
import {
  AlertCircle,
  BadgeCheck,
  CheckCircle2,
  Clock3,
  Flame,
  MessageCircleMore,
  RefreshCcw,
  Sparkles,
  SmilePlus,
  UserRound,
} from "lucide-react";
import {
  DEFAULT_COMMENT_AVATAR_LIBRARY,
  DEFAULT_COMMUNITY_CONFIG,
  buildCommentFeaturePills,
  buildCommentSortLabel,
  buildWalineRuntimeOptions,
  getCommentAvatarStorageKey,
  getCommentDraftStorageKey,
  getCommentSortStorageKey,
  loadCommunityConfig,
  resolveCommentAvatarPreset,
  type CommentAvatarPreset,
  type CommentDraftSnapshot,
  type CommentSurfaceActivity,
  type CommunityCommentSort,
  type CommunityConfig,
  type CommunitySurface,
} from "@/lib/community-config";
import "./WalineSurface.css";

export interface WalineSurfaceProps {
  surface: CommunitySurface;
  slug?: string;
  title?: string;
  description?: string;
  className?: string;
  communityConfig?: CommunityConfig | null;
  avatarLibrary?: CommentAvatarPreset[];
  onActivity?: (activity: CommentSurfaceActivity) => void;
}

type NoticeTone = "neutral" | "positive" | "warning" | "danger";

interface SurfaceNotice {
  tone: NoticeTone;
  title: string;
  detail?: string;
}

const defaultSubtitle = "昵称必填，邮箱可选，支持 Markdown / GFM、表情包搜索和更克制的头像呈现。";
const loadingCopy = "正在载入评论配置...";
const draftInputSelector = "textarea, input";
const persistDelay = 180;

const isSupportedSort = (value: string | null): value is CommunityCommentSort =>
  value === "latest" || value === "oldest" || value === "hottest";

const stringifyNotice = (notice: SurfaceNotice | null) =>
  notice ? `${notice.title}${notice.detail ? ` · ${notice.detail}` : ""}` : "";

const escapeSelectorValue = (value: string) => value.replaceAll("\\", "\\\\").replaceAll('"', '\\"');

const WalineSurface = ({
  surface,
  slug,
  title,
  description,
  className,
  communityConfig,
  avatarLibrary,
  onActivity,
}: WalineSurfaceProps) => {
  const [remoteConfig, setRemoteConfig] = useState<CommunityConfig | null>(communityConfig ?? null);
  const [loading, setLoading] = useState(!communityConfig);
  const [sortMode, setSortMode] = useState<CommunityCommentSort>("latest");
  const [selectedAvatarId, setSelectedAvatarId] = useState<string | null>(null);
  const [draftSnapshot, setDraftSnapshot] = useState<CommentDraftSnapshot | null>(null);
  const [notice, setNotice] = useState<SurfaceNotice | null>(null);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const instanceRef = useRef<WalineInstance | null>(null);
  const noticeTimerRef = useRef<number | null>(null);
  const sortHydratedRef = useRef(false);
  const avatarHydratedRef = useRef(false);
  const selectedAvatarIdRef = useRef<string | null>(null);

  useEffect(() => {
    selectedAvatarIdRef.current = selectedAvatarId;
  }, [selectedAvatarId]);

  useEffect(() => {
    let active = true;

    if (communityConfig) {
      setRemoteConfig(communityConfig);
      setLoading(false);
      return () => {
        active = false;
      };
    }

    setLoading(true);
    void (async () => {
      const config = await loadCommunityConfig();
      if (!active) return;
      setRemoteConfig(config);
      setLoading(false);
    })();

    return () => {
      active = false;
    };
  }, [communityConfig]);

  const resolvedConfig = remoteConfig ?? DEFAULT_COMMUNITY_CONFIG;
  const resolvedAvatarLibrary = useMemo(() => {
    if (avatarLibrary?.length) {
      return avatarLibrary;
    }

    if (resolvedConfig.avatarLibrary.length) {
      return resolvedConfig.avatarLibrary;
    }

    return DEFAULT_COMMENT_AVATAR_LIBRARY;
  }, [avatarLibrary, resolvedConfig.avatarLibrary]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const storedSort = window.localStorage.getItem(getCommentSortStorageKey(surface, slug));
    if (isSupportedSort(storedSort)) {
      setSortMode(storedSort);
      sortHydratedRef.current = true;
      return;
    }

    if (!sortHydratedRef.current) {
      setSortMode(resolvedConfig.commentSorting ?? "latest");
      sortHydratedRef.current = true;
    }
  }, [resolvedConfig.commentSorting, slug, surface]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const storageKey = getCommentAvatarStorageKey(surface, slug);
    const storedAvatarId = window.localStorage.getItem(storageKey);
    const resolvedAvatar = resolveCommentAvatarPreset(resolvedAvatarLibrary, storedAvatarId);

    if (resolvedAvatar) {
      setSelectedAvatarId(resolvedAvatar.id);
      avatarHydratedRef.current = true;
      return;
    }

    if (!avatarHydratedRef.current) {
      setSelectedAvatarId(resolvedAvatarLibrary[0]?.id ?? null);
      avatarHydratedRef.current = true;
    }
  }, [resolvedAvatarLibrary, slug, surface]);

  const resolvedAvatar = useMemo(
    () => resolveCommentAvatarPreset(resolvedAvatarLibrary, selectedAvatarId),
    [resolvedAvatarLibrary, selectedAvatarId],
  );

  const subtitle = description ?? resolvedConfig.helperCopy ?? defaultSubtitle;
  const runtimeOptions = useMemo(
    () => buildWalineRuntimeOptions(resolvedConfig, surface, slug, sortMode),
    [resolvedConfig, sortMode, slug, surface],
  );
  const hasServer = runtimeOptions.serverURL.trim().length > 0;
  const featurePills = useMemo(
    () => buildCommentFeaturePills(resolvedConfig, sortMode, resolvedAvatar?.label ?? null),
    [resolvedConfig, resolvedAvatar?.label, sortMode],
  );
  const visibleFeaturePills = useMemo(() => {
    const preferredOrder = ["meta", "sort", "search", "avatar"];
    return preferredOrder
      .map((key) => featurePills.find((item) => item.key === key))
      .filter((item): item is (typeof featurePills)[number] => Boolean(item));
  }, [featurePills]);
  const draftSummary = useMemo(() => {
    if (!draftSnapshot) {
      return "草稿会自动同步到本地缓存。";
    }

    const fieldCount = Object.keys(draftSnapshot.fields).length;
    if (draftSnapshot.body.length === 0 && fieldCount === 0) {
      return draftSnapshot.avatarId ? "匿名头像已记住，本地缓存会同步你的选择。" : "草稿会自动同步到本地缓存。";
    }
    return `草稿已保存 · ${draftSnapshot.body.length} 字 · ${fieldCount} 个字段`;
  }, [draftSnapshot]);

  const reportNotice = useCallback(
    (nextNotice: SurfaceNotice | null, activity?: CommentSurfaceActivity) => {
      if (noticeTimerRef.current) {
        window.clearTimeout(noticeTimerRef.current);
        noticeTimerRef.current = null;
      }

      setNotice(nextNotice);
      if (activity) {
        onActivity?.(activity);
      }

      if (nextNotice?.tone !== "danger" && nextNotice) {
        noticeTimerRef.current = window.setTimeout(() => {
          setNotice(null);
        }, 4200);
      }
    },
    [onActivity],
  );

  const handleSortChange = useCallback(
    (nextSort: CommunityCommentSort) => {
      if (nextSort === sortMode) {
        return;
      }

      setSortMode(nextSort);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(getCommentSortStorageKey(surface, slug), nextSort);
      }

      reportNotice(
        {
          tone: "neutral",
          title: "排序已切换",
          detail: buildCommentSortLabel(nextSort),
        },
        {
          type: "sort-change",
          surface,
          slug: slug ?? "guestbook",
          message: `排序切换为 ${buildCommentSortLabel(nextSort)}`,
          sort: nextSort,
        },
      );
    },
    [reportNotice, slug, sortMode, surface],
  );

  const handleAvatarChange = useCallback(
    (preset: CommentAvatarPreset) => {
      setSelectedAvatarId(preset.id);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(getCommentAvatarStorageKey(surface, slug), preset.id);
      }
      reportNotice(
        {
          tone: "positive",
          title: "匿名头像已选定",
          detail: preset.label,
        },
        {
          type: "avatar-change",
          surface,
          slug: slug ?? "guestbook",
          message: `匿名头像切换为 ${preset.label}`,
          avatarId: preset.id,
          avatarLabel: preset.label,
        },
      );
    },
    [reportNotice, slug, surface],
  );

  useEffect(() => {
    if (!draftSnapshot) {
      return;
    }

    const fieldCount = Object.keys(draftSnapshot.fields).length;
    if (draftSnapshot.body.length === 0 && fieldCount === 0) {
      return;
    }

    if (draftSnapshot.avatarId === selectedAvatarId) {
      return;
    }

    setDraftSnapshot({
      ...draftSnapshot,
      avatarId: selectedAvatarId,
      updatedAt: Date.now(),
    });
  }, [draftSnapshot, selectedAvatarId]);

  useEffect(() => {
    if (typeof window === "undefined" || !selectedAvatarId) {
      return;
    }

    window.localStorage.setItem(getCommentAvatarStorageKey(surface, slug), selectedAvatarId);
  }, [selectedAvatarId, slug, surface]);

  useEffect(() => {
    if (typeof window === "undefined" || !draftSnapshot) {
      return;
    }

    window.localStorage.setItem(getCommentDraftStorageKey(surface, slug), JSON.stringify(draftSnapshot));
  }, [draftSnapshot, slug, surface]);

  useEffect(() => {
    if (loading || !hasServer || !hostRef.current) {
      instanceRef.current?.destroy();
      instanceRef.current = null;
      return;
    }

    instanceRef.current?.destroy();
    instanceRef.current = init({
      ...runtimeOptions,
      el: hostRef.current,
    });

    return () => {
      instanceRef.current?.destroy();
      instanceRef.current = null;
    };
  }, [hasServer, loading, runtimeOptions]);

  useEffect(() => {
    if (loading || !hasServer || !hostRef.current || typeof window === "undefined") {
      return;
    }

    const host = hostRef.current;
    const originalFetch = window.fetch.bind(window);
    const boundElements = new WeakSet<Element>();
    let restoredDraft = false;
    let isRestoring = false;
    let saveTimer: number | null = null;
    let scanTimer: number | null = null;
    let active = true;

    const persistDraft = () => {
      if (isRestoring) return;

      if (saveTimer) {
        window.clearTimeout(saveTimer);
      }

      saveTimer = window.setTimeout(() => {
        if (!active || isRestoring) return;

        const fields: Record<string, string> = {};
        let body = "";

        host.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>(draftInputSelector).forEach((element) => {
          if (element instanceof HTMLInputElement) {
            const type = element.type.toLowerCase();
            if (["button", "submit", "reset", "checkbox", "radio", "file"].includes(type)) {
              return;
            }
          }

          const key = element.name.trim() || element.id.trim();
          if (!key) {
            if (element instanceof HTMLTextAreaElement) {
              body = element.value;
            }
            return;
          }

          const value = element.value;
          fields[key] = value;
          if (element instanceof HTMLTextAreaElement) {
            body = value;
          }
        });

        const snapshot: CommentDraftSnapshot = {
          body,
          fields,
          avatarId: selectedAvatarIdRef.current,
          updatedAt: Date.now(),
        };

        if (body.trim().length === 0 && Object.values(fields).every((value) => value.trim().length === 0)) {
          setDraftSnapshot(null);
          window.localStorage.removeItem(getCommentDraftStorageKey(surface, slug));
          return;
        }

        setDraftSnapshot(snapshot);
      }, persistDelay);
    };

    const applyDraftSnapshot = () => {
      if (restoredDraft) {
        return;
      }

      const rawDraft = window.localStorage.getItem(getCommentDraftStorageKey(surface, slug));
      if (!rawDraft) {
        return;
      }

      try {
        const parsed = JSON.parse(rawDraft) as Partial<CommentDraftSnapshot>;
        const nextFields = parsed.fields && typeof parsed.fields === "object" ? parsed.fields : {};
        const nextBody = typeof parsed.body === "string" ? parsed.body : "";
        const nextAvatarId = typeof parsed.avatarId === "string" && parsed.avatarId.trim() ? parsed.avatarId.trim() : null;

        if (Object.keys(nextFields).length === 0 && !nextBody && !nextAvatarId) {
          return;
        }

        if (nextAvatarId) {
          const matchedAvatar = resolveCommentAvatarPreset(resolvedAvatarLibrary, nextAvatarId);
          if (matchedAvatar) {
            setSelectedAvatarId(matchedAvatar.id);
          }
        }

        Object.entries(nextFields).forEach(([fieldName, fieldValue]) => {
          if (!fieldName) return;
          const escaped = escapeSelectorValue(fieldName);
          const target = host.querySelector<HTMLInputElement | HTMLTextAreaElement>(`[name="${escaped}"], #${escaped}`);
          if (!target) return;
          if (target.value === fieldValue) return;
          target.value = fieldValue;
          target.dispatchEvent(new Event("input", { bubbles: true }));
          target.dispatchEvent(new Event("change", { bubbles: true }));
        });

        if (nextBody) {
          const textarea = host.querySelector<HTMLTextAreaElement>("textarea");
          if (textarea && textarea.value !== nextBody) {
            textarea.value = nextBody;
            textarea.dispatchEvent(new Event("input", { bubbles: true }));
            textarea.dispatchEvent(new Event("change", { bubbles: true }));
          }
        }

        restoredDraft = true;
        setDraftSnapshot({
          body: nextBody,
          fields: nextFields,
          avatarId: nextAvatarId,
          updatedAt: typeof parsed.updatedAt === "number" ? parsed.updatedAt : Date.now(),
        });
        reportNotice(
          {
            tone: "positive",
            title: "草稿已恢复",
            detail: nextBody ? `${nextBody.length} 字` : "本地保存的内容已重新填入",
          },
          {
            type: "draft-restored",
            surface,
            slug: slug ?? "guestbook",
            message: "草稿已恢复到评论框",
            draftLength: nextBody.length,
          },
        );
      } catch {
        // ignore malformed draft payloads
      }
    };

    const bindComposerField = (element: HTMLInputElement | HTMLTextAreaElement) => {
      if (boundElements.has(element)) {
        return;
      }

      boundElements.add(element);
      element.addEventListener("input", persistDraft);
      element.addEventListener("change", persistDraft);
    };

    const scanComposer = () => {
      host.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>(draftInputSelector).forEach(bindComposerField);
      if (!restoredDraft) {
        isRestoring = true;
        applyDraftSnapshot();
        isRestoring = false;
      }
    };

    const observer = new MutationObserver(() => {
      if (scanTimer) window.clearTimeout(scanTimer);
      scanTimer = window.setTimeout(scanComposer, 60);
    });

    observer.observe(host, { childList: true, subtree: true });
    scanComposer();

    window.fetch = (async (...args: Parameters<typeof window.fetch>) => {
      const request = args[0] instanceof Request ? args[0] : new Request(String(args[0]), args[1]);
      const requestUrl = new URL(request.url, window.location.href);
      const isWalineRequest = requestUrl.href.startsWith(resolvedConfig.serverURL);
      const method = request.method.toUpperCase();
      const isMutation = isWalineRequest && method !== "GET";

      if (isMutation) {
        setNotice({
          tone: "neutral",
          title: "正在提交评论",
          detail: "请求已发送到 Waline",
        });
      }

      try {
        const response = await originalFetch(...args);
        if (isMutation && active) {
          if (response.ok) {
            reportNotice(
              {
                tone: "positive",
                title: "提交成功",
                detail: method === "POST" ? "评论已提交，徽章刷新已预留" : "评论操作已完成",
              },
              {
                type: "submission-success",
                surface,
                slug: slug ?? "guestbook",
                message: method === "POST" ? "评论已提交，评论徽章可刷新" : "评论操作成功",
              },
            );
          } else {
            reportNotice(
              {
                tone: "danger",
                title: "提交失败",
                detail: `HTTP ${response.status}`,
              },
              {
                type: "submission-error",
                surface,
                slug: slug ?? "guestbook",
                message: `提交失败，HTTP ${response.status}`,
              },
            );
          }
        }
        return response;
      } catch (error) {
        if (isMutation && active) {
          const message = error instanceof Error ? error.message : "网络错误";
          reportNotice(
            {
              tone: "danger",
              title: "提交失败",
              detail: message,
            },
            {
              type: "submission-error",
              surface,
              slug: slug ?? "guestbook",
              message,
            },
          );
        }
        throw error;
      }
    }) as typeof window.fetch;

    return () => {
      active = false;
      observer.disconnect();
      if (saveTimer) {
        window.clearTimeout(saveTimer);
      }
      if (scanTimer) {
        window.clearTimeout(scanTimer);
      }
      window.fetch = originalFetch;
    };
  }, [hasServer, loading, reportNotice, resolvedAvatarLibrary, resolvedConfig.serverURL, slug, surface]);

  useEffect(() => {
    return () => {
      if (noticeTimerRef.current) {
        window.clearTimeout(noticeTimerRef.current);
      }
    };
  }, []);

  const isAvatarLibraryEnabled = resolvedConfig.avatarLibraryEnabled !== false;
  const noticeLabel = notice ? stringifyNotice(notice) : draftSummary;

  return (
    <section className={`aerisun-waline-shell ${className ?? ""}`.trim()}>
      <div className="aerisun-waline-shell__glow" aria-hidden="true" />
      <div className="aerisun-waline-shell__header">
        <div className="space-y-3">
          <p className="aerisun-waline-shell__eyebrow">
            <span className="inline-flex items-center gap-2">
              <MessageCircleMore className="h-4 w-4" />
              社区评论
            </span>
          </p>
          <div className="space-y-1">
            <h2 className="aerisun-waline-shell__title">{title ?? "评论区"}</h2>
            <p className="aerisun-waline-shell__subtitle">{subtitle}</p>
          </div>
        </div>

        <div className="aerisun-waline-shell__pills" aria-label="Waline capabilities">
          {visibleFeaturePills.map((pill) => (
            <span key={pill.key} className="aerisun-waline-shell__pill" data-tone={pill.tone ?? "default"}>
              {pill.key === "meta" ? (
                <BadgeCheck className="h-3.5 w-3.5" />
              ) : pill.key === "login" ? (
                <UserRound className="h-3.5 w-3.5" />
              ) : pill.key === "sort" ? (
                <RefreshCcw className="h-3.5 w-3.5" />
              ) : pill.key === "search" ? (
                <Sparkles className="h-3.5 w-3.5" />
              ) : pill.key === "upload" ? (
                <SmilePlus className="h-3.5 w-3.5" />
              ) : (
                <Flame className="h-3.5 w-3.5" />
              )}
              {pill.label}
            </span>
          ))}
        </div>
      </div>

      <div className="aerisun-waline-shell__toolbar">
        <div className="aerisun-waline-shell__sort-strip" role="tablist" aria-label="评论排序">
          {(["latest", "oldest", "hottest"] as CommunityCommentSort[]).map((option) => {
            const active = option === sortMode;
            return (
              <button
                key={option}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => handleSortChange(option)}
                className={`aerisun-waline-shell__sort-chip ${active ? "is-active" : ""}`}
              >
                {buildCommentSortLabel(option)}
              </button>
            );
          })}
        </div>

        {isAvatarLibraryEnabled ? (
          <div className="aerisun-waline-shell__avatar-strip" role="list" aria-label="匿名头像选择">
            {resolvedAvatarLibrary.map((preset) => {
              const active = preset.id === selectedAvatarId;
              return (
                <button
                  key={preset.id}
                  type="button"
                  role="listitem"
                  aria-pressed={active}
                  onClick={() => handleAvatarChange(preset)}
                  className={`aerisun-waline-shell__avatar-chip ${active ? "is-active" : ""}`}
                >
                  <img className="aerisun-waline-shell__avatar-image" src={preset.src} alt={preset.label} loading="lazy" />
                  <span className="aerisun-waline-shell__avatar-chip-label">{preset.label}</span>
                </button>
              );
            })}
          </div>
        ) : null}
      </div>

      <div className="aerisun-waline-shell__note" data-tone={notice?.tone ?? "neutral"}>
        {notice ? (
          <>
            {notice.tone === "positive" ? (
              <CheckCircle2 className="h-4 w-4" />
            ) : notice.tone === "danger" ? (
              <AlertCircle className="h-4 w-4" />
            ) : (
              <RefreshCcw className="h-4 w-4" />
            )}
            <span>{noticeLabel}</span>
          </>
        ) : (
          <>
            <Clock3 className="h-4 w-4" />
            <span>{noticeLabel}</span>
          </>
        )}
      </div>

      <div className="aerisun-waline-shell__body">
        {loading ? (
          <div className="aerisun-waline-shell__loading" role="status" aria-live="polite">
            <div className="aerisun-waline-shell__spinner" />
            <p>{loadingCopy}</p>
          </div>
        ) : hasServer ? (
          <div ref={hostRef} className="aerisun-waline-host">
            <div className="sr-only">
              {title ?? "评论区"} {subtitle}
            </div>
          </div>
        ) : (
          <div className="aerisun-waline-shell__empty" role="status">
            <p className="text-sm font-medium text-foreground/80">Waline 服务未配置</p>
            <p className="mt-2 text-sm leading-6 text-foreground/55">
              需要在公开社区配置或 `VITE_WALINE_SERVER_URL` 中提供服务地址后，这个评论区才会显示。
            </p>
          </div>
        )}
      </div>
    </section>
  );
};

export default WalineSurface;
