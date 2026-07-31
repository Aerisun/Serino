import { useId, useState, type RefObject } from "react";
import {
  ArrowUpRight,
  CornerDownRight,
  Eye,
  ImagePlus,
  Loader2,
  LockKeyhole,
  PencilLine,
  Send,
  Smile,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { transition } from "@/config";
import type { AvatarPreset } from "@/lib/community-config";
import { useFrontendI18n } from "@/i18n";
import CommentMarkdownRenderer from "@/components/CommentMarkdownRenderer";
import WalineAvatarSelector from "./WalineAvatarSelector";
import {
  communityActionClass,
  communityChipClass,
  communityEmojiPopupClass,
  communityInputClass,
  communityTextareaClass,
  scrollToCommentTarget,
  type DraftState,
  type EditorMode,
  type EmojiChoice,
  type ReplyTarget,
} from "./waline-types";

interface AuthSession {
  objectId: string;
  display_name: string;
  email: string;
  url: string;
  avatar: string;
  is_admin: boolean;
}

interface PendingCommentImagePreview {
  marker: string;
  previewUrl: string;
  alt: string;
}

const CommentFeedbackHelp = () => {
  const { t } = useFrontendI18n();
  const [open, setOpen] = useState(false);
  const panelId = useId();

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-[rgb(var(--shiro-border-rgb)/0.2)] text-[0.68rem] font-semibold text-foreground/45 transition hover:border-[rgb(var(--shiro-accent-rgb)/0.24)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)]"
        aria-label={t("waline.form.feedbackHelpAria")}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((current) => !current)}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
      >
        ?
      </button>
      {open ? (
        <span
          id={panelId}
          role="tooltip"
          className="absolute bottom-[calc(100%+0.55rem)] left-0 z-20 w-[min(18rem,calc(100vw-2rem))] rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-background/[0.96] px-3.5 py-3 text-left text-xs leading-5 text-foreground/68 shadow-[0_18px_48px_rgb(15_23_42/0.14)] backdrop-blur-xl dark:bg-card/[0.98]"
        >
          {t("waline.form.feedbackHelp")}
        </span>
      ) : null}
    </span>
  );
};

export interface WalineCommentFormProps {
  /* Auth */
  authLoading: boolean;
  authSession: AuthSession | null;
  authError: string | null;
  requiresAuthentication: boolean;
  commentEmailLoginEnabled: boolean;
  loginMethodLabels: string[];
  hasLoginMethod: boolean;
  onOpenLogin: (opts: { allowEmailLogin: boolean }) => void;
  onLogout: () => void;

  /* Draft state */
  draft: DraftState;
  onFieldChange: (field: keyof DraftState, value: string) => void;
  feedbackEnabled: boolean;
  commentFeedbackAvailable: boolean;
  onFeedbackEnabledChange: (enabled: boolean) => void;

  /* Composer toggle */
  composerOpen: boolean;
  isGuestbook: boolean;

  /* Reply */
  replyTarget: ReplyTarget | null;
  onClearReply: () => void;

  /* Editor mode */
  editorMode: EditorMode;
  onSetEditorMode: (mode: EditorMode) => void;
  deferredBody: string;
  textareaRef: RefObject<HTMLTextAreaElement | null>;

  /* Emoji */
  emojiPickerOpen: boolean;
  onToggleEmojiPicker: () => void;
  emojiChoices: EmojiChoice[];
  onEmojiInsert: (emoji: string) => void;
  emojiPickerRef: RefObject<HTMLDivElement | null>;

  /* Image upload */
  imageUploadsEnabled: boolean;
  imageUploading: boolean;
  imageInputRef: RefObject<HTMLInputElement | null>;
  onImageUpload: (files: File[]) => void;
  pendingImages: PendingCommentImagePreview[];
  onRemovePendingImage: (marker: string) => void;

