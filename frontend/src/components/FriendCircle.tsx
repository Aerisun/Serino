import { ArrowUpRight } from "lucide-react";
import { useNavigate } from "react-router-dom";

interface FriendPost {
  avatar: string;
  blogName: string;
  title: string;
  date: string;
}

const friendPosts: FriendPost[] = [
  {
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Natsume",
    blogName: "夏目的博客",
    title: "网络流算法详解",
    date: "2026-03-18",
  },
  {
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Miku",
    blogName: "喵二の小博客",
    title: "\u201C糖\u201D",
    date: "2026-03-16",
  },
  {
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Natsume",
    blogName: "夏目的博客",
    title: "一些思考",
    date: "2026-03-14",
  },
  {
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Erhecy",
    blogName: "Erhecy's Blog",
    title: "在博客中优雅地添加 Bilibili 追番页面",
    date: "2026-03-13",
  },
  {
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=BaiYuan",
    blogName: "空山灵雨",
    title: "一招解决 Origin 运行报错：找不到 mfc140u.dll",
    date: "2026-03-11",
  },
  {
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Akara",
    blogName: "AkaraChen",
    title: "如何使用 Cloudflare API 為網站新增數據監測大屏",
    date: "2026-03-10",
  },
  {
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Paul",
    blogName: "保罗的小宇宙",
    title: "Hand Motion Retargeting",
    date: "2026-03-10",
  },
  {
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Lucifer",
    blogName: "Lucifer's Blog",
    title: "To panic! or Not to panic!",
    date: "2026-03-10",
  },
  {
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Qingya",
    blogName: "轻雅阁",
    title: "Spring Boot 3 迁移指南",
    date: "2026-03-08",
  },
];

const FriendCircle = () => {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-baseline justify-between mb-5">
        <h3 className="text-sm font-body font-medium text-foreground/50 uppercase tracking-widest">
          朋友圈
        </h3>
        <button
          onClick={() => navigate("/friends")}
          className="text-[11px] font-body text-foreground/30 hover:text-foreground/50 transition-colors flex items-center gap-1"
        >
          查看全部 <ArrowUpRight className="h-3 w-3" />
        </button>
      </div>

      <div className="overflow-y-auto max-h-[420px] scrollbar-hide pr-1 -mr-1 flex flex-col gap-0.5">
        {friendPosts.map((post, i) => (
          <div
            key={i}
            className="group flex items-start gap-3 rounded-xl px-2.5 py-3 transition-colors hover:bg-foreground/[0.04]"
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
              <p className="text-[13px] font-body font-medium text-foreground/80 group-hover:text-foreground transition-colors leading-snug truncate">
                {post.title}
              </p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[10px] font-body text-foreground/30 truncate">
                  {post.blogName}
                </span>
                <span className="text-[10px] font-body text-foreground/15">
                  · {post.date}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default FriendCircle;
