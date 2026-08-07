import { startTransition, useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { PencilLine, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import {
  createCommentApiV1SiteInteractionsCommentsContentTypeSlugPost,
  createGuestbookApiV1SiteInteractionsGuestbookPost,
  deleteCommentApiV1SiteInteractionsCommentsCommentIdDelete,
  deleteGuestbookEntryApiV1SiteInteractionsGuestbookEntryIdDelete,
  updateCommentFeedbackApiV1SiteInteractionsCommentsCommentIdFeedbackPatch,
  uploadCommentImageApiV1SiteInteractionsCommentImagePost,
} from "@serino/api-client/site-interactions";
import {
  DEFAULT_COMMUNITY_CONFIG,
  loadCommunityConfig,
  type CommunityConfig,
  type CommunitySurface,
} from "@/lib/community-config";
import { useFrontendI18n } from "@/i18n";
import { useSiteAuth } from "@/contexts/use-site-auth";
import { usePageConfig } from "@/contexts/runtime-config";
import {
  invalidateCommunityEntryCache,
  primeCommentPage,
  primeGuestbookPage,
  readCachedCommentPage,
  readCachedGuestbookPage,
} from "@/lib/community-cache";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import { transition } from "@/config";
import { prepareImageUploadFile } from "@serino/utils/image-upload";
import WalineCommentForm from "./WalineCommentForm";
import WalineCommentList from "./WalineCommentList";
import {
  buildAvatarPresets,
  buildDefaultAvatarPreset,
  collectAvatarUsage,
  countCommentTree,
  EMOJI_CHOICES,
  insertTextAtSelection,
  normalizeName,
  PROFILE_STORAGE_PREFIX,
  providerLabel,
  readStoredDraft,
  resolveApiError,
  sortComments,
  sortGuestbookEntries,
  communityPanelClass,
  type CommunityCommentItem,
  type CommunityGuestbookItem,
  type DraftState,
  type EditorMode,
  type ReplyTarget,
} from "./waline-types";
import "./WalineSurface.css";

interface CommunityPageSnapshot<T> {
  items: T[];
  pendingItems: T[];
  hasMore: boolean;
  total: number;
  page: number;
}

interface PendingCommentImage {
  marker: string;
  previewUrl: string;
  file: File;
  alt: string;
}

const MAX_IMAGES_PER_COMMENT = 9;
const COMMENT_MARKDOWN_IMAGE_RE = /!\[[^\]]*]\([^)]+\)/g;

const createPendingImageMarker = () => {
  const cryptoId = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : "";
  const fallbackId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return cryptoId || fallbackId;
};

const sanitizeMarkdownImageAlt = (value: string) =>
  value.replace(/[\r\n[\]]+/g, " ").replace(/\s+/g, " ").trim() || "image";

const countCommentImages = (body: string) => body.match(COMMENT_MARKDOWN_IMAGE_RE)?.length ?? 0;

const removeCommentFromTree = (items: CommunityCommentItem[], commentId: string): CommunityCommentItem[] =>
  items
    .filter((item) => item.id !== commentId)
    .map((item) => ({
      ...item,
      replies: removeCommentFromTree(item.replies ?? [], commentId),
    }));

const findCommentInTree = (
  items: CommunityCommentItem[],
  commentId: string,
): CommunityCommentItem | null => {
  for (const item of items) {
    if (item.id === commentId) {
      return item;
    }
    const found = findCommentInTree(item.replies ?? [], commentId);
    if (found) {
      return found;
    }
  }
  return null;
};

const updateCommentInTree = (
  items: CommunityCommentItem[],
  commentId: string,
  updater: (item: CommunityCommentItem) => CommunityCommentItem,
): CommunityCommentItem[] =>
  items.map((item) => {
    const nextItem = item.id === commentId ? updater(item) : item;
    return {
      ...nextItem,
      replies: updateCommentInTree(nextItem.replies ?? [], commentId, updater),
    };
  });

export interface WalineSurfaceProps {
  surface: CommunitySurface;
  slug?: string;
  className?: string;
  layout?: "default" | "modal";
  communityConfig?: CommunityConfig | null;
  onVisibleCountChange?: (count: number) => void;
}

