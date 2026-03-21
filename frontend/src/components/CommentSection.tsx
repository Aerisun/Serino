import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Heart, MessageCircle, Reply, ChevronDown } from "lucide-react";
import { transition } from "@/config";
import {
  createPublicComment,
  createPublicReaction,
  fetchPublicComments,
  fetchPublicReaction,
  type PublicComment,
} from "@/lib/api";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import { useLocation, useParams } from "react-router-dom";

interface Comment {
  id: string;
  author: string;
  avatar: string;
  date: string;
  content: string;
  likes: number;
  liked?: boolean;
  isAuthor?: boolean;
  replies?: Comment[];
}

type RemoteCommentRecord = {
  id?: string | number;
  author_name?: string;
  author?: string;
  name?: string;
  nickname?: string;
  avatar?: string;
  avatar_url?: string;
  date?: string;
  created_at?: string;
  body?: string;
  content?: string;
  message?: string;
  likes?: number;
  like_count?: number;
  liked?: boolean;
  is_author?: boolean;
  replies?: RemoteCommentRecord[];
  children?: RemoteCommentRecord[];
};

interface CommentItemProps {
  comment: Comment;
  isReply?: boolean;
  onReply: (comment: Comment) => void;
}

interface CommentSectionProps {
  commentCount?: number;
  likeCount?: number;
  contentType?: "posts" | "diary";
  contentSlug?: string;
}

const AVATAR_OPTIONS = ["🐱", "🐶", "🦊", "🐼", "🐨", "🦁", "🐸", "🐧", "🦋", "🌸", "🍀", "⭐"];

const VIEWER_TOKEN_STORAGE_KEY = "aerisun:engagement:viewer-token";

const getContentReactionStorageKey = (contentType: string, slug: string) =>
  `aerisun:engagement:reaction:${contentType}:${slug}:like`;

const isImageAvatar = (avatar: string) => /^https?:\/\//.test(avatar);

const formatDisplayDate = (value: string | null | undefined) => {
  if (!value) return "刚刚";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;

  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  })
    .format(parsed)
    .replaceAll("/", "-");
};

const extractCommentItems = (payload: unknown): RemoteCommentRecord[] => {
  if (Array.isArray(payload)) return payload as RemoteCommentRecord[];

  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    for (const candidate of [record.items, record.comments, record.entries, record.data, record.results]) {
      if (Array.isArray(candidate)) return candidate as RemoteCommentRecord[];
    }
  }

  return [];
};

const countCommentTree = (items: Comment[]) =>
  items.reduce((total, item) => total + 1 + countCommentTree(item.replies ?? []), 0);

const getViewerToken = () => {
  if (typeof window === "undefined") {
    return undefined;
  }

  const stored = window.localStorage.getItem(VIEWER_TOKEN_STORAGE_KEY);
  if (stored) {
    return stored;
  }

  const token =
    typeof window.crypto?.randomUUID === "function"
      ? window.crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  window.localStorage.setItem(VIEWER_TOKEN_STORAGE_KEY, token);
  return token;
};

const normalizeCommentNode = (record: RemoteCommentRecord): Comment => {
  const author = String(record.author_name ?? record.author ?? record.name ?? record.nickname ?? "访客");
  const children = record.replies ?? record.children ?? [];

  return {
    id: String(record.id ?? `${author}-${record.created_at ?? record.date ?? Date.now()}`),
    author,
    avatar: String(record.avatar ?? record.avatar_url ?? (author.slice(0, 1) || "访")),
    date: formatDisplayDate(record.date ?? record.created_at),
    content: String(record.body ?? record.content ?? record.message ?? ""),
    likes: Number(record.like_count ?? record.likes ?? 0),
    liked: Boolean(record.liked),
    isAuthor: Boolean(record.is_author) || author === "博主",
    replies: children.map(normalizeCommentNode),
  };
};

const insertReply = (items: Comment[], parentId: string | null, reply: Comment): Comment[] => {
  if (!parentId) {
    return [reply, ...items];
  }

  return items.map((item) => {
    if (item.id === parentId) {
      return { ...item, replies: [...(item.replies ?? []), reply] };
    }

    if (item.replies?.length) {
      return { ...item, replies: insertReply(item.replies, parentId, reply) };
    }

    return item;
  });
};

const replaceComment = (items: Comment[], targetId: string, nextComment: Comment): Comment[] =>
  items.map((item) => {
    if (item.id === targetId) {
      return nextComment;
    }

    if (item.replies?.length) {
      return { ...item, replies: replaceComment(item.replies, targetId, nextComment) };
    }

    return item;
  });