  /* Avatar picker */
  avatarPickerOpen: boolean;
  avatarPickerRef: RefObject<HTMLDivElement | null>;
  onToggleAvatarPicker: () => void;
  onCloseAvatarPicker: () => void;
  avatarPresets: AvatarPreset[];
  selectedPreset: AvatarPreset | null;
  isAvatarOccupied: (preset: AvatarPreset) => boolean;

  /* Submit */
  submitting: boolean;
  submitError: string | null;
  submitNotice: string | null;
  onSubmit: () => void;

  /* Animation */
  prefersReducedMotion: boolean;

  /* Guestbook labels */
  guestbookBodyPlaceholder: string;
  guestbookSubmitLabel: string;
  guestbookSubmittingLabel: string;
}

const WalineCommentForm = ({
  authLoading,
  authSession,
  authError,
  requiresAuthentication,
  commentEmailLoginEnabled,
  hasLoginMethod,
  onOpenLogin,
  draft,
  onFieldChange,
  feedbackEnabled,
  commentFeedbackAvailable,
  onFeedbackEnabledChange,
  composerOpen,
  isGuestbook,
  replyTarget,
  onClearReply,
  editorMode,
  onSetEditorMode,
  deferredBody,
  textareaRef,
  emojiPickerOpen,
  onToggleEmojiPicker,
  emojiChoices,
  onEmojiInsert,
  emojiPickerRef,
  imageUploadsEnabled,
  imageUploading,
  imageInputRef,
  onImageUpload,
  pendingImages,
  onRemovePendingImage,
  avatarPickerOpen,
  avatarPickerRef,
  onToggleAvatarPicker,
  onCloseAvatarPicker,
  avatarPresets,
  selectedPreset,
  isAvatarOccupied,
  submitting,
  submitError,
  submitNotice,
  onSubmit,
  prefersReducedMotion,
  guestbookBodyPlaceholder,
  guestbookSubmitLabel,
  guestbookSubmittingLabel,
}: WalineCommentFormProps) => {
  const { t } = useFrontendI18n();
  const showAuthGate = !authLoading && requiresAuthentication && !authSession;
  const showEditorControls = !requiresAuthentication || Boolean(authSession);

  return (
    <AnimatePresence initial={false}>
      {composerOpen ? (
        <motion.div
          key="composer-open"
          initial={{ height: 0, opacity: 0, y: prefersReducedMotion ? 0 : 6 }}
          animate={{ height: "auto", opacity: 1, y: 0 }}
          exit={{ height: 0, opacity: 0, y: prefersReducedMotion ? 0 : 6 }}
          transition={transition({ duration: 0.26, reducedMotion: prefersReducedMotion })}
          className={emojiPickerOpen || avatarPickerOpen ? "aerisun-comment-form-motion overflow-visible" : "aerisun-comment-form-motion overflow-hidden"}
        >
          <div ref={avatarPickerRef} className="space-y-4">
            {/* Auth status section */}
            {authLoading ? (
              <div className="rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.7] px-4 py-3 text-sm text-foreground/48 dark:bg-card/[0.78]">
                {t("waline.form.checkingAuth")}
              </div>
            ) : showAuthGate ? (
              <div className="flex flex-col items-center gap-4 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.72] px-4 py-5 text-center dark:bg-card/[0.82]">
                <p className="text-sm font-medium text-foreground">{t("waline.form.loginRequiredTitle")}</p>
                <button
                  type="button"
                  onClick={() => onOpenLogin({ allowEmailLogin: commentEmailLoginEnabled })}
                  disabled={!hasLoginMethod}
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-[rgb(var(--shiro-accent-rgb)/0.24)] bg-[rgb(var(--shiro-accent-rgb)/0.1)] px-4 py-2.5 text-sm font-semibold text-[rgb(var(--shiro-accent-rgb)/0.88)] transition hover:bg-[rgb(var(--shiro-accent-rgb)/0.14)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <LockKeyhole className="h-4 w-4" />
                  {t("waline.form.loginToComment")}
                </button>
              </div>
            ) : null}

            {authError ? (
              <div className="rounded-2xl border border-amber-500/18 bg-amber-500/8 px-4 py-3 text-sm text-amber-700 dark:text-amber-300">
                {authError}
              </div>
            ) : null}

            {showEditorControls ? (
              <>
                {/* Guest identity fields + avatar selector */}
                {!authSession ? (
                  <div className="relative">
                    {!requiresAuthentication ? (
                      <div className="grid grid-cols-[auto_minmax(0,1fr)] items-end gap-3 md:grid-cols-[auto_minmax(0,0.92fr)_minmax(0,1.08fr)] md:gap-4">
                        <WalineAvatarSelector
                          avatarPresets={avatarPresets}
                          selectedAvatarKey={draft.avatarKey}
                          draftName={draft.name}
                          isAvatarOccupied={isAvatarOccupied}
                          open={avatarPickerOpen}
                          onSelect={onFieldChange}
                          onClose={onCloseAvatarPicker}
                          onToggle={onToggleAvatarPicker}
                          selectedPreset={selectedPreset}
                        />

                        <label className="space-y-2">
                          <span className="text-xs font-medium uppercase tracking-[0.22em] text-foreground/40">{t("common.nickname")}</span>
                          <input
                            value={draft.name}
                            onChange={(event) => onFieldChange("name", event.target.value)}
                            placeholder={t("waline.form.nicknamePlaceholder")}
                            className={communityInputClass}
                          />
                        </label>
                        <label className="col-span-full space-y-2 md:col-span-1">
                          <span className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.22em] text-foreground/40">
                            {t("common.email")}
                            <LockKeyhole className="h-3.5 w-3.5" />
                          </span>
                          <input
                            type="email"
                            value={draft.email}
                            onChange={(event) => onFieldChange("email", event.target.value)}
                            placeholder={t("waline.form.emailPlaceholder")}
                            className={communityInputClass}
                          />
                        </label>
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {/* Reply target indicator */}
                {replyTarget ? (
                  <div className="shiro-accent-panel flex flex-wrap items-center gap-2 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] px-4 py-3 text-sm text-foreground/62">
                    <CornerDownRight className="h-4 w-4" />
                    <button
                      type="button"
                      onClick={() => scrollToCommentTarget(replyTarget.id)}
                      className="aerisun-comment-context"
                    >
                      <ArrowUpRight className="h-3.5 w-3.5" />
                      {t("waline.form.replyingTo", { name: replyTarget.name })}
                    </button>
                    <button
                      type="button"
                      onClick={onClearReply}
                      className={`${communityActionClass} px-2 text-xs`}
                    >
                      <X className="h-3.5 w-3.5" />
                      {t("waline.form.cancelReply")}
                    </button>
                  </div>
                ) : null}

                {/* Editor area */}
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5 whitespace-nowrap sm:flex-wrap sm:justify-between sm:gap-3">
                    {/* Write / preview tabs */}
                    <div className="inline-flex shrink-0 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.74] p-0.5 sm:p-1 dark:bg-card/[0.8]">
                      <button
                        type="button"
                        onClick={() => onSetEditorMode("write")}
                        className={`inline-flex items-center gap-0.5 rounded-full px-2 py-1.5 text-[11px] transition sm:gap-1.5 sm:px-3 sm:text-xs ${
                          editorMode === "write"
                            ? "bg-[rgb(var(--shiro-accent-rgb)/0.12)] text-[rgb(var(--shiro-accent-rgb)/0.88)]"
                            : "text-foreground/52 hover:text-foreground/76"
                        }`}
                      >
                        <PencilLine className="h-3 w-3 sm:h-3.5 sm:w-3.5" />
                        {t("waline.form.edit")}
                      </button>
                      <button
                        type="button"
                        onClick={() => onSetEditorMode("preview")}
                        className={`inline-flex items-center gap-0.5 rounded-full px-2 py-1.5 text-[11px] transition sm:gap-1.5 sm:px-3 sm:text-xs ${
                          editorMode === "preview"
                            ? "bg-[rgb(var(--shiro-accent-rgb)/0.12)] text-[rgb(var(--shiro-accent-rgb)/0.88)]"
                            : "text-foreground/52 hover:text-foreground/76"
                        }`}
                      >
                        <Eye className="h-3 w-3 sm:h-3.5 sm:w-3.5" />
                        {t("waline.form.preview")}
                      </button>
                    </div>

                    {/* Emoji + image buttons */}
                    <div className="ml-auto flex items-center gap-1.5 whitespace-nowrap pl-2 sm:ml-0 sm:gap-2 sm:pl-0">
                      <div ref={emojiPickerRef} className="relative hidden shrink-0 sm:block">
                          <button
                            type="button"
                            onClick={onToggleEmojiPicker}
                            className={`${communityChipClass} gap-0.5 px-2 py-1.5 text-[11px] sm:gap-1.5 sm:px-3 sm:text-xs`}
                            aria-expanded={emojiPickerOpen}
                            aria-label={t("waline.form.openEmojiPicker")}
                          >
                            <Smile className="h-3 w-3 sm:h-3.5 sm:w-3.5" />
                            {t("waline.form.emoji")}
                          </button>
                          {emojiPickerOpen ? (
                            <div className={communityEmojiPopupClass}>
                              <div className="max-h-[min(20rem,60vh)] overflow-y-auto overscroll-contain pr-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                                <div className="grid grid-cols-6 gap-2 sm:grid-cols-7">
                                  {emojiChoices.map((choice, index) => (
                                    <button
                                      key={`${choice.emoji}-${index}`}
                                      type="button"
                                      title={choice.label}
                                      onClick={() => onEmojiInsert(choice.emoji)}
                                      className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-transparent bg-background/[0.76] text-base transition hover:border-[rgb(var(--shiro-accent-rgb)/0.2)] hover:bg-[rgb(var(--shiro-accent-rgb)/0.12)] dark:bg-card/[0.82]"
                                    >
                                      {choice.emoji}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            </div>
                          ) : null}
                        </div>

                      {imageUploadsEnabled ? (
                        <>
                          <button
                            type="button"
                            onClick={() => imageInputRef.current?.click()}
                            disabled={imageUploading}
                            className={`${communityChipClass} shrink-0 gap-0.5 px-2 py-1.5 text-[11px] sm:gap-1.5 sm:px-3 sm:text-xs disabled:cursor-not-allowed disabled:opacity-60`}
                          >
                            {imageUploading ? <Loader2 className="h-3 w-3 animate-spin sm:h-3.5 sm:w-3.5" /> : <ImagePlus className="h-3 w-3 sm:h-3.5 sm:w-4" />}
                            {t("waline.form.image")}
                          </button>
                          <input
                            ref={imageInputRef}
                            type="file"
                            accept="image/*"
                            multiple
                            className="hidden"
                            onChange={(event) => {
                              const files = Array.from(event.target.files ?? []);
                              if (files.length > 0) {
                                onImageUpload(files);
                              }
                            }}
                          />
                        </>
                      ) : null}
                    </div>
                  </div>

                  {pendingImages.length > 0 ? (
                    <div className="aerisun-comment-attachment-picker">
                      {pendingImages.map((image) => (
                        <div key={image.marker} className="aerisun-comment-attachment-picker__item">
                          <img
                            src={image.previewUrl}
                            alt={image.alt}
                            loading="lazy"
                            decoding="async"
                          />
                          <button
                            type="button"
                            className="aerisun-comment-attachment-picker__remove"
                            onClick={() => onRemovePendingImage(image.marker)}
                            aria-label={image.alt ? `移除图片：${image.alt}` : "移除图片"}
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : null}

                  {/* Textarea / preview area */}
                  {editorMode === "preview" ? (
                    <div className="min-h-[160px] rounded-[1.4rem] border border-[rgb(var(--shiro-border-rgb)/0.28)] bg-background/[0.82] px-4 py-4 dark:border-[rgb(var(--shiro-border-rgb)/0.32)] dark:bg-card/[0.9]">
                      {deferredBody.trim() ? (
                        <CommentMarkdownRenderer
                          content={deferredBody}
                          className="aerisun-comment-preview"
                        />
                      ) : (
                        <div className="flex min-h-[128px] items-center justify-center text-sm text-foreground/42">
                          {t("waline.form.previewPlaceholder")}
                        </div>
                      )}
                    </div>
                  ) : (
                    <textarea
                      ref={textareaRef}
                      value={draft.body}
                      onChange={(event) => onFieldChange("body", event.target.value)}
                      placeholder={isGuestbook ? guestbookBodyPlaceholder : t("waline.form.commentPlaceholder")}
                      wrap="soft"
                      className={communityTextareaClass}
                    />
                  )}
                </div>

                {/* Error / notice */}
                {submitError ? (
                  <div className="rounded-2xl border border-red-500/18 bg-red-500/8 px-4 py-3 text-sm text-red-600 dark:text-red-300">
                    {submitError}
                  </div>
                ) : null}
                {submitNotice ? (
                  <div className="rounded-2xl border border-emerald-500/18 bg-emerald-500/8 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">
                    {submitNotice}
                  </div>
                ) : null}

                {/* Footer: feedback + submit */}
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    {!isGuestbook && commentFeedbackAvailable ? (
                      <div className="inline-flex items-center gap-2 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.58] px-2.5 py-1.5 text-xs text-foreground/56 dark:bg-card/[0.66]">
                        <button
                          type="button"
                          role="switch"
                          aria-checked={feedbackEnabled}
                          onClick={() => onFeedbackEnabledChange(!feedbackEnabled)}
                          className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition ${
                            feedbackEnabled
                              ? "border-[rgb(var(--shiro-accent-rgb)/0.28)] bg-[rgb(var(--shiro-accent-rgb)/0.18)]"
                              : "border-[rgb(var(--shiro-border-rgb)/0.24)] bg-foreground/[0.06]"
                          }`}
                        >
                          <span
                            className={`block h-4 w-4 rounded-full bg-background shadow-sm transition-transform dark:bg-foreground ${
                              feedbackEnabled ? "translate-x-4" : "translate-x-0.5"
                            }`}
                          />
                        </button>
                        <span className="whitespace-nowrap">{t("waline.form.feedbackLabel")}</span>
                        <CommentFeedbackHelp />
                      </div>
                    ) : (
                      <p className="text-xs leading-6 text-foreground/42">
                        {authSession
                          ? t("waline.form.submitQueuedHint")
                          : t("waline.form.loginBeforeSubmitHint")}
                      </p>
                    )}
                  </div>
                  <div className="ml-auto flex flex-wrap items-center justify-end gap-3">
                    <span className="text-xs leading-6 text-foreground/42">
                      {t("waline.form.selfDeleteHint")}
                    </span>
                  <button
                    type="button"
                    onClick={onSubmit}
                    disabled={submitting}
                    className="inline-flex items-center gap-2 rounded-full border border-[rgb(var(--shiro-accent-rgb)/0.24)] bg-[rgb(var(--shiro-accent-rgb)/0.1)] px-5 py-2.5 text-sm font-semibold text-[rgb(var(--shiro-accent-rgb)/0.88)] transition hover:bg-[rgb(var(--shiro-accent-rgb)/0.14)] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                    {submitting
                      ? (isGuestbook ? guestbookSubmittingLabel : t("waline.form.submitLoading"))
                      : isGuestbook
                        ? guestbookSubmitLabel
                        : replyTarget
                          ? t("waline.form.submitReply")
                          : t("waline.form.submitComment")}
                  </button>
                  </div>
                </div>
              </>
            ) : null}
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
};

export default WalineCommentForm;