const WalineSurface = ({
  surface,
  slug,
  className,
  layout = "default",
  communityConfig,
  onVisibleCountChange,
}: WalineSurfaceProps) => {
  const prefersReducedMotion = useReducedMotionPreference();
  const { t } = useFrontendI18n();
  const isGuestbook = surface === "guestbook";
  const pageConfig = usePageConfig();
  const guestbookPageConfig = (pageConfig.guestbook as Record<string, unknown> | undefined) ?? {};
  const guestbookBodyPlaceholder = String(
    guestbookPageConfig.contentPlaceholder ?? t("waline.surface.guestbookBodyPlaceholder"),
  );
  const guestbookSubmitLabel = String(guestbookPageConfig.submitLabel ?? t("waline.surface.guestbookSubmit"));
  const guestbookSubmittingLabel = String(guestbookPageConfig.submittingLabel ?? t("waline.surface.guestbookSubmitting"));
  const guestbookLoadingLabel = String(guestbookPageConfig.loadingLabel ?? t("waline.surface.guestbookLoading"));
  const guestbookRetryLabel = String(guestbookPageConfig.retryLabel ?? t("waline.surface.guestbookRetry"));
  const guestbookEmptyMessage = String(guestbookPageConfig.emptyMessage ?? t("waline.surface.guestbookEmpty"));
  const imageLimitMessageKey = isGuestbook
    ? "waline.surface.guestbookImageLimitExceeded"
    : "waline.surface.commentImageLimitExceeded";
  const storageKey = `${PROFILE_STORAGE_PREFIX}${surface}:${slug ?? "guestbook"}`;
  const {
    user: siteUser,
    loading: authLoading,
    emailLoginEnabled: siteAuthEmailLoginEnabled,
    oauthProviders: siteAuthOauthProviders,
    openLogin,
    logout,
  } = useSiteAuth();
  const [config, setConfig] = useState<CommunityConfig | null>(communityConfig ?? null);
  const [loadingConfig, setLoadingConfig] = useState(!communityConfig);
  const [loadingEntries, setLoadingEntries] = useState(true);
  const [loadingMoreEntries, setLoadingMoreEntries] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [refreshSeed, setRefreshSeed] = useState(0);
  const [authError, setAuthError] = useState<string | null>(null);
  const [comments, setComments] = useState<CommunityCommentItem[]>([]);
  const [guestbookEntries, setGuestbookEntries] = useState<CommunityGuestbookItem[]>([]);
  const [loadedPageCount, setLoadedPageCount] = useState(1);
  const [hasMoreEntries, setHasMoreEntries] = useState(false);
  const [entryTotal, setEntryTotal] = useState(0);
  const [pendingComments, setPendingComments] = useState<CommunityCommentItem[]>([]);
  const [pendingGuestbookEntries, setPendingGuestbookEntries] = useState<CommunityGuestbookItem[]>([]);
  const [feedbackEnabled, setFeedbackEnabled] = useState(true);
  const [busyItemIds, setBusyItemIds] = useState<Set<string>>(() => new Set());
  const [draft, setDraft] = useState<DraftState>(() => {
    const storedDraft = readStoredDraft(storageKey);
    return {
      name: typeof storedDraft.name === "string" ? storedDraft.name : "",
      email: typeof storedDraft.email === "string" ? storedDraft.email : "",
      website: typeof storedDraft.website === "string" ? storedDraft.website : "",
      body: "",
      avatarKey: typeof storedDraft.avatarKey === "string" ? storedDraft.avatarKey : "",
    };
  });
  const [replyTarget, setReplyTarget] = useState<ReplyTarget | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitNotice, setSubmitNotice] = useState<string | null>(null);
  const [avatarPickerOpen, setAvatarPickerOpen] = useState(false);
  const [emojiPickerOpen, setEmojiPickerOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<EditorMode>("write");
  const [composerOpen, setComposerOpen] = useState(false);
  const [imageUploading, setImageUploading] = useState(false);
  const [pendingCommentImages, setPendingCommentImages] = useState<PendingCommentImage[]>([]);
  const avatarPickerRef = useRef<HTMLDivElement | null>(null);
  const emojiPickerRef = useRef<HTMLDivElement | null>(null);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const pendingCommentImagesRef = useRef<PendingCommentImage[]>([]);
  const deferredBody = useDeferredValue(draft.body);

  useEffect(() => {
    pendingCommentImagesRef.current = pendingCommentImages;
  }, [pendingCommentImages]);

  useEffect(() => () => {
    for (const item of pendingCommentImagesRef.current) {
      URL.revokeObjectURL(item.previewUrl);
    }
  }, []);

  useEffect(() => {
    if (communityConfig) {
      setConfig(communityConfig);
      setLoadingConfig(false);
      return;
    }

    let active = true;
    setLoadingConfig(true);
    void loadCommunityConfig({ cache: "no-store" })
      .then((nextConfig) => {
        if (!active) return;
        setConfig(nextConfig);
      })
      .finally(() => {
        if (active) {
          setLoadingConfig(false);
        }
      });

    return () => {
      active = false;
    };
  }, [communityConfig]);

  const resolvedConfig = config ?? DEFAULT_COMMUNITY_CONFIG;
  const imageUploadsEnabled = resolvedConfig.image_uploader;
  const commentFeedbackAvailable = !isGuestbook && resolvedConfig.comment_feedback_enabled;
  const requiresAuthentication = true;
  const commentEmailLoginEnabled = resolvedConfig.anonymous_enabled && siteAuthEmailLoginEnabled;
  const oauthProviderLabels = useMemo(
    () => siteAuthOauthProviders.map(providerLabel),
    [siteAuthOauthProviders],
  );
  const loginMethodLabels = useMemo(
    () => [
      ...(commentEmailLoginEnabled ? [t("waline.surface.loginMethodEmail")] : []),
      ...oauthProviderLabels,
    ],
    [commentEmailLoginEnabled, oauthProviderLabels, t],
  );
  const hasLoginMethod = loginMethodLabels.length > 0;
  const authSession = useMemo(
    () =>
      siteUser
        ? {
            objectId: siteUser.id,
            display_name: siteUser.effective_display_name,
            email: siteUser.email,
            url: "",
            avatar: siteUser.effective_avatar_url,
            is_admin: siteUser.is_admin ?? false,
          }
        : null,
    [siteUser],
  );
  const viewerCacheKey = authSession ? `user:${authSession.objectId}` : "anon";
  const [avatarPresets, setAvatarPresets] = useState<import("@/lib/community-config").AvatarPreset[]>([]);
  const defaultAvatarPreset = useMemo(
    () => buildDefaultAvatarPreset(draft.email || draft.name),
    [draft.email, draft.name],
  );

  useEffect(() => {
    setAvatarPresets(buildAvatarPresets(draft.email || draft.name));
  }, [draft.email, draft.name, refreshSeed]);

  useEffect(() => {
    if (authSession) {
      return;
    }
    if (!avatarPresets.length) {
      return;
    }
    if (draft.avatarKey && avatarPresets.some((preset) => preset.key === draft.avatarKey)) {
      return;
    }
    setDraft((current) => ({ ...current, avatarKey: defaultAvatarPreset.key }));
  }, [authSession, avatarPresets, defaultAvatarPreset.key, draft.avatarKey]);

  useEffect(() => {
    try {
      localStorage.setItem(
        storageKey,
        JSON.stringify({
          name: draft.name,
          email: draft.email,
          website: draft.website,
          avatarKey: draft.avatarKey,
        }),
      );
    } catch {
      // Ignore storage failures.
    }
  }, [draft.avatarKey, draft.email, draft.name, draft.website, storageKey]);

  const initialPageSize = Math.max(1, resolvedConfig.page_size ?? 10);

  const applyEntryPages = useCallback((
    pages: Array<CommunityPageSnapshot<CommunityCommentItem> | CommunityPageSnapshot<CommunityGuestbookItem>>,
  ) => {
    const orderedPages = [...pages].sort((left, right) => left.page - right.page);
    const lastPage = orderedPages.at(-1);
    const mergedItems = orderedPages.flatMap((page) => page.items);
    const pendingItems = orderedPages.find((page) => page.page === 1)?.pendingItems ?? [];

    if (isGuestbook) {
      setGuestbookEntries(
        sortGuestbookEntries(mergedItems as CommunityGuestbookItem[], resolvedConfig.default_sorting),
      );
      setPendingGuestbookEntries(
        sortGuestbookEntries(pendingItems as CommunityGuestbookItem[], resolvedConfig.default_sorting),
      );
    } else {
      setComments(
        sortComments(mergedItems as CommunityCommentItem[], resolvedConfig.default_sorting),
      );
      setPendingComments(
        sortComments(pendingItems as CommunityCommentItem[], resolvedConfig.default_sorting),
      );
    }

    setLoadedPageCount(lastPage?.page ?? 1);
    setHasMoreEntries(Boolean(lastPage?.hasMore));
    setEntryTotal(lastPage?.total ?? 0);
  }, [isGuestbook, resolvedConfig.default_sorting]);

  const readCachedPages = useCallback((requestedPageCount: number) => {
    const pages: Array<CommunityPageSnapshot<CommunityCommentItem> | CommunityPageSnapshot<CommunityGuestbookItem>> = [];

    for (let page = 1; page <= requestedPageCount; page += 1) {
      const cached = isGuestbook
        ? readCachedGuestbookPage({ page, pageSize: initialPageSize, viewerKey: viewerCacheKey })
        : slug
          ? readCachedCommentPage({
              surface,
              slug,
              page,
              pageSize: initialPageSize,
              viewerKey: viewerCacheKey,
            })
          : null;

      if (!cached) {
        break;
      }

      pages.push({
        items: cached.items,
        pendingItems: cached.pendingItems ?? [],
        hasMore: cached.hasMore,
        total: cached.total ?? (isGuestbook ? cached.items.length : countCommentTree(cached.items as CommunityCommentItem[])),
        page: cached.page,
      });

      if (!cached.hasMore) {
        break;
      }
    }

    return pages;
  }, [initialPageSize, isGuestbook, slug, surface, viewerCacheKey]);

  const fetchEntryPage = useCallback(async (
    page: number,
    forceNetwork = false,
  ): Promise<CommunityPageSnapshot<CommunityCommentItem> | CommunityPageSnapshot<CommunityGuestbookItem>> => {
    if (isGuestbook) {
      const payload = await primeGuestbookPage(
        { page, pageSize: initialPageSize, viewerKey: viewerCacheKey },
        { forceNetwork },
      );

      return {
        items: payload.items,
        pendingItems: payload.pendingItems ?? [],
        hasMore: payload.hasMore,
        total: payload.total,
        page: payload.page,
      };
    }

    if (!slug) {
      throw new Error(t("waline.surface.missingPath"));
    }

    const payload = await primeCommentPage(
      {
        surface,
        slug,
        page,
        pageSize: initialPageSize,
        viewerKey: viewerCacheKey,
      },
      { forceNetwork },
    );

    return {
      items: payload.items,
      pendingItems: payload.pendingItems ?? [],
      hasMore: payload.hasMore,
      total: payload.total,
      page: payload.page,
    };
  }, [initialPageSize, isGuestbook, slug, surface, t, viewerCacheKey]);

  const loadEntries = useCallback(async (
    requestedPageCount = 1,
    options?: {
      fetchNextPageOnly?: boolean;
      forceNetwork?: boolean;
      silent?: boolean;
      reconcileAfterAppend?: boolean;
    },
  ) => {
    if (!isGuestbook && !slug) {
      setLoadError(t("waline.surface.missingPath"));
      setLoadingEntries(false);
      setLoadingMoreEntries(false);
      return;
    }

    const nextPageCount = Math.max(1, requestedPageCount);
    const loadMoreRequest = Boolean(options?.fetchNextPageOnly && nextPageCount > loadedPageCount);

    if (!options?.silent) {
      if (loadMoreRequest) {
        setLoadingMoreEntries(true);
      } else {
        setLoadingEntries(true);
      }
    }

    setLoadError(null);

    try {
      if (loadMoreRequest) {
        const nextPage = await fetchEntryPage(nextPageCount, options?.forceNetwork);
        const mergedPages = [
          ...readCachedPages(nextPageCount - 1),
          nextPage,
        ];
        applyEntryPages(mergedPages);

        if (options?.reconcileAfterAppend) {
          startTransition(() => {
            void loadEntries(nextPageCount, {
              silent: true,
              forceNetwork: true,
            });
          });
        }

        return;
      }

      const pages = await Promise.all(
        Array.from({ length: nextPageCount }, (_, index) =>
          fetchEntryPage(index + 1, options?.forceNetwork),
        ),
      );
      applyEntryPages(pages);
    } catch (error) {
      if (!options?.silent || (isGuestbook ? guestbookEntries.length === 0 : comments.length === 0)) {
        setLoadError(resolveApiError(error, t("waline.common.requestFailed")));
      }
    } finally {
      if (!options?.silent) {
        setLoadingEntries(false);
        setLoadingMoreEntries(false);
      }
    }
  }, [applyEntryPages, comments.length, fetchEntryPage, guestbookEntries.length, isGuestbook, loadedPageCount, readCachedPages, slug, t]);

  useEffect(() => {
    const cachedPages = readCachedPages(1);
    if (cachedPages.length > 0) {
      applyEntryPages(cachedPages);
      setLoadingEntries(false);
    }

    void loadEntries(1, { silent: cachedPages.length > 0, forceNetwork: cachedPages.length > 0 });
  }, [applyEntryPages, loadEntries, readCachedPages]);

  const loadMoreEntries = useCallback(() => {
    if (loadingEntries || loadingMoreEntries || !hasMoreEntries) {
      return;
    }

    void loadEntries(loadedPageCount + 1, {
      fetchNextPageOnly: true,
      reconcileAfterAppend: true,
    });
  }, [hasMoreEntries, loadEntries, loadedPageCount, loadingEntries, loadingMoreEntries]);

  useEffect(() => {
    if (!avatarPickerOpen && !emojiPickerOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!avatarPickerRef.current?.contains(event.target as Node)) {
        setAvatarPickerOpen(false);
      }
      if (!emojiPickerRef.current?.contains(event.target as Node)) {
        setEmojiPickerOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [avatarPickerOpen, emojiPickerOpen]);

  useEffect(() => {
    if (replyTarget) {
      setComposerOpen(true);
    }
  }, [replyTarget]);

  const avatarUsage = useMemo(
    () => collectAvatarUsage(comments, guestbookEntries, pendingComments, pendingGuestbookEntries),
    [comments, guestbookEntries, pendingComments, pendingGuestbookEntries],
  );

  const isAvatarOccupied = useCallback((preset: import("@/lib/community-config").AvatarPreset) => {
    const occupants = avatarUsage.get(preset.key) ?? avatarUsage.get(preset.avatar_url);
    if (!occupants || occupants.size === 0) {
      return false;
    }

    const activeName = normalizeName(draft.name);
    if (!activeName) {
      return true;
    }

    return Array.from(occupants).some((name) => name !== activeName);
  }, [avatarUsage, draft.name]);

  const handleFieldChange = useCallback(
    (field: keyof DraftState, value: string) => {
      setDraft((current) => ({ ...current, [field]: value }));
      setSubmitError(null);
      setSubmitNotice(null);
    },
    [],
  );

  const insertIntoBody = useCallback((insertion: string) => {
    const textarea = textareaRef.current;
    const { nextValue, selectionStart } = insertTextAtSelection(draft.body, insertion, textarea);
    setDraft((current) => ({ ...current, body: nextValue }));
    setSubmitError(null);
    setSubmitNotice(null);
    setEditorMode("write");
    requestAnimationFrame(() => {
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(selectionStart, selectionStart);
    });
  }, [draft.body]);

  const handleEmojiInsert = useCallback((emoji: string) => {
    insertIntoBody(emoji);
    setEmojiPickerOpen(false);
  }, [insertIntoBody]);

  const handleImageUpload = useCallback(async (files: File[]) => {
    if (!imageUploadsEnabled) {
      setSubmitError(t("waline.surface.imageUploadDisabled"));
      if (imageInputRef.current) {
        imageInputRef.current.value = "";
      }
      return;
    }
    if (requiresAuthentication && !authSession) {
      setSubmitError(isGuestbook ? t("waline.surface.loginRequiredGuestbook") : t("waline.surface.loginRequiredComment"));
      if (imageInputRef.current) {
        imageInputRef.current.value = "";
      }
      return;
    }
    const totalImageCount = countCommentImages(draft.body) + pendingCommentImages.length + files.length;
    if (totalImageCount > MAX_IMAGES_PER_COMMENT) {
      setSubmitError(t(imageLimitMessageKey, {
        count: MAX_IMAGES_PER_COMMENT,
      }));
      if (imageInputRef.current) {
        imageInputRef.current.value = "";
      }
      return;
    }

    setImageUploading(true);
    setSubmitError(null);
    setSubmitNotice(null);

    try {
      const preparedImages: PendingCommentImage[] = [];
      for (const file of files) {
        const compressedFile = await prepareImageUploadFile(file, {
          mode: "compress",
          maxDimension: 1920,
          quality: 0.82,
          targetMaxBytes: config?.image_max_bytes ?? 512 * 1024,
        });
        preparedImages.push({
          marker: createPendingImageMarker(),
          previewUrl: URL.createObjectURL(compressedFile),
          file: compressedFile,
          alt: sanitizeMarkdownImageAlt(file.name.replace(/\.[^.]+$/, "")),
        });
      }
      setPendingCommentImages((current) => [...current, ...preparedImages]);
    } catch (error) {
      setSubmitError(resolveApiError(error, t("waline.common.requestFailed")));
    } finally {
      setImageUploading(false);
      if (imageInputRef.current) {
        imageInputRef.current.value = "";
      }
    }
  }, [authSession, config?.image_max_bytes, draft.body, imageLimitMessageKey, imageUploadsEnabled, isGuestbook, pendingCommentImages.length, requiresAuthentication, t]);

  const handleRemovePendingCommentImage = useCallback((marker: string) => {
    setPendingCommentImages((current) => {
      const removed = current.find((item) => item.marker === marker);
      if (removed) {
        URL.revokeObjectURL(removed.previewUrl);
      }
      return current.filter((item) => item.marker !== marker);
    });
    setSubmitError(null);
    setSubmitNotice(null);
  }, []);

  const handleLogout = useCallback(() => {
    setAuthError(null);
    void logout();
  }, [logout]);

  const handleSubmit = useCallback(async () => {
    if (requiresAuthentication && !authSession) {
      setSubmitError(isGuestbook ? t("waline.surface.loginRequiredGuestbook") : t("waline.surface.loginRequiredComment"));
      return;
    }

    const authorName = authSession?.display_name?.trim() || draft.name.trim();
    const authorEmail = authSession?.email?.trim() || draft.email.trim();
    const authorWebsite = authSession?.url?.trim() || draft.website.trim();
    const avatarKey = authSession ? `oauth-${authSession.objectId}` : draft.avatarKey;

    if (!authSession && !authorName) {
      setSubmitError(t("waline.surface.nicknameRequired"));
      return;
    }
    if (!authSession && !authorEmail) {
      setSubmitError(t("waline.surface.emailRequired"));
      return;
    }
    const draftBody = draft.body.trim();
    if (!draftBody && pendingCommentImages.length === 0) {
      setSubmitError(isGuestbook ? t("waline.surface.guestbookBodyRequired") : t("waline.surface.commentBodyRequired"));
      return;
    }
    if (countCommentImages(draftBody) + pendingCommentImages.length > MAX_IMAGES_PER_COMMENT) {
      setSubmitError(t(imageLimitMessageKey, {
        count: MAX_IMAGES_PER_COMMENT,
      }));
      return;
    }
    if (!authSession && !avatarKey) {
      setSubmitError(t("waline.surface.avatarRequired"));
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    setSubmitNotice(null);

    try {
      let bodyForSubmit = draftBody;
      if (pendingCommentImages.length > 0) {
        setImageUploading(true);
        const uploadedImages: string[] = [];
        try {
          for (const item of pendingCommentImages) {
            const response = await uploadCommentImageApiV1SiteInteractionsCommentImagePost(
              { file: item.file } as never,
              { surface: isGuestbook ? "guestbook" : "comment" },
            );
            const imageUrl = response.data.data?.url;
            if (!imageUrl) {
              throw new Error(t("waline.surface.imageUploadMissingUrl"));
            }
            uploadedImages.push(`![${item.alt}](${imageUrl})`);
          }
        } finally {
          setImageUploading(false);
        }

        bodyForSubmit = [
          uploadedImages.join("\n"),
          draftBody,
        ].filter(Boolean).join("\n\n");

        setDraft((current) => ({ ...current, body: bodyForSubmit }));
        setPendingCommentImages((current) => {
          for (const item of current) {
            URL.revokeObjectURL(item.previewUrl);
          }
          return [];
        });
      }

      if (isGuestbook) {
        const payload = {
          name: authorName,
          email: authorEmail,
          website: authorWebsite || null,
          body: bodyForSubmit,
          avatar_key: avatarKey,
        };
        const response = await createGuestbookApiV1SiteInteractionsGuestbookPost(payload as never);
        const created = response.data.item as CommunityGuestbookItem;
        if (created.status === "pending") {
          setPendingGuestbookEntries((current) => [created, ...current.filter((item) => item.id !== created.id)]);
        } else {
          setEntryTotal((current) => current + 1);
        }
      } else {
        const payload = {
          author_name: authorName,
          author_email: authorEmail,
          body: bodyForSubmit,
          parent_id: replyTarget?.id ?? null,
          avatar_key: avatarKey,
          ...(commentFeedbackAvailable ? { feedback_enabled: feedbackEnabled } : {}),
        };
        const response = await createCommentApiV1SiteInteractionsCommentsContentTypeSlugPost(surface, slug ?? "", payload as never);
        const created = response.data.item as CommunityCommentItem;
        if (created.status === "pending") {
          setPendingComments((current) => [created, ...current.filter((item) => item.id !== created.id)]);
        } else {
          setEntryTotal((current) => current + 1);
        }
      }

      setDraft((current) => ({ ...current, body: "" }));
      setReplyTarget(null);
      setComposerOpen(false);
      setSubmitNotice(t("waline.surface.submitNotice"));
      invalidateCommunityEntryCache(surface, slug);
      startTransition(() => {
        void loadEntries(loadedPageCount, {
          silent: true,
          forceNetwork: true,
        });
      });
    } catch (error) {
      setSubmitError(resolveApiError(error, t("waline.common.requestFailed")));
    } finally {
      setSubmitting(false);
    }
  }, [authSession, commentFeedbackAvailable, draft, feedbackEnabled, imageLimitMessageKey, isGuestbook, loadEntries, loadedPageCount, pendingCommentImages, requiresAuthentication, replyTarget, slug, surface, t]);

  const setItemBusy = useCallback((itemId: string, busy: boolean) => {
    setBusyItemIds((current) => {
      const next = new Set(current);
      if (busy) {
        next.add(itemId);
      } else {
        next.delete(itemId);
      }
      return next;
    });
  }, []);

  const handleDeleteComment = useCallback(async (commentId: string) => {
    if (!window.confirm(t("waline.list.confirmDeleteComment"))) {
      return;
    }
    setItemBusy(commentId, true);
    setSubmitError(null);
    const deletedComment = findCommentInTree(comments, commentId);
    const deletedApprovedCount = deletedComment ? countCommentTree([deletedComment]) : 0;
    try {
      await deleteCommentApiV1SiteInteractionsCommentsCommentIdDelete(commentId);
      setComments((current) => removeCommentFromTree(current, commentId));
      setPendingComments((current) => removeCommentFromTree(current, commentId));
      if (deletedApprovedCount > 0) {
        setEntryTotal((current) => Math.max(0, current - deletedApprovedCount));
      }
      invalidateCommunityEntryCache(surface, slug);
      startTransition(() => {
        void loadEntries(loadedPageCount, {
          silent: true,
          forceNetwork: true,
        });
      });
    } catch (error) {
      setSubmitError(resolveApiError(error, t("waline.common.requestFailed")));
    } finally {
      setItemBusy(commentId, false);
    }
  }, [comments, loadEntries, loadedPageCount, setItemBusy, slug, surface, t]);

  const handleDeleteGuestbookEntry = useCallback(async (entryId: string) => {
    if (!window.confirm(t("waline.list.confirmDeleteGuestbook"))) {
      return;
    }
    setItemBusy(entryId, true);
    setSubmitError(null);
    const deletedApprovedEntry = guestbookEntries.some((item) => item.id === entryId);
    try {
      await deleteGuestbookEntryApiV1SiteInteractionsGuestbookEntryIdDelete(entryId);
      setGuestbookEntries((current) => current.filter((item) => item.id !== entryId));
      setPendingGuestbookEntries((current) => current.filter((item) => item.id !== entryId));
      if (deletedApprovedEntry) {
        setEntryTotal((current) => Math.max(0, current - 1));
      }
      invalidateCommunityEntryCache(surface, slug);
      startTransition(() => {
        void loadEntries(loadedPageCount, {
          silent: true,
          forceNetwork: true,
        });
      });
    } catch (error) {
      setSubmitError(resolveApiError(error, t("waline.common.requestFailed")));
    } finally {
      setItemBusy(entryId, false);
    }
  }, [guestbookEntries, loadEntries, loadedPageCount, setItemBusy, slug, surface, t]);

  const handleFeedbackChange = useCallback(async (commentId: string, enabled: boolean) => {
    if (!commentFeedbackAvailable) {
      return;
    }
    setItemBusy(commentId, true);
    setSubmitError(null);
    const updateLocal = (item: CommunityCommentItem): CommunityCommentItem => ({
      ...item,
      feedback_enabled: enabled,
    });
    setComments((current) => updateCommentInTree(current, commentId, updateLocal));
    setPendingComments((current) => updateCommentInTree(current, commentId, updateLocal));
    try {
      const response = await updateCommentFeedbackApiV1SiteInteractionsCommentsCommentIdFeedbackPatch(
        commentId,
        { feedback_enabled: enabled } as never,
      );
      const updated = response.data as CommunityCommentItem;
      setComments((current) => updateCommentInTree(current, commentId, () => updated));
      setPendingComments((current) => updateCommentInTree(current, commentId, () => updated));
      invalidateCommunityEntryCache(surface, slug);
    } catch (error) {
      const rollback = (item: CommunityCommentItem): CommunityCommentItem => ({
        ...item,
        feedback_enabled: !enabled,
      });
      setComments((current) => updateCommentInTree(current, commentId, rollback));
      setPendingComments((current) => updateCommentInTree(current, commentId, rollback));
      setSubmitError(resolveApiError(error, t("waline.common.requestFailed")));
    } finally {
      setItemBusy(commentId, false);
    }
  }, [commentFeedbackAvailable, setItemBusy, slug, surface, t]);

  const selectedPreset = avatarPresets.find((preset) => preset.key === draft.avatarKey) ?? avatarPresets[0] ?? null;
  const visibleEntryCount = entryTotal + (
    isGuestbook ? pendingGuestbookEntries.length : countCommentTree(pendingComments)
  );
  useEffect(() => {
    onVisibleCountChange?.(visibleEntryCount);
  }, [onVisibleCountChange, visibleEntryCount]);

  const toggleAvatarPicker = useCallback(() => {
    setAvatarPickerOpen((current) => {
      if (!current) {
        setRefreshSeed((value) => value + 1);
      }
      return !current;
    });
  }, []);

  const handleReply = useCallback((target: ReplyTarget) => {
    setReplyTarget(target);
    setComposerOpen(true);
  }, []);

  const isModalLayout = layout === "modal";
  const isComposerPinned = composerOpen;
  const shouldShowCommentList = !isModalLayout || !composerOpen;
  const composer = (
    <div className={`${communityPanelClass} aerisun-community-surface__composer scrollbar-hide ${isComposerPinned ? "aerisun-community-surface__composer--open" : "aerisun-community-surface__composer--collapsed py-4"}`.trim()}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="inline-flex items-center gap-2 text-[0.72rem] font-medium uppercase tracking-[0.22em] text-foreground/42">
            <Sparkles className="h-3.5 w-3.5" />
            {isGuestbook ? t("waline.surface.sectionGuestbook") : t("waline.surface.sectionComments")}
          </div>
          <motion.button
            type="button"
            onClick={() => setComposerOpen((current) => !current)}
            whileTap={prefersReducedMotion ? undefined : { scale: 0.98 }}
            transition={transition({ duration: 0.16, reducedMotion: prefersReducedMotion })}
            className="inline-flex items-center gap-2 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.76] px-4 py-1.5 text-sm font-medium text-foreground/60 transition hover:border-[rgb(var(--shiro-accent-rgb)/0.22)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] dark:bg-card/[0.82]"
          >
            <PencilLine className="h-4 w-4" />
            {composerOpen
              ? (replyTarget ? t("waline.surface.collapseReplyBox") : t("waline.surface.collapseEditor"))
              : replyTarget
                ? t("waline.surface.writeReply")
                : isGuestbook
                  ? t("waline.surface.writeGuestbook")
                  : t("waline.surface.writeComment")}
          </motion.button>
        </div>

        <div className={isComposerPinned ? "mt-4 space-y-3" : "mt-0"}>
          <WalineCommentForm
            authLoading={authLoading}
            authSession={authSession}
            authError={authError}
            requiresAuthentication={requiresAuthentication}
            commentEmailLoginEnabled={commentEmailLoginEnabled}
            loginMethodLabels={loginMethodLabels}
            hasLoginMethod={hasLoginMethod}
            onOpenLogin={openLogin}
            onLogout={handleLogout}
            draft={draft}
            onFieldChange={handleFieldChange}
            feedbackEnabled={feedbackEnabled}
            commentFeedbackAvailable={commentFeedbackAvailable}
            onFeedbackEnabledChange={setFeedbackEnabled}
            composerOpen={isComposerPinned}
            isGuestbook={isGuestbook}
            replyTarget={replyTarget}
            onClearReply={() => setReplyTarget(null)}
            editorMode={editorMode}
            onSetEditorMode={setEditorMode}
            deferredBody={deferredBody}
            textareaRef={textareaRef}
            emojiPickerOpen={emojiPickerOpen}
            onToggleEmojiPicker={() => setEmojiPickerOpen((current) => !current)}
            emojiChoices={EMOJI_CHOICES}
            onEmojiInsert={handleEmojiInsert}
            emojiPickerRef={emojiPickerRef}
            imageUploadsEnabled={imageUploadsEnabled && (!requiresAuthentication || Boolean(authSession))}
            imageUploading={imageUploading}
            imageInputRef={imageInputRef}
            onImageUpload={(files) => void handleImageUpload(files)}
            pendingImages={pendingCommentImages}
            onRemovePendingImage={handleRemovePendingCommentImage}
            avatarPickerOpen={avatarPickerOpen}
            avatarPickerRef={avatarPickerRef}
            onToggleAvatarPicker={toggleAvatarPicker}
            onCloseAvatarPicker={() => setAvatarPickerOpen(false)}
            avatarPresets={avatarPresets}
            selectedPreset={selectedPreset}
            isAvatarOccupied={isAvatarOccupied}
            submitting={submitting}
            submitError={submitError}
            submitNotice={submitNotice}
            onSubmit={() => void handleSubmit()}
            prefersReducedMotion={prefersReducedMotion}
            guestbookBodyPlaceholder={guestbookBodyPlaceholder}
            guestbookSubmitLabel={guestbookSubmitLabel}
            guestbookSubmittingLabel={guestbookSubmittingLabel}
          />
        </div>
    </div>
  );
  const commentList = (
    <div className="aerisun-community-surface__list scrollbar-hide">
      <WalineCommentList
        isGuestbook={isGuestbook}
        loadingConfig={loadingConfig}
        loadingEntries={loadingEntries}
        loadingMoreEntries={loadingMoreEntries}
        loadError={loadError}
        comments={comments}
        guestbookEntries={guestbookEntries}
        pendingComments={pendingComments}
        pendingGuestbookEntries={pendingGuestbookEntries}
        hasMoreEntries={hasMoreEntries}
        busyItemIds={busyItemIds}
        commentFeedbackAvailable={commentFeedbackAvailable}
        onReply={handleReply}
        onDeleteComment={(commentId) => void handleDeleteComment(commentId)}
        onDeleteGuestbookEntry={(entryId) => void handleDeleteGuestbookEntry(entryId)}
        onFeedbackChange={(commentId, enabled) => void handleFeedbackChange(commentId, enabled)}
        onLoadMore={loadMoreEntries}
        onRetry={() => void loadEntries(loadedPageCount, { forceNetwork: true })}
        guestbookLoadingLabel={guestbookLoadingLabel}
        guestbookRetryLabel={guestbookRetryLabel}
        guestbookEmptyMessage={guestbookEmptyMessage}
      />
    </div>
  );

  return (
    <section className={`aerisun-community-surface ${isModalLayout ? "aerisun-community-surface--modal" : "space-y-5"} ${className ?? ""}`.trim()}>
      {composer}
      {shouldShowCommentList ? commentList : null}
    </section>
  );
};

export default WalineSurface;
