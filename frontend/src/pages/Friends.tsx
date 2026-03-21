import { useState, useCallback, useEffect } from "react";
import { motion } from "motion/react";
import { RefreshCw, ChevronDown } from "lucide-react";
import PageShell from "@/components/PageShell";
import { pageConfig, staggerItem } from "@/config";
import {
  fetchPublicFriendFeed,
  fetchPublicFriends,
  formatFriendFeedDate,
  type PublicFriend,
  type PublicFriendFeedItem,
} from "@/lib/api";

interface Friend {
  name: string;
  desc: string;
  avatar: string;
}

interface CirclePost {
  avatar: string;
  blogName: string;
  title: string;
  date: string;
}

const LOCAL_FRIENDS: Friend[] = [
  { name: "Miku's Blog", desc: "记录生活与技术的小站", avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Miku" },
  { name: "AkaraChen", desc: "位于互联网边缘的小站。", avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Akara" },
  { name: "夏目的博客", desc: "总有人间一两风，填我十万八千梦。", avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Natsume" },
  { name: "保罗的小宇宙", desc: "Still single, still waiting...", avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Paul" },
  { name: "猫羽のブログ", desc: "空中有颗星为你而亮", avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Nekoha" },
  { name: "Erhecy's Blog", desc: "欢迎来到咱的博客！", avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Erhecy" },
  { name: "轻雅阁", desc: "新时代教师的日常", avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Qingya" },
  { name: "柏园猫のBlog", desc: "人与人虽然相距遥远，但又彼此相依", avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=BaiYuan" },
  { name: "Lucifer's Blog", desc: "Keep moving", avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Lucifer" },
];

// All circle posts data (simulating paginated API)
const LOCAL_CIRCLE_POSTS: CirclePost[] = [
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Natsume", blogName: "夏目的博客", title: "网络流算法详解", date: "2026-03-18" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Miku", blogName: "喵二の小博客", title: "\u201C糖\u201D", date: "2026-03-16" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Natsume", blogName: "夏目的博客", title: "一些思考", date: "2026-03-14" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Erhecy", blogName: "Erhecy's Blog", title: "在博客中优雅地添加 Bilibili 追番页面", date: "2026-03-13" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=BaiYuan", blogName: "空山灵雨", title: "一招解决 Origin 运行报错：找不到 mfc140u.dll", date: "2026-03-11" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Akara", blogName: "AkaraChen", title: "如何使用 Cloudflare API 為網站新增數據監測大屏", date: "2026-03-10" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Paul", blogName: "保罗的小宇宙", title: "Hand Motion Retargeting", date: "2026-03-10" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Lucifer", blogName: "Lucifer's Blog", title: "To panic! or Not to panic!", date: "2026-03-10" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Qingya", blogName: "轻雅阁", title: "碎碎念：找实习、生病与一块薯饼的治愈", date: "2026-03-10" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Erhecy", blogName: "Erhecy's Blog", title: "从零开始的随机算法", date: "2026-03-10" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Nekoha", blogName: "猫羽のブログ", title: "AI 时代的重构方式：从 RFC 到五个 Plan", date: "2026-03-10" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=BaiYuan", blogName: "空山灵雨", title: "使用 Python 绘制中国省份管网老化分布地图", date: "2026-03-06" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=BaiYuan", blogName: "空山灵雨", title: "边缘世界新手生存指南：活过第一个殖民地", date: "2026-03-02" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Nekoha", blogName: "猫羽のブログ", title: "键盘上的春节", date: "2026-03-02" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Nekoha", blogName: "猫羽のブログ", title: "AI 时代的效率悖论：当生产力提升反而带来疲惫", date: "2026-03-01" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Paul", blogName: "保罗的小宇宙", title: "TraceDiary 开发复盘：我如何并行协作 4 个 Agent", date: "2026-02-27" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Akara", blogName: "AkaraChen", title: "Astrbot / 夕颜是如何炼成的", date: "2026-02-27" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Paul", blogName: "保罗的小宇宙", title: "我用 Vibe Coding 开发了一个照片标注工具 ImgStamp", date: "2026-02-26" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Paul", blogName: "保罗的小宇宙", title: "格式刷失灵？解决 Word 段落样式异常的问题", date: "2026-02-26" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Akara", blogName: "AkaraChen", title: "Gravatar Mirror", date: "2026-02-25" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=BaiYuan", blogName: "空山灵雨", title: "又重构了，这次用 Next.js 16", date: "2026-02-24" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Lucifer", blogName: "Lucifer's Blog", title: "ArrayBuffer 与 TypedArray 在 MP4 Box 解析中的运用", date: "2026-02-21" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Qingya", blogName: "轻雅阁", title: "RIA Expo#8 子夜港摊位后日谈", date: "2026-02-18" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Nekoha", blogName: "猫羽のブログ", title: "年味渐淡的春节记忆", date: "2026-02-17" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Miku", blogName: "喵二の小博客", title: "新年快乐", date: "2026-02-12" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Natsume", blogName: "夏目的博客", title: "Rust Programming Language -- Notes", date: "2026-02-09" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Erhecy", blogName: "Erhecy's Blog", title: "SSH Directly into Slurm Job", date: "2026-01-15" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Erhecy", blogName: "Erhecy's Blog", title: "从零开始的 Proxy Lab", date: "2026-01-11" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Miku", blogName: "喵二の小博客", title: "飞牛吐槽，反馈无门却被管理团队坑！", date: "2026-01-04" },
  { avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Qingya", blogName: "轻雅阁", title: "前往 2026", date: "2026-01-04" },
];

const config = pageConfig.friends;

const toFriend = (value: PublicFriend): Friend => ({
  name: value.name,
  desc: value.description?.trim() || "记录生活与技术的小站",
  avatar:
    value.avatar?.trim() ||
    `https://api.dicebear.com/9.x/notionists/svg?seed=${encodeURIComponent(value.name)}`,
});

const toCirclePost = (value: PublicFriendFeedItem): CirclePost => ({
  blogName: value.blogName,
  title: value.title,
  date: formatFriendFeedDate(value.publishedAt) || new Date().toISOString().slice(0, 10),
  avatar:
    value.avatar?.trim() ||
    `https://api.dicebear.com/9.x/notionists/svg?seed=${encodeURIComponent(value.blogName)}`,
});

const Friends = () => {
  const [friends, setFriends] = useState<Friend[]>(LOCAL_FRIENDS);
  const [allCirclePosts, setAllCirclePosts] = useState<CirclePost[]>(LOCAL_CIRCLE_POSTS);
  const [visibleCount, setVisibleCount] = useState(config.pageSize);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    const loadRemoteData = async () => {
      try {
        const [friendsPayload, feedPayload] = await Promise.all([
          fetchPublicFriends(undefined, { signal: controller.signal }),
          fetchPublicFriendFeed(undefined, { signal: controller.signal }),
        ]);

        if (controller.signal.aborted) {
          return;
        }

        const nextFriends = friendsPayload.items.map(toFriend).filter((item) => Boolean(item.name));
        const nextCirclePosts = feedPayload.items
          .map(toCirclePost)
          .filter((item) => Boolean(item.blogName && item.title));

        setFriends(nextFriends.length > 0 ? nextFriends : LOCAL_FRIENDS);
        setAllCirclePosts(nextCirclePosts.length > 0 ? nextCirclePosts : LOCAL_CIRCLE_POSTS);
      } catch {
        if (controller.signal.aborted) {
          return;
        }

        setFriends(LOCAL_FRIENDS);
        setAllCirclePosts(LOCAL_CIRCLE_POSTS);
      }
    };

    void loadRemoteData();

    return () => {
      controller.abort();
    };
  }, []);

  useEffect(() => {
    setVisibleCount((current) => Math.min(Math.max(current, config.pageSize), allCirclePosts.length));
  }, [allCirclePosts.length]);

  const loadMore = useCallback(() => {
    if (loading || visibleCount >= allCirclePosts.length) return;
    setLoading(true);
    // Simulate network delay
    setTimeout(() => {
      setVisibleCount((c) => Math.min(c + config.pageSize, allCirclePosts.length));
      setLoading(false);
    }, 600);
  }, [loading, visibleCount, allCirclePosts.length]);

  const hasMore = visibleCount < allCirclePosts.length;
  const visiblePosts = allCirclePosts.slice(0, visibleCount);

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
      headerAside={
        <span className="text-xs tracking-[0.18em] text-foreground/28">
          {config.headerCountLabel(friends.length)}
        </span>
      }
    >

        {/* Friend Grid */}
        <div className="mt-12 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:gap-5">
          {friends.map((friend, i) => (
            <motion.div
              key={friend.name}
              className="group flex flex-col items-center rounded-2xl px-4 py-8 text-center transition-colors hover:bg-foreground/[0.04]"
              {...staggerItem(i, {
                baseDelay: config.motion.delay,
                step: config.motion.stagger,
                duration: config.motion.duration,
              })}
            >
              <div className="h-16 w-16 overflow-hidden rounded-full bg-foreground/[0.04]">
                <img
                  src={friend.avatar}
                  alt={friend.name}
                  className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-110"
                  loading="lazy"
                />
              </div>
              <p className="mt-4 text-sm font-medium text-foreground/80 group-hover:text-foreground transition-colors">
                {friend.name}
              </p>
              <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-foreground/30">
                {friend.desc}
              </p>
            </motion.div>
          ))}
        </div>

        {/* Divider */}
        <div className="mt-16 mb-10 border-t border-foreground/[0.06]" />

        {/* Friend Circle Section */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: config.motion.duration + 0.05, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="flex items-baseline justify-between mb-2">
            <h2 className="text-2xl font-heading italic tracking-tight text-foreground sm:text-3xl">
              {config.circleTitle}
            </h2>
            <div className="text-xs font-body text-foreground/25 flex items-center gap-1.5">
              <RefreshCw className="h-3 w-3" />
              {config.statusLabel}
            </div>
          </div>
          <p className="text-xs font-body text-foreground/20 mb-8">
            {config.circleSubtitle(friends.length, allCirclePosts.length)}
          </p>
        </motion.div>

        {/* Circle Posts */}
        <div className="flex flex-col">
          {visiblePosts.map((post, i) => (
            <motion.div
              key={`${post.blogName}-${post.date}-${i}`}
              className="group flex items-start gap-3.5 py-4 border-t border-foreground/[0.05] transition-colors hover:bg-foreground/[0.02] -mx-3 px-3 rounded-lg"
              {...staggerItem(i, {
                baseDelay: 0,
                step: 0.03,
                duration: 0.35,
              })}
            >
              {/* Avatar */}
              <div className="h-9 w-9 shrink-0 overflow-hidden rounded-full bg-foreground/[0.06] mt-0.5">
                <img
                  src={post.avatar}
                  alt={post.blogName}
                  className="h-full w-full object-cover"
                  loading="lazy"
                />
              </div>

              {/* Content */}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-body text-foreground/25 truncate">
                  {post.blogName}
                </p>
                <p className="text-[15px] font-body font-medium text-foreground/80 group-hover:text-foreground transition-colors leading-snug mt-0.5 line-clamp-2">
                  {post.title}
                </p>
              </div>

              {/* Date */}
              <span className="text-[11px] font-body text-foreground/20 shrink-0 mt-1 tabular-nums">
                📅 {post.date}
              </span>
            </motion.div>
          ))}
        </div>

        {/* Load More */}
        {hasMore && (
          <div className="mt-8 flex justify-center">
            <button
              onClick={loadMore}
              disabled={loading}
              className="flex items-center gap-2 rounded-full px-6 py-2.5 text-sm font-body text-foreground/50 liquid-glass hover:text-foreground/70 transition-colors active:scale-[0.97] disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  {config.loadingLabel}
                </>
              ) : (
                <>
                  <ChevronDown className="h-3.5 w-3.5" />
                  {config.loadMoreLabel}
                </>
              )}
            </button>
          </div>
        )}

        {!hasMore && (
          <p className="mt-8 text-center text-xs font-body text-foreground/15">
            {friends.length} links with {friends.length} active · {allCirclePosts.length} articles in total
          </p>
        )}
    </PageShell>
  );
};

export default Friends;
