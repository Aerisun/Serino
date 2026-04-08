import { type RefObject } from "react";
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
  Sparkles,
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
  fallbackAvatar,
  scrollToCommentTarget,
  StatusPill,
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
  onImageUpload: (file: File) => void;

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

  return (
    <AnimatePresence initial={false}>
      {composerOpen ? (
        <motion.div
          key="composer-open"
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={transition({ duration: 0.3, reducedMotion: prefersReducedMotion })}
          className={emojiPickerOpen || avatarPickerOpen ? "overflow-visible" : "overflow-hidden"}
        >
          <div ref={avatarPickerRef} className="space-y-4">
            {replyTarget ? (
              <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.72] px-4 py-3 text-sm text-foreground/48 dark:bg-card/[0.82]">
                <Sparkles className="h-4 w-4" />
                <button
                  type="button"
                  onClick={() => scrollToCommentTarget(replyTarget.id)}
                  className="aerisun-comment-context"
                >
                  <ArrowUpRight className="h-3.5 w-3.5" />
                  {t("waline.form.replyingTo", { name: replyTarget.name })}
                </button>
              </div>
            ) : null}

            {/* Auth status section */}
            {authLoading ? (
              <div className="rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.7] px-4 py-3 text-sm text-foreground/48 dark:bg-card/[0.78]">
                {t("waline.form.checkingAuth")}
              </div>
            ) : authSession ? (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.72] px-4 py-3 dark:bg-card/[0.82]">
                <div className="flex items-center gap-3">
                  <img
                    src={authSession.avatar || fallbackAvatar(authSession.display_name)}
                    alt={authSession.display_name}
                    className="h-12 w-12 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] object-cover"
                  />
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-foreground">{authSession.display_name}</span>
                      <StatusPill text={authSession.is_admin ? t("waline.form.adminMode") : t("waline.form.loggedIn")} tone="author" />
                    </div>
                  </div>
                </div>
              </div>
            ) : requiresAuthentication ? (
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
                        className="hidden"
                        onChange={(event) => {
                          const file = event.target.files?.[0];
                          if (file) {
                            onImageUpload(file);
                          }
                        }}
                      />
                    </>
                  ) : null}
                </div>
              </div>

              {/* Textarea / preview area */}
              {editorMode === "preview" ? (
                <div className="min-h-[160px] rounded-[1.4rem] border border-[rgb(var(--shiro-border-rgb)/0.28)] bg-background/[0.82] px-4 py-4 dark:border-[rgb(var(--shiro-border-rgb)/0.32)] dark:bg-card/[0.9]">
                  {deferredBody.trim() ? (
                    <CommentMarkdownRenderer content={deferredBody} className="aerisun-comment-preview" />
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

            {/* Footer: hint + submit */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs leading-6 text-foreground/42">
                {authSession
                  ? t("waline.form.submitQueuedHint")
                  : t("waline.form.loginBeforeSubmitHint")}
              </p>
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
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
};

export default WalineCommentForm;
