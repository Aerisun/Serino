import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Heart, MessageCircle, Reply, ChevronDown } from "lucide-react";
import { transition } from "@/config";
import { apiClient } from "@/lib/api";
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
  liked?: boolean;
  replies?: RemoteCommentRecord[];
  children?: RemoteCommentRecord[];
};

type ReactionResponse = {
  total?: number;
};

const mockComments: Comment[] = [
  {
    id: "1",
    author: "林小北",
    avatar: "北",
    date: "2 小时前",
    content: "写得真好，尤其是关于节奏感的那段，让我重新思考了自己的排版方式。",
    likes: 12,
    replies: [
      {
        id: "11",
        author: "博主",
        avatar: "我",
        date: "1 小时前",
        content: "谢谢！排版确实是一个容易被忽略但影响很大的部分。",
        likes: 3,
      },
    ],
  },
  {
    id: "2",
    author: "设计小白",
    avatar: "白",
    date: "5 小时前",
    content: "作为刚入行的设计师，这篇文章给了我很多启发。收藏了！",
    likes: 8,
  },
  {
    id: "3",
    author: "代码诗人",
    avatar: "诗",
    date: "昨天",
    content: "从技术实现的角度来说，这些思路也完全适用于组件化开发。好的组件和好的排版一样，都需要节奏。",
    likes: 15,
    replies: [
      {
        id: "31",
        author: "林小北",
        avatar: "北",
        date: "昨天",
        content: "同意！设计和开发本质上是相通的。",
        likes: 4,
      },
      {
        id: "32",
        author: "博主",
        avatar: "我",
        date: "12 小时前",
        content: "没错，我一直觉得写代码和做设计的思维方式很像，都是在约束中寻找最优解。",
        likes: 6,
      },
    ],
  },
];

interface CommentItemProps {
  comment: Comment;
  isReply?: boolean;
  onReply: (comment: Comment) => void;
}

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

const VIEWER_TOKEN_STORAGE_KEY = "aerisun:engagement:viewer-token";

