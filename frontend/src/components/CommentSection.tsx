import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Heart, MessageCircle, Reply, ChevronDown } from "lucide-react";

interface Comment {
  id: number;
  author: string;
  avatar: string;
  date: string;
  content: string;
  likes: number;
  liked?: boolean;
  replies?: Comment[];
}

const mockComments: Comment[] = [
  {
    id: 1,
    author: "林小北",
    avatar: "北",
    date: "2 小时前",
    content: "写得真好，尤其是关于节奏感的那段，让我重新思考了自己的排版方式。",
    likes: 12,
    replies: [
      {
        id: 11,
        author: "博主",
        avatar: "我",
        date: "1 小时前",
        content: "谢谢！排版确实是一个容易被忽略但影响很大的部分。",
        likes: 3,
      },
    ],
  },
  {
    id: 2,
    author: "设计小白",
    avatar: "白",
    date: "5 小时前",
    content: "作为刚入行的设计师，这篇文章给了我很多启发。收藏了！",
    likes: 8,
  },
  {
    id: 3,
    author: "代码诗人",
    avatar: "诗",
    date: "昨天",
    content: "从技术实现的角度来说，这些思路也完全适用于组件化开发。好的组件和好的排版一样，都需要节奏。",
    likes: 15,
    replies: [
      {
        id: 31,
        author: "林小北",
        avatar: "北",
        date: "昨天",
        content: "同意！设计和开发本质上是相通的。",
        likes: 4,
      },
      {
        id: 32,
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
  onReply: (author: string) => void;
}

const CommentItem = ({ comment, isReply = false, onReply }: CommentItemProps) => {
  const [liked, setLiked] = useState(comment.liked || false);
  const [likes, setLikes] = useState(comment.likes);
  const [showReplies, setShowReplies] = useState(true);
  const isAuthor = comment.author === "博主";

  const handleLike = () => {
    setLiked(!liked);
    setLikes(l => liked ? l - 1 : l + 1);
  };

  return (
    <div className={isReply ? "" : ""}>
      <div className="flex gap-3">
        {/* Avatar */}
        <div
          className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-body font-medium ${
            isAuthor
              ? "bg-foreground/15 text-foreground/70"
              : "bg-foreground/5 text-foreground/35"
          }`}
        >
          {comment.avatar}
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
              onClick={() => onReply(comment.author)}
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
}

const AVATAR_OPTIONS = ["🐱", "🐶", "🦊", "🐼", "🐨", "🦁", "🐸", "🐧", "🦋", "🌸", "🍀", "⭐"];

const CommentSection = ({ commentCount, likeCount = 42 }: CommentSectionProps) => {
  const [comments] = useState<Comment[]>(mockComments);
  const [newComment, setNewComment] = useState("");
  const [nickname, setNickname] = useState("");
  const [selectedAvatar, setSelectedAvatar] = useState("🐱");
  const [showAvatarPicker, setShowAvatarPicker] = useState(false);
  const [replyTo, setReplyTo] = useState<string | null>(null);
  const [showComments, setShowComments] = useState(false);
  const [liked, setLiked] = useState(false);
  const [likes, setLikes] = useState(likeCount);

  const handleReply = (author: string) => {
    setReplyTo(author);
    setNewComment(`@${author} `);
    if (!showComments) setShowComments(true);
  };

  const handleSubmit = () => {
    if (!newComment.trim() || !nickname.trim()) return;
    setNewComment("");
    setReplyTo(null);
  };

  const handleLikeToggle = () => {
    setLiked(!liked);
    setLikes(l => liked ? l - 1 : l + 1);
  };

  const total = commentCount ?? comments.reduce((acc, c) => acc + 1 + (c.replies?.length || 0), 0);

  return (
    <motion.div
      className="mt-12"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
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
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            {/* Input */}
            <div className="liquid-glass rounded-2xl p-4 mb-8">
              <div className="flex items-center gap-3 mb-3 pb-3 border-b border-foreground/5">
                <div className="relative">
                  <button
                    onClick={() => setShowAvatarPicker(!showAvatarPicker)}
                    className="w-9 h-9 rounded-full bg-foreground/5 flex items-center justify-center text-lg hover:bg-foreground/10 transition-colors active:scale-95"
                  >
                    {selectedAvatar}
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
                            onClick={() => { setSelectedAvatar(emoji); setShowAvatarPicker(false); }}
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
                    onClick={() => { setReplyTo(null); setNewComment(""); }}
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
                  disabled={!newComment.trim() || !nickname.trim()}
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
                  transition={{ duration: 0.35, delay: 0.05 + i * 0.05, ease: [0.16, 1, 0.3, 1] }}
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
