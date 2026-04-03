import { startTransition, useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { PencilLine, Sparkles } from "lucide-react";
import {
  createCommentApiV1SiteInteractionsCommentsContentTypeSlugPost,
  createGuestbookApiV1SiteInteractionsGuestbookPost,
  readCommentsApiV1SiteInteractionsCommentsContentTypeSlugGet,
  readGuestbookApiV1SiteInteractionsGuestbookGet,
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
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import { prepareImageUploadFile } from "@serino/utils";
import WalineCommentForm from "./WalineCommentForm";
import WalineCommentList from "./WalineCommentList";
import {
  buildAvatarPresets,
  buildDefaultAvatarPreset,
  collectAvatarUsage,
  getLocalizedEmojiGroups,
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

export interface WalineSurfaceProps {
  surface: CommunitySurface;
  slug?: string;
  className?: string;
  communityConfig?: CommunityConfig | null;
}

const WalineSurface = ({
  surface,
  slug,
  className,
  communityConfig,
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
  const storageKey = `${PROFILE_STORAGE_PREFIX}${surface}:${slug ?? "guestbook"}`;
  const storedDraft = readStoredDraft(storageKey);
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
  const [pendingComments, setPendingComments] = useState<CommunityCommentItem[]>([]);
  const [pendingGuestbookEntries, setPendingGuestbookEntries] = useState<CommunityGuestbookItem[]>([]);
  const [draft, setDraft] = useState<DraftState>({
    name: typeof storedDraft.name === "string" ? storedDraft.name : "",
    email: typeof storedDraft.email === "string" ? storedDraft.email : "",
    website: typeof storedDraft.website === "string" ? storedDraft.website : "",
    body: "",
    avatarKey: typeof storedDraft.avatarKey === "string" ? storedDraft.avatarKey : "",
  });
  const [replyTarget, setReplyTarget] = useState<ReplyTarget | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitNotice, setSubmitNotice] = useState<string | null>(null);
  const [avatarPickerOpen, setAvatarPickerOpen] = useState(false);
  const [emojiPickerOpen, setEmojiPickerOpen] = useState(false);
  const [emojiQuery, setEmojiQuery] = useState("");
  const [editorMode, setEditorMode] = useState<EditorMode>("write");
  const [composerOpen, setComposerOpen] = useState(false);
  const [imageUploading, setImageUploading] = useState(false);
  const avatarPickerRef = useRef<HTMLDivElement | null>(null);
  const emojiPickerRef = useRef<HTMLDivElement | null>(null);
  const emojiSearchRef = useRef<HTMLInputElement | null>(null);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const deferredBody = useDeferredValue(draft.body);

  useEffect(() => {
    if (communityConfig) {
      setConfig(communityConfig);
      setLoadingConfig(false);
      return;
    }

    let active = true;
    setLoadingConfig(true);
    void loadCommunityConfig()
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
  const emojiSelectionEnabled = resolvedConfig.enable_enjoy_search !== false;
  const imageUploadsEnabled = resolvedConfig.image_uploader;
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

  const loadEntries = useCallback(async (requestedPageCount = 1) => {
    if (!isGuestbook && !slug) {
      setLoadError(t("waline.surface.missingPath"));
      setLoadingEntries(false);
      setLoadingMoreEntries(false);
      return;
    }

    const nextPageCount = Math.max(1, requestedPageCount);
    const loadMoreRequest = nextPageCount > 1;
    if (loadMoreRequest) {
      setLoadingMoreEntries(true);
    } else {
      setLoadingEntries(true);
    }
    setLoadError(null);

    try {
      if (isGuestbook) {
        const collected: CommunityGuestbookItem[] = [];
        let hasMore = false;
        let loadedPages = 0;
        for (let page = 1; page <= nextPageCount; page += 1) {
          const response = await readGuestbookApiV1SiteInteractionsGuestbookGet({
            page,
            page_size: initialPageSize,
          });
          collected.push(
            ...sortGuestbookEntries(
              response.data.items as CommunityGuestbookItem[],
              resolvedConfig.default_sorting,
            ),
          );
          hasMore = Boolean(response.data.has_more);
          loadedPages = page;
          if (!hasMore) {
            break;
          }
        }
        setGuestbookEntries(collected);
        setLoadedPageCount(loadedPages || 1);
        setHasMoreEntries(hasMore);
        return;
      }

      const collected: CommunityCommentItem[] = [];
      let hasMore = false;
      let loadedPages = 0;
      for (let page = 1; page <= nextPageCount; page += 1) {
        const response = await readCommentsApiV1SiteInteractionsCommentsContentTypeSlugGet(
          surface,
          slug ?? "",
          {
            page,
            page_size: initialPageSize,
          },
        );
        collected.push(
          ...sortComments(
            response.data.items as CommunityCommentItem[],
            resolvedConfig.default_sorting,
          ),
        );
        hasMore = Boolean(response.data.has_more);
        loadedPages = page;
        if (!hasMore) {
          break;
        }
      }
      setComments(collected);
      setLoadedPageCount(loadedPages || 1);
      setHasMoreEntries(hasMore);
    } catch (error) {
      setLoadError(resolveApiError(error, t("waline.common.requestFailed")));
    } finally {
      setLoadingEntries(false);
      setLoadingMoreEntries(false);
    }
  }, [initialPageSize, isGuestbook, resolvedConfig.default_sorting, slug, surface, t]);

  useEffect(() => {
    void loadEntries(1);
  }, [loadEntries]);

  const loadMoreEntries = useCallback(() => {
    if (loadingEntries || loadingMoreEntries || !hasMoreEntries) {
      return;
    }
    void loadEntries(loadedPageCount + 1);
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
    if (!emojiSelectionEnabled) {
      setEmojiPickerOpen(false);
      setEmojiQuery("");
    }
  }, [emojiSelectionEnabled]);

  useEffect(() => {
    if (!emojiPickerOpen) {
      setEmojiQuery("");
      return;
    }

    const frame = requestAnimationFrame(() => {
      emojiSearchRef.current?.focus();
    });

    return () => {
      cancelAnimationFrame(frame);
    };
  }, [emojiPickerOpen]);

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

  const deferredEmojiQuery = useDeferredValue(emojiQuery.trim().toLowerCase());
  const localizedEmojiGroups = useMemo(() => getLocalizedEmojiGroups(t), [t]);

  const filteredEmojiGroups = useMemo(() => {
    const query = deferredEmojiQuery;
    if (!query) {
      return localizedEmojiGroups;
    }
    return localizedEmojiGroups
      .map((group) => ({
        ...group,
        items: group.items.filter((choice) => {
          const label = choice.label.toLowerCase();
          return (
            choice.emoji.includes(query)
            || label.includes(query)
            || choice.keywords.some((keyword) => keyword.toLowerCase().includes(query))
          );
        }),
      }))
      .filter((group) => group.items.length > 0);
  }, [deferredEmojiQuery, localizedEmojiGroups]);

  const handleEmojiInsert = useCallback((emoji: string) => {
    if (!emojiSelectionEnabled) {
      return;
    }
    insertIntoBody(emoji);
    setEmojiPickerOpen(false);
  }, [emojiSelectionEnabled, insertIntoBody]);

  const handleImageUpload = useCallback(async (file: File) => {
    if (!imageUploadsEnabled) {
      setSubmitError(t("waline.surface.imageUploadDisabled"));
      if (imageInputRef.current) {
        imageInputRef.current.value = "";
      }
      return;
    }

    setImageUploading(true);
    setSubmitError(null);
    setSubmitNotice(null);

    try {
      const compressedFile = await prepareImageUploadFile(file, {
        mode: "compress",
        maxDimension: 1920,
        quality: 0.82,
        minBytesToCompress: config?.image_max_bytes ?? 512 * 1024,
      });
      const response = await uploadCommentImageApiV1SiteInteractionsCommentImagePost({ file: compressedFile } as never);
      const imageUrl = response.data.data?.url;
      if (!imageUrl) {
        throw new Error(t("waline.surface.imageUploadMissingUrl"));
      }
      const alt = file.name.replace(/\.[^.]+$/, "").trim() || "image";
      const prefix = draft.body.trim() ? "\n" : "";
      insertIntoBody(`${prefix}![${alt}](${imageUrl})\n`);
    } catch (error) {
      setSubmitError(resolveApiError(error, t("waline.common.requestFailed")));
    } finally {
      setImageUploading(false);
      if (imageInputRef.current) {
        imageInputRef.current.value = "";
      }
    }
  }, [config?.image_max_bytes, draft.body, imageUploadsEnabled, insertIntoBody, t]);

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
    if (!draft.body.trim()) {
      setSubmitError(isGuestbook ? t("waline.surface.guestbookBodyRequired") : t("waline.surface.commentBodyRequired"));
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
      if (isGuestbook) {
        const payload = {
          name: authorName,
          email: authorEmail,
          website: authorWebsite || null,
          body: draft.body.trim(),
          avatar_key: avatarKey,
        };
        const response = await createGuestbookApiV1SiteInteractionsGuestbookPost(payload as never);
        const created = response.data.item as CommunityGuestbookItem;
        setPendingGuestbookEntries((current) => [created, ...current]);
      } else {
        const payload = {
          author_name: authorName,
          author_email: authorEmail,
          body: draft.body.trim(),
          parent_id: replyTarget?.id ?? null,
          avatar_key: avatarKey,
        };
        const response = await createCommentApiV1SiteInteractionsCommentsContentTypeSlugPost(surface, slug ?? "", payload as never);
        const created = response.data.item as CommunityCommentItem;
        setPendingComments((current) => [created, ...current]);
      }

      setDraft((current) => ({ ...current, body: "" }));
      setReplyTarget(null);
      setComposerOpen(false);
      setSubmitNotice(t("waline.surface.submitNotice"));
      startTransition(() => {
        void loadEntries(loadedPageCount);
      });
    } catch (error) {
      setSubmitError(resolveApiError(error, t("waline.common.requestFailed")));
    } finally {
      setSubmitting(false);
    }
  }, [authSession, draft, isGuestbook, loadEntries, loadedPageCount, requiresAuthentication, replyTarget, slug, surface, t]);

  const selectedPreset = avatarPresets.find((preset) => preset.key === draft.avatarKey) ?? avatarPresets[0] ?? null;
  const toggleAvatarPicker = useCallback(() => {
    setAvatarPickerOpen((current) => {
      if (!current) {
        setRefreshSeed((value) => value + 1);
      }
      return !current;
    });
  }, []);

  return (
    <section className={`aerisun-community-surface space-y-5 ${className ?? ""}`.trim()}>
      <div className={`${communityPanelClass} ${composerOpen ? "" : "py-4"}`.trim()}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="inline-flex items-center gap-2 text-[0.72rem] font-medium uppercase tracking-[0.22em] text-foreground/42">
            <Sparkles className="h-3.5 w-3.5" />
            {isGuestbook ? t("waline.surface.sectionGuestbook") : t("waline.surface.sectionComments")}
          </div>
          <button
            type="button"
            onClick={() => setComposerOpen((current) => !current)}
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
          </button>
        </div>

        <div className={composerOpen ? "mt-4 space-y-3" : "mt-0"}>
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
            composerOpen={composerOpen}
            isGuestbook={isGuestbook}
            replyTarget={replyTarget}
            onClearReply={() => setReplyTarget(null)}
            editorMode={editorMode}
            onSetEditorMode={setEditorMode}
            deferredBody={deferredBody}
            textareaRef={textareaRef}
            emojiSelectionEnabled={emojiSelectionEnabled}
            emojiPickerOpen={emojiPickerOpen}
            onToggleEmojiPicker={() => setEmojiPickerOpen((current) => !current)}
            emojiQuery={emojiQuery}
            onEmojiQueryChange={setEmojiQuery}
            filteredEmojiGroups={filteredEmojiGroups}
            onEmojiInsert={handleEmojiInsert}
            emojiPickerRef={emojiPickerRef}
            emojiSearchRef={emojiSearchRef}
            imageUploadsEnabled={imageUploadsEnabled}
            imageUploading={imageUploading}
            imageInputRef={imageInputRef}
            onImageUpload={(file) => void handleImageUpload(file)}
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
        onReply={setReplyTarget}
        onLoadMore={loadMoreEntries}
        onRetry={() => void loadEntries(loadedPageCount)}
        guestbookLoadingLabel={guestbookLoadingLabel}
        guestbookRetryLabel={guestbookRetryLabel}
        guestbookEmptyMessage={guestbookEmptyMessage}
      />
    </section>
  );
};

export default WalineSurface;