const getContentReactionStorageKey = (contentType: string, slug: string) =>
  `aerisun:engagement:reaction:${contentType}:${slug}:like`;

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
  const avatar = String(record.avatar ?? record.avatar_url ?? (author.slice(0, 1) || "访客"));
  const children = record.replies ?? record.children ?? [];

  return {
    id: String(record.id ?? `${author}-${record.created_at ?? record.date ?? Date.now()}`),
    author,
    avatar,
    date: formatDisplayDate(record.date ?? record.created_at),
    content: String(record.body ?? record.content ?? record.message ?? ""),
    likes: Number(record.likes ?? 0),
    liked: Boolean(record.liked),
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

const CommentItem = ({ comment, isReply = false, onReply }: CommentItemProps) => {
  const [liked, setLiked] = useState(comment.liked || false);
  const [likes, setLikes] = useState(comment.likes);
  const [showReplies, setShowReplies] = useState(true);
  const isAuthor = comment.author === "博主";

  const handleLike = () => {
    setLiked(!liked);
    setLikes((l) => (liked ? l - 1 : l + 1));
  };

  return (
    <div className={isReply ? "" : ""}>
      <div className="flex gap-3">
        {/* Avatar */}
        <div
          className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center overflow-hidden text-xs font-body font-medium ${
            isAuthor
              ? "bg-foreground/15 text-foreground/70"
              : "bg-foreground/5 text-foreground/35"
          }`}
        >
          {isImageAvatar(comment.avatar) ? (
            <img src={comment.avatar} alt={comment.author} className="h-full w-full object-cover" loading="lazy" />
          ) : (
            comment.avatar
          )}
        </div>

        <div className="flex-1 min-w-0">
          {/* Author + date */}
          <div className="flex items-center gap-2">
            <span className={`text-sm font-body font-medium ${isAuthor ? "text-foreground/70" : "text-foreground/55"}`}>
              {comment.author}
            </span>
            {isAuthor && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-foreground/8 text-foreground/30 font-body">
                作者
              </span>
            )}
            <span className="text-[11px] font-body text-foreground/20">{comment.date}</span>
          </div>

          {/* Content */}
          <p className="mt-1.5 text-sm font-body text-foreground/45 leading-relaxed">
            {comment.content}
          </p>

          {/* Actions */}
          <div className="mt-2 flex items-center gap-4">
            <button
              onClick={handleLike}
              className={`flex items-center gap-1 text-[11px] font-body transition-colors active:scale-95 ${
                liked ? "text-red-400/70" : "text-foreground/20 hover:text-foreground/40"
              }`}
            >
              <Heart className={`h-3.5 w-3.5 ${liked ? "fill-current" : ""}`} />
              {likes > 0 && likes}
            </button>
            <button
              onClick={() => onReply(comment)}
              className="flex items-center gap-1 text-[11px] font-body text-foreground/20 hover:text-foreground/40 transition-colors active:scale-95"
            >
              <Reply className="h-3.5 w-3.5" />
              回复
            </button>
          </div>

          {/* Replies */}
          {comment.replies && comment.replies.length > 0 && (
            <div className="mt-3">
              {!isReply && comment.replies.length > 1 && (
                <button
                  onClick={() => setShowReplies(!showReplies)}
                  className="flex items-center gap-1 text-[11px] font-body text-foreground/25 hover:text-foreground/40 transition-colors mb-2"
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
                    className="overflow-hidden border-l border-foreground/5 pl-4 flex flex-col gap-4"
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

interface CommentSectionProps {
  commentCount?: number;
  likeCount?: number;
  contentType?: "posts" | "diary";
  contentSlug?: string;
}

const AVATAR_OPTIONS = ["🐱", "🐶", "🦊", "🐼", "🐨", "🦁", "🐸", "🐧", "🦋", "🌸", "🍀", "⭐"];

const CommentSection = ({
  commentCount,
  likeCount = 42,
  contentType,
  contentSlug,
}: CommentSectionProps) => {
  const [comments, setComments] = useState<Comment[]>(mockComments);
  const [newComment, setNewComment] = useState("");
  const [nickname, setNickname] = useState("");
  const [selectedAvatar, setSelectedAvatar] = useState("🐱");
  const [showAvatarPicker, setShowAvatarPicker] = useState(false);
  const [replyTo, setReplyTo] = useState<string | null>(null);
  const [replyTargetId, setReplyTargetId] = useState<string | null>(null);
  const [showComments, setShowComments] = useState(false);
  const [liked, setLiked] = useState(false);
  const [likes, setLikes] = useState(likeCount);
  const [hasRemoteComments, setHasRemoteComments] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
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
    setComments(mockComments);
    setHasRemoteComments(false);
    setLikes(likeCount);
  }, [contentContext?.contentType, contentContext?.slug, likeCount]);

  useEffect(() => {
    if (!contentContext?.slug) {
      return;
    }

    let cancelled = false;

    const loadComments = async () => {
      try {
        const payload = await apiClient.get<unknown>(
          `/api/v1/public/comments/${contentContext.contentType}/${encodeURIComponent(contentContext.slug)}`,
        );
        const remoteComments = extractCommentItems(payload).map(normalizeCommentNode);

        if (!cancelled) {
          setComments(remoteComments);
          setHasRemoteComments(true);
        }
      } catch {
        if (!cancelled) {
          setHasRemoteComments(false);
        }
      }
    };

    void loadComments();

    return () => {
      cancelled = true;
    };
  }, [contentContext?.contentType, contentContext?.slug]);

  const handleReply = (comment: Comment) => {
    setReplyTo(comment.author);
    setReplyTargetId(comment.id);
    setNewComment(`@${comment.author} `);
    if (!showComments) setShowComments(true);
  };

  const handleSubmit = async () => {
    if (!newComment.trim() || !nickname.trim() || isSubmitting) return;

    const optimisticComment: Comment = {
      id: `local-${Date.now()}`,
      author: nickname.trim(),
      avatar: selectedAvatar,
      date: "刚刚",
      content: newComment.trim(),
      likes: 0,
      replies: [],
    };

    setComments((current) => insertReply(current, replyTargetId, optimisticComment));
    setNewComment("");
    setReplyTo(null);
    setReplyTargetId(null);
    setIsSubmitting(true);

    if (contentContext?.slug) {
      try {
        await apiClient.post(
          `/api/v1/public/comments/${contentContext.contentType}/${encodeURIComponent(contentContext.slug)}`,
          {
            author_name: optimisticComment.author,
            body: optimisticComment.content,
            parent_id: replyTargetId,
          },
          { credentials: "include" },
        );
      } catch {
        // Keep the optimistic local entry as fallback if the backend is unavailable.
      }
    }

    setIsSubmitting(false);
  };

  const handleLikeToggle = async () => {
    if (liked) {
      return;
    }

    const nextLikes = likes + 1;
    setLiked(true);
    setLikes(nextLikes);

    if (!contentContext?.slug) {
      return;
    }

    const reactionStorageKey = getContentReactionStorageKey(contentContext.contentType, contentContext.slug);

    try {
      const payload = await apiClient.post<ReactionResponse>(
        "/api/v1/public/reactions",
        {
          content_type: contentContext.contentType,
          content_slug: contentContext.slug,
          reaction_type: "like",
          client_token: getViewerToken(),
        },
        { credentials: "include" },
      );
      setLikes(typeof payload.total === "number" ? payload.total : nextLikes);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(reactionStorageKey, "true");
      }
    } catch {
      // Keep the local optimistic state if the backend is unavailable.
    }
  };

  const total = hasRemoteComments
    ? countCommentTree(comments)
    : commentCount ?? countCommentTree(comments);

  return (
    <motion.div
      className="mt-12"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={transition({ duration: 0.5, delay: 0.2, reducedMotion: prefersReducedMotion })}
    >
      {/* Action buttons */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={handleLikeToggle}
          className={`liquid-glass rounded-2xl px-5 py-3 flex items-center gap-2 transition-all active:scale-[0.97] ${
            liked ? "text-red-400/80" : "text-foreground/40 hover:text-foreground/60"
          }`}
        >
          <Heart className={`h-4 w-4 ${liked ? "fill-current" : ""}`} />
          <span className="text-sm font-body font-medium tabular-nums">{likes}</span>
        </button>

        <button
          onClick={() => setShowComments(!showComments)}
          className={`liquid-glass rounded-2xl px-5 py-3 flex items-center gap-2 transition-all active:scale-[0.97] ${
            showComments ? "text-foreground/70" : "text-foreground/40 hover:text-foreground/60"
          }`}
        >
          <MessageCircle className={`h-4 w-4 ${showComments ? "fill-foreground/10" : ""}`} />
          <span className="text-sm font-body font-medium tabular-nums">{total}</span>
        </button>
      </div>

      {/* Comments area — toggled */}
      <AnimatePresence>
        {showComments && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={transition({ duration: 0.35, reducedMotion: prefersReducedMotion })}
            className="overflow-hidden"
          >
            {/* Input */}
            <div className="liquid-glass rounded-2xl p-4 mb-8">
              <div className="flex items-center gap-3 mb-3 pb-3 border-b border-foreground/5">
                <div className="relative">
                  <button
                    onClick={() => setShowAvatarPicker(!showAvatarPicker)}
                    className="w-9 h-9 rounded-full bg-foreground/5 flex items-center justify-center text-lg hover:bg-foreground/10 transition-colors active:scale-95 overflow-hidden"
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
                        className="absolute top-full left-0 mt-2 z-10 liquid-glass rounded-xl p-2 grid grid-cols-6 gap-1 min-w-[180px]"
                      >
                        {AVATAR_OPTIONS.map((emoji) => (
                          <button
                            key={emoji}
                            onClick={() => {
                              setSelectedAvatar(emoji);
                              setShowAvatarPicker(false);
                            }}
                            className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm hover:bg-foreground/10 transition-colors active:scale-90 ${
                              selectedAvatar === emoji ? "bg-foreground/15 ring-1 ring-foreground/20" : ""
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
                  onChange={(e) => setNickname(e.target.value.slice(0, 20))}
                  placeholder="你的昵称"
                  maxLength={20}
                  className="flex-1 bg-transparent text-sm font-body text-foreground/60 placeholder:text-foreground/15 outline-none"
                />
                <span className="text-[10px] font-body text-foreground/15 shrink-0">
                  {nickname.length}/20
                </span>
              </div>

              {replyTo && (
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[11px] font-body text-foreground/25">回复 {replyTo}</span>
                  <button
                    onClick={() => {
                      setReplyTo(null);
                      setReplyTargetId(null);
                      setNewComment("");
                    }}
                    className="text-[11px] font-body text-foreground/20 hover:text-foreground/40 transition-colors"
                  >
                    取消
                  </button>
                </div>
              )}
              <textarea
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                placeholder="写下你的想法..."
                rows={3}
                maxLength={500}
                className="w-full bg-transparent text-sm font-body text-foreground/60 placeholder:text-foreground/15 outline-none resize-none leading-relaxed"
              />
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-foreground/5">
                <span className="text-[11px] font-body text-foreground/15">
                  {newComment.length}/500
                </span>
                <button
                  onClick={handleSubmit}
                  disabled={!newComment.trim() || !nickname.trim() || isSubmitting}
                  className="px-4 py-1.5 rounded-xl text-xs font-body font-medium transition-all active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed bg-foreground/10 text-foreground/60 hover:bg-foreground/15 hover:text-foreground/80"
                >
                  发表评论
                </button>
              </div>
            </div>

            {/* Comments list */}
            <div className="flex flex-col gap-6">
              {comments.map((comment, i) => (
                <motion.div
                  key={comment.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={transition({
                    duration: 0.35,
                    delay: prefersReducedMotion ? 0 : 0.05 + i * 0.05,
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
