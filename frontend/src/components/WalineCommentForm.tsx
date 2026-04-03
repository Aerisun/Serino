import { type RefObject } from "react";
import {
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
import MarkdownRenderer from "@/components/MarkdownRenderer";
import WalineAvatarSelector from "./WalineAvatarSelector";
import {
  communityActionClass,
  communityChipClass,
  communityEmojiPopupClass,
  communityEmojiSearchClass,
  communityInputClass,
  communityTextareaClass,
  fallbackAvatar,
  StatusPill,
  type DraftState,
  type EditorMode,
  type EmojiGroup,
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
  emojiSelectionEnabled: boolean;
  emojiPickerOpen: boolean;
  onToggleEmojiPicker: () => void;
  emojiQuery: string;
  onEmojiQueryChange: (value: string) => void;
  filteredEmojiGroups: EmojiGroup[];
  onEmojiInsert: (emoji: string) => void;
  emojiPickerRef: RefObject<HTMLDivElement | null>;
  emojiSearchRef: RefObject<HTMLInputElement | null>;

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
  loginMethodLabels,
  hasLoginMethod,
  onOpenLogin,
  onLogout,
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
  emojiSelectionEnabled,
  emojiPickerOpen,
  onToggleEmojiPicker,
  emojiQuery,
  onEmojiQueryChange,
  filteredEmojiGroups,
  onEmojiInsert,
  emojiPickerRef,
  emojiSearchRef,
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
  return (
    <AnimatePresence initial={false}>
      {composerOpen ? (
        <motion.div
          key="composer-open"
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={transition({ duration: 0.3, reducedMotion: prefersReducedMotion })}
          className="overflow-hidden"
        >
          <div ref={avatarPickerRef} className="space-y-4">
            {replyTarget ? (
              <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.72] px-4 py-3 text-sm text-foreground/48 dark:bg-card/[0.82]">
                <Sparkles className="h-4 w-4" />
                正在回复 {replyTarget.name}
              </div>
            ) : null}

            {/* Auth status section */}
            {authLoading ? (
              <div className="rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.7] px-4 py-3 text-sm text-foreground/48 dark:bg-card/[0.78]">
                正在检查登录状态...
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
                      <StatusPill text={authSession.is_admin ? "管理员模式" : "已登录"} tone="author" />
                    </div>
                    <p className="mt-1 text-xs text-foreground/45">
                      {authSession.is_admin
                        ? `将使用您的昵称"${authSession.display_name}"作为名字，并使用 Hero 翻转视觉图作为头像提交评论。`
                        : `将使用 ${authSession.display_name} 的昵称、邮箱和头像提交评论。`}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={onLogout}
                  className="inline-flex items-center gap-2 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.7] px-3.5 py-2 text-xs font-medium text-foreground/60 transition hover:border-[rgb(var(--shiro-accent-rgb)/0.22)] hover:text-[rgb(var(--shiro-accent-rgb)/0.84)] dark:bg-card/[0.82]"
                >
                  <X className="h-3.5 w-3.5" />
                  退出登录
                </button>
              </div>
            ) : requiresAuthentication ? (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.72] px-4 py-3 dark:bg-card/[0.82]">
                <div className="space-y-1">
                  <p className="text-sm font-medium text-foreground">登录后才能发布内容</p>
                  <p className="text-xs text-foreground/45">
                    登录后会固定使用你的站点身份发表评论或留言，手动输入昵称、邮箱和访客头像的入口已关闭。
                  </p>
                  {loginMethodLabels.length ? (
                    <div className="flex flex-wrap gap-2 pt-1">
                      {loginMethodLabels.map((label) => (
                        <span
                          key={label}
                          className="inline-flex items-center rounded-full border border-[rgb(var(--shiro-border-rgb)/0.14)] bg-background/[0.8] px-2.5 py-1 text-[0.7rem] text-foreground/58 dark:bg-card/[0.88]"
                        >
                          {label}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="pt-1 text-xs text-amber-700 dark:text-amber-300">
                      当前还没有配置可用的评论登录方式。
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => onOpenLogin({ allowEmailLogin: commentEmailLoginEnabled })}
                  disabled={!hasLoginMethod}
                  className="inline-flex items-center gap-2 rounded-full border border-[rgb(var(--shiro-accent-rgb)/0.24)] bg-[rgb(var(--shiro-accent-rgb)/0.1)] px-4 py-2.5 text-sm font-semibold text-[rgb(var(--shiro-accent-rgb)/0.88)] transition hover:bg-[rgb(var(--shiro-accent-rgb)/0.14)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <LockKeyhole className="h-4 w-4" />
                  登录评论
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
                      <span className="text-xs font-medium uppercase tracking-[0.22em] text-foreground/40">昵称</span>
                      <input
                        value={draft.name}
                        onChange={(event) => onFieldChange("name", event.target.value)}
                        placeholder="输入要显示的名字"
                        className={communityInputClass}
                      />
                    </label>
                    <label className="col-span-full space-y-2 md:col-span-1">
                      <span className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.22em] text-foreground/40">
                        邮箱
                        <LockKeyhole className="h-3.5 w-3.5" />
                      </span>
                      <input
                        type="email"
                        value={draft.email}
                        onChange={(event) => onFieldChange("email", event.target.value)}
                        placeholder="仅用于绑定昵称，不会公开显示"
                        className={communityInputClass}
                      />
                    </label>
                  </div>
                ) : null}
              </div>
            ) : null}

            {/* Website field (guestbook only) */}
            {isGuestbook ? (
              <label className="block space-y-2">
                <span className="text-xs font-medium uppercase tracking-[0.22em] text-foreground/40">网站</span>
                <input
                  value={draft.website}
                  onChange={(event) => onFieldChange("website", event.target.value)}
                  placeholder="https://example.com"
                  className={communityInputClass}
                />
              </label>
            ) : null}

            {/* Reply target indicator */}
            {replyTarget ? (
              <div className="shiro-accent-panel flex flex-wrap items-center gap-2 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] px-4 py-3 text-sm text-foreground/62">
                <CornerDownRight className="h-4 w-4" />
                正在回复 <span className="font-semibold text-foreground">{replyTarget.name}</span>
                <button
                  type="button"
                  onClick={onClearReply}
                  className={`${communityActionClass} px-2 text-xs`}
                >
                  <X className="h-3.5 w-3.5" />
                  取消回复
                </button>
              </div>
            ) : null}

            {/* Editor area */}
            <div className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-3">
                {/* Write / preview tabs */}
                <div className="inline-flex rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.74] p-1 dark:bg-card/[0.8]">
                  <button
                    type="button"
                    onClick={() => onSetEditorMode("write")}
                    className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs transition ${
                      editorMode === "write"
                        ? "bg-[rgb(var(--shiro-accent-rgb)/0.12)] text-[rgb(var(--shiro-accent-rgb)/0.88)]"
                        : "text-foreground/52 hover:text-foreground/76"
                    }`}
                  >
                    <PencilLine className="h-3.5 w-3.5" />
                    编辑
                  </button>
                  <button
                    type="button"
                    onClick={() => onSetEditorMode("preview")}
                    className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs transition ${
                      editorMode === "preview"
                        ? "bg-[rgb(var(--shiro-accent-rgb)/0.12)] text-[rgb(var(--shiro-accent-rgb)/0.88)]"
                        : "text-foreground/52 hover:text-foreground/76"
                    }`}
                  >
                    <Eye className="h-3.5 w-3.5" />
                    预览
                  </button>
                </div>

                {/* Emoji + image buttons */}
                <div className="flex flex-wrap items-center gap-2">
                  {emojiSelectionEnabled ? (
                    <div ref={emojiPickerRef} className="relative">
                      <button
                        type="button"
                        onClick={onToggleEmojiPicker}
                        className={communityChipClass}
                        aria-expanded={emojiPickerOpen}
                        aria-label="打开表情选择器"
                      >
                        <Smile className="h-3.5 w-3.5" />
                        表情
                      </button>
                      {emojiPickerOpen ? (
                        <div className={communityEmojiPopupClass}>
                          <label className="block space-y-2">
                            <span className="text-[0.65rem] font-medium uppercase tracking-[0.22em] text-foreground/40">
                              搜索表情
                            </span>
                            <input
                              ref={emojiSearchRef}
                              value={emojiQuery}
                              onChange={(event) => onEmojiQueryChange(event.target.value)}
                              placeholder="输入表情名、关键词或表情本身"
                              className={communityEmojiSearchClass}
                            />
                          </label>

                          <div className="mt-3 max-h-56 space-y-3 overflow-auto pr-1">
                            {filteredEmojiGroups.length ? filteredEmojiGroups.map((group) => (
                              <div key={group.title} className="space-y-2">
                                <p className="text-[0.65rem] font-medium uppercase tracking-[0.22em] text-foreground/35">
                                  {group.title}
                                </p>
                                <div className="grid grid-cols-6 gap-2">
                                  {group.items.map((choice) => (
                                    <button
                                      key={choice.emoji}
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
                            )) : (
                              <div className="rounded-2xl border border-dashed border-[rgb(var(--shiro-border-rgb)/0.18)] px-3 py-6 text-center text-sm text-foreground/40">
                                没有找到匹配的表情。
                              </div>
                            )}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  {imageUploadsEnabled ? (
                    <>
                      <button
                        type="button"
                        onClick={() => imageInputRef.current?.click()}
                        disabled={imageUploading}
                        className={`${communityChipClass} disabled:cursor-not-allowed disabled:opacity-60`}
                      >
                        {imageUploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ImagePlus className="h-3.5 w-4" />}
                        图片
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
                    <MarkdownRenderer content={deferredBody} className="aerisun-comment-preview" />
                  ) : (
                    <div className="flex min-h-[128px] items-center justify-center text-sm text-foreground/42">
                      这里会显示 Markdown 预览。
                    </div>
                  )}
                </div>
              ) : (
                <textarea
                  ref={textareaRef}
                  value={draft.body}
                  onChange={(event) => onFieldChange("body", event.target.value)}
                  placeholder={isGuestbook ? guestbookBodyPlaceholder : "写下你的看法、补充或追问"}
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
                  ? "提交后会先进入审核队列；当前内容会固定使用你的站点昵称和头像。"
                  : "当前站点要求先登录后再发表评论或留言。"}
              </p>
              <button
                type="button"
                onClick={onSubmit}
                disabled={submitting}
                className="inline-flex items-center gap-2 rounded-full border border-[rgb(var(--shiro-accent-rgb)/0.24)] bg-[rgb(var(--shiro-accent-rgb)/0.1)] px-5 py-2.5 text-sm font-semibold text-[rgb(var(--shiro-accent-rgb)/0.88)] transition hover:bg-[rgb(var(--shiro-accent-rgb)/0.14)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                {submitting
                  ? (isGuestbook ? guestbookSubmittingLabel : "提交中...")
                  : isGuestbook
                    ? guestbookSubmitLabel
                    : replyTarget
                      ? "提交回复"
                      : "提交评论"}
              </button>
            </div>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
};

export default WalineCommentForm;