const CommentItem = ({ comment, isReply = false, onReply }: CommentItemProps) => {
  const [liked, setLiked] = useState(comment.liked || false);
  const [likes, setLikes] = useState(comment.likes);
  const [showReplies, setShowReplies] = useState(true);
  const isAuthor = Boolean(comment.isAuthor) || comment.author === "博主";

  const handleLike = () => {
    setLiked(!liked);
    setLikes((value) => (liked ? value - 1 : value + 1));
  };

  return (
    <div>
      <div className="flex gap-3">
        <div
          className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center overflow-hidden text-xs font-body font-medium ${
            isAuthor ? "bg-foreground/15 text-foreground/70" : "bg-foreground/5 text-foreground/35"
          }`}
        >
          {isImageAvatar(comment.avatar) ? (
            <img src={comment.avatar} alt={comment.author} className="h-full w-full object-cover" loading="lazy" />
          ) : (
            comment.avatar
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-sm font-body font-medium ${isAuthor ? "text-foreground/70" : "text-foreground/55"}`}>
              {comment.author}
            </span>
            {isAuthor && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-[rgb(var(--shiro-panel-rgb)/0.38)] text-[rgb(var(--shiro-accent-rgb)/0.75)] font-body">
                作者
              </span>
            )}
            <span className="text-[11px] font-body text-foreground/20">{comment.date}</span>
          </div>

          <p className="mt-1.5 text-sm font-body text-foreground/45 leading-relaxed">{comment.content}</p>

          <div className="mt-2 flex items-center gap-4">
            <button
              type="button"
              onClick={handleLike}
              className={`flex items-center gap-1 text-[11px] font-body transition-colors active:scale-95 ${
                liked
                  ? "text-[rgb(var(--shiro-accent-rgb)/0.82)]"
                  : "text-foreground/20 hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]"
              }`}
            >
              <Heart className={`h-3.5 w-3.5 ${liked ? "fill-current" : ""}`} />
              {likes > 0 && likes}
            </button>
            <button
              type="button"
              onClick={() => onReply(comment)}
              className="flex items-center gap-1 text-[11px] font-body text-foreground/20 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.72)] active:scale-95"
            >
              <Reply className="h-3.5 w-3.5" />
              回复
            </button>
          </div>

          {comment.replies && comment.replies.length > 0 && (
            <div className="mt-3">
              {!isReply && comment.replies.length > 1 && (
                <button
                  type="button"
                  onClick={() => setShowReplies(!showReplies)}
                  className="mb-2 flex items-center gap-1 text-[11px] font-body text-foreground/25 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]"
                >
                  <ChevronDown className={`h-3 w-3 transition-transform ${showReplies ? "rotate-180" : ""}`} />
                  {showReplies ? "收起回复" : `展开 ${comment.replies.length} 条回复`}
                </button>
              )}
              <AnimatePresence>
                {showReplies && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.25 }}
                    className="flex flex-col gap-4 overflow-hidden border-l border-[rgb(var(--shiro-divider-rgb)/0.34)] pl-4"
                    >
                    {comment.replies.map((reply) => (
                      <CommentItem key={reply.id} comment={reply} isReply onReply={onReply} />
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const CommentSection = ({ commentCount, likeCount, contentType, contentSlug }: CommentSectionProps) => {
  const [comments, setComments] = useState<Comment[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [newComment, setNewComment] = useState("");
  const [nickname, setNickname] = useState("");
  const [selectedAvatar, setSelectedAvatar] = useState(AVATAR_OPTIONS[0]);
  const [showAvatarPicker, setShowAvatarPicker] = useState(false);
  const [replyTo, setReplyTo] = useState<string | null>(null);
  const [replyTargetId, setReplyTargetId] = useState<string | null>(null);
  const [showComments, setShowComments] = useState(false);
  const [liked, setLiked] = useState(false);
  const [likeTotal, setLikeTotal] = useState<number | null>(typeof likeCount === "number" ? likeCount : null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isReacting, setIsReacting] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const prefersReducedMotion = useReducedMotionPreference();
  const location = useLocation();
  const { id } = useParams();

  const contentContext = useMemo(() => {
    if (contentType && contentSlug) {
      return { contentType, slug: contentSlug };
    }

    if (location.pathname.startsWith("/posts/")) {
      return { contentType: "posts" as const, slug: id ?? "" };
    }

    if (location.pathname.startsWith("/diary/")) {
      return { contentType: "diary" as const, slug: id ?? "" };
    }

    return null;
  }, [contentSlug, contentType, id, location.pathname]);

  useEffect(() => {
    if (!contentContext?.slug || typeof window === "undefined") {
      setLiked(false);
      return;
    }

    const storageKey = getContentReactionStorageKey(contentContext.contentType, contentContext.slug);
    setLiked(window.localStorage.getItem(storageKey) === "true");
  }, [contentContext?.contentType, contentContext?.slug]);

  useEffect(() => {
    setComments([]);
    setStatus(contentContext?.slug ? "loading" : "empty");
    setErrorMessage("");
    setLikeTotal(typeof likeCount === "number" ? likeCount : null);
    setNewComment("");
    setReplyTo(null);
    setReplyTargetId(null);
    setShowAvatarPicker(false);
  }, [contentContext?.contentType, contentContext?.slug, likeCount]);

  useEffect(() => {
    if (!contentContext?.slug) {
      return;
    }

    const controller = new AbortController();

    const loadComments = async () => {
      try {
        const payload = await fetchPublicComments(contentContext.contentType, contentContext.slug, {
          signal: controller.signal,
        });
        if (controller.signal.aborted) {
          return;
        }

        const nextComments = extractCommentItems(payload).map(normalizeCommentNode);
        setComments(nextComments);
        setStatus(nextComments.length > 0 ? "ready" : "empty");
      } catch (error) {
        if (!controller.signal.aborted) {
          setComments([]);
          setStatus("error");
          setErrorMessage(error instanceof Error ? error.message : "评论加载失败");
        }
      }
    };

    const loadReactionTotal = async () => {
      try {
        const payload = await fetchPublicReaction(contentContext.contentType, contentContext.slug, "like", {
          signal: controller.signal,
        });
        if (!controller.signal.aborted && typeof payload.total === "number") {
          setLikeTotal(payload.total);
        }
      } catch {
        // Keep the externally supplied count if the read endpoint is unavailable.
      }
    };

    void loadComments();
    void loadReactionTotal();

    return () => {
      controller.abort();
    };
  }, [contentContext?.contentType, contentContext?.slug, reloadKey]);

  const handleReply = (comment: Comment) => {
    setReplyTo(comment.author);
    setReplyTargetId(comment.id);
    setNewComment((current) => (current.startsWith(`@${comment.author} `) ? current : `@${comment.author} `));
    setShowComments(true);
  };

  const handleSubmit = async () => {
    if (!contentContext?.slug || !newComment.trim() || !nickname.trim() || isSubmitting) {
      return;
    }

    const draftComment = newComment;
    const draftReplyTo = replyTo;
    const draftReplyTargetId = replyTargetId;
    const previousComments = comments;
    const optimisticComment: Comment = {
      id: `local-${Date.now()}`,
      author: nickname.trim(),
      avatar: selectedAvatar,
      date: "刚刚",
      content: newComment.trim(),
      likes: 0,
      replies: [],
    };

    setErrorMessage("");
    setIsSubmitting(true);
    setComments((current) => insertReply(current, replyTargetId, optimisticComment));
    setStatus("ready");
    setNewComment("");
    setReplyTo(null);
    setReplyTargetId(null);
    setShowAvatarPicker(false);

    try {
      const response = await createPublicComment(
        contentContext.contentType,
        contentContext.slug,
        {
          author_name: optimisticComment.author,
          body: optimisticComment.content,
          parent_id: draftReplyTargetId,
        },
        { credentials: "include" },
      );

      const savedComment = normalizeCommentNode(response.item as PublicComment);
      setComments((current) =>
        replaceComment(current, optimisticComment.id, {
          ...savedComment,
          avatar: optimisticComment.avatar,
        }),
      );
    } catch (error) {
      setComments(previousComments);
      setStatus(previousComments.length > 0 ? "ready" : "empty");
      setErrorMessage(error instanceof Error ? error.message : "评论提交失败");
      setNewComment(draftComment);
      setReplyTo(draftReplyTo);
      setReplyTargetId(draftReplyTargetId);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLikeToggle = async () => {
    if (!contentContext?.slug || liked || isReacting) {
      return;
    }

    const previousTotal = likeTotal;
    setIsReacting(true);
    setErrorMessage("");

    try {
      const payload = await createPublicReaction(
        {
          content_type: contentContext.contentType,
          content_slug: contentContext.slug,
          reaction_type: "like",
          client_token: getViewerToken(),
        },
        { credentials: "include" },
      );
      setLiked(true);
      setLikeTotal(typeof payload.total === "number" ? payload.total : (previousTotal ?? 0) + 1);
      if (typeof window !== "undefined") {
        const storageKey = getContentReactionStorageKey(contentContext.contentType, contentContext.slug);
        window.localStorage.setItem(storageKey, "true");
      }
    } catch (error) {
      setLiked(false);
      setLikeTotal(previousTotal);
      setErrorMessage(error instanceof Error ? error.message : "点赞失败");
    } finally {
      setIsReacting(false);
    }
  };

  const total = status === "ready" ? countCommentTree(comments) : commentCount ?? countCommentTree(comments);

  return (
    <motion.div
      className="mt-12"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={transition({ duration: 0.5, delay: 0.2, reducedMotion: prefersReducedMotion })}
    >
      <div className="mb-6 flex items-center gap-3">
        <button
          type="button"
          onClick={handleLikeToggle}
          disabled={liked || isReacting || !contentContext?.slug}
          className={`liquid-glass rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.18)] px-5 py-3 flex items-center gap-2 transition-all active:scale-[0.97] disabled:opacity-50 ${
            liked
              ? "text-[rgb(var(--shiro-accent-rgb)/0.85)]"
              : "text-foreground/40 hover:border-[rgb(var(--shiro-accent-rgb)/0.28)] hover:text-[rgb(var(--shiro-accent-rgb)/0.78)]"
          }`}
        >
          <Heart className={`h-4 w-4 ${liked ? "fill-current" : ""}`} />
          <span className="text-sm font-body font-medium tabular-nums">
            {typeof likeTotal === "number" ? likeTotal : 0}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setShowComments((value) => !value)}
          className={`liquid-glass rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.18)] px-5 py-3 flex items-center gap-2 transition-all active:scale-[0.97] ${
            showComments
              ? "text-[rgb(var(--shiro-accent-rgb)/0.82)]"
              : "text-foreground/40 hover:border-[rgb(var(--shiro-accent-rgb)/0.28)] hover:text-[rgb(var(--shiro-accent-rgb)/0.78)]"
          }`}
        >
          <MessageCircle className={`h-4 w-4 ${showComments ? "fill-[rgb(var(--shiro-panel-rgb)/0.34)]" : ""}`} />
          <span className="text-sm font-body font-medium tabular-nums">{total}</span>
        </button>
      </div>

      <AnimatePresence>
        {showComments && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={transition({ duration: 0.35, reducedMotion: prefersReducedMotion })}
            className="overflow-hidden"
          >
            <div className="liquid-glass rounded-2xl p-4 mb-8">
              <div className="flex items-center gap-3 mb-3 pb-3 border-b border-[rgb(var(--shiro-divider-rgb)/0.28)]">
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setShowAvatarPicker(!showAvatarPicker)}
                    className="w-9 h-9 rounded-full bg-foreground/5 flex items-center justify-center overflow-hidden text-lg transition-[background-color,box-shadow,transform] hover:bg-[rgb(var(--shiro-panel-rgb)/0.28)] hover:ring-1 hover:ring-[rgb(var(--shiro-accent-rgb)/0.16)] active:scale-95"
                  >
                    {isImageAvatar(selectedAvatar) ? (
                      <img src={selectedAvatar} alt="avatar" className="h-full w-full object-cover" />
                    ) : (
                      selectedAvatar
                    )}
                  </button>
                  <AnimatePresence>
                    {showAvatarPicker && (
                      <motion.div
                        initial={{ opacity: 0, scale: 0.9, y: 4 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.9, y: 4 }}
                        transition={{ duration: 0.2 }}
                        className="absolute top-full left-0 z-10 mt-2 grid min-w-[180px] grid-cols-6 gap-1 rounded-xl liquid-glass p-2"
                      >
                        {AVATAR_OPTIONS.map((emoji) => (
                          <button
                            key={emoji}
                            type="button"
                            onClick={() => {
                              setSelectedAvatar(emoji);
                              setShowAvatarPicker(false);
                            }}
                            className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm transition-[background-color,box-shadow,transform,color] hover:bg-[rgb(var(--shiro-panel-rgb)/0.26)] hover:text-[rgb(var(--shiro-accent-rgb)/0.78)] active:scale-90 ${
                              selectedAvatar === emoji
                                ? "bg-[rgb(var(--shiro-panel-rgb)/0.36)] ring-1 ring-[rgb(var(--shiro-accent-rgb)/0.22)]"
                                : ""
                            }`}
                          >
                            {emoji}
                          </button>
                        ))}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                <input
                  type="text"
                  value={nickname}
                  onChange={(event) => setNickname(event.target.value.slice(0, 20))}
                  placeholder="你的昵称"
                  maxLength={20}
                  className="flex-1 bg-transparent text-sm font-body text-foreground/60 placeholder:text-foreground/15 outline-none transition-colors focus:text-foreground focus:placeholder:text-foreground/18"
                />
                <span className="text-[10px] font-body text-foreground/15 shrink-0">{nickname.length}/20</span>
              </div>

              {replyTo && (
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[11px] font-body text-[rgb(var(--shiro-accent-rgb)/0.68)]">回复 {replyTo}</span>
                  <button
                    type="button"
                    onClick={() => {
                      setReplyTo(null);
                      setReplyTargetId(null);
                      setNewComment("");
                    }}
                    className="text-[11px] font-body text-foreground/20 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]"
                  >
                    取消
                  </button>
                </div>
              )}

              <textarea
                value={newComment}
                onChange={(event) => setNewComment(event.target.value)}
                placeholder="写下你的想法..."
                rows={3}
                maxLength={500}
                className="w-full resize-none bg-transparent text-sm font-body leading-relaxed text-foreground/60 placeholder:text-foreground/15 outline-none transition-colors focus:text-foreground focus:placeholder:text-foreground/18"
              />

              <div className="mt-3 flex items-center justify-between border-t border-[rgb(var(--shiro-divider-rgb)/0.26)] pt-3">
                <span className="text-[11px] font-body text-foreground/15">{newComment.length}/500</span>
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={!newComment.trim() || !nickname.trim() || isSubmitting}
                  className="rounded-xl border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-foreground/10 px-4 py-1.5 text-xs font-body font-medium text-foreground/60 transition-[border-color,background-color,color,transform] hover:border-[rgb(var(--shiro-accent-rgb)/0.3)] hover:bg-[rgb(var(--shiro-panel-rgb)/0.28)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] active:scale-95 disabled:cursor-not-allowed disabled:opacity-30"
                >
                  发表评论
                </button>
              </div>
            </div>

            <div className="flex flex-col gap-6">
              {status === "loading" &&
                Array.from({ length: 3 }, (_, index) => (
                  <div key={`comment-skeleton-${index}`} className="flex gap-3">
                    <div className="h-8 w-8 shrink-0 rounded-full bg-foreground/[0.05]" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <div className="h-3.5 w-20 rounded-full bg-foreground/[0.04]" />
                        <div className="h-3 w-14 rounded-full bg-foreground/[0.03]" />
                      </div>
                      <div className="mt-2 h-3.5 w-[82%] rounded-full bg-foreground/[0.035]" />
                      <div className="mt-1.5 h-3.5 w-[68%] rounded-full bg-foreground/[0.03]" />
                    </div>
                  </div>
                ))}

              {status === "error" && (
                <div className="flex gap-3">
                  <div className="h-8 w-8 shrink-0 rounded-full bg-foreground/[0.05]" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-body font-medium text-foreground/55">评论加载失败</span>
                      <button
                        type="button"
                        onClick={() => setReloadKey((value) => value + 1)}
                        className="text-[11px] font-body text-foreground/25 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]"
                      >
                        重试
                      </button>
                    </div>
                    <p className="mt-1.5 text-sm font-body leading-relaxed text-foreground/35">
                      {errorMessage || "请稍后再试。"}
                    </p>
                  </div>
                </div>
              )}

              {status === "empty" && (
                <div className="flex gap-3">
                  <div className="h-8 w-8 shrink-0 rounded-full bg-foreground/[0.05]" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-body font-medium text-foreground/50">还没有评论</span>
                    </div>
                    <p className="mt-1.5 text-sm font-body leading-relaxed text-foreground/35">
                      留下第一条吧。
                    </p>
                  </div>
                </div>
              )}

              {status === "ready" &&
                comments.map((comment, index) => (
                  <motion.div
                    key={comment.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={transition({
                      duration: 0.35,
                      delay: prefersReducedMotion ? 0 : 0.05 + index * 0.05,
                      reducedMotion: prefersReducedMotion,
                    })}
                  >
                    <CommentItem comment={comment} onReply={handleReply} />
                  </motion.div>
                ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default CommentSection;
