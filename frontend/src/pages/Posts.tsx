import { useState } from "react";
import { motion } from "motion/react";
import { Eye, MessageCircle, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import PageShell from "@/components/PageShell";

interface Post {
  id: number;
  title: string;
  excerpt: string;
  date: string;
  category: string;
  tags?: string[];
  views: number;
  comments: number;
}

const posts: Post[] = [
  {
    id: 1,
    title: "从零搭建个人设计系统的完整思路",
    excerpt: "设计系统不只是组件库，它是一套关于一致性、效率和沟通的方法论。这篇文章记录了我从调研到落地的全过程。",
    date: "3 天前",
    category: "设计",
    tags: ["design-system"],
    views: 1247,
    comments: 18,
  },
  {
    id: 2,
    title: "液态玻璃效果的 CSS 实现与优化",
    excerpt: "Apple 在 visionOS 中引入的液态玻璃语言如何用纯 CSS 复现，以及在低端设备上的性能优化策略。",
    date: "1 周前",
    category: "技术",
    tags: ["css", "performance"],
    views: 3082,
    comments: 24,
  },
  {
    id: 3,
    title: "为什么我选择做独立设计师",
    excerpt: "离开团队一年后的真实感受：自由、焦虑、成长，以及那些没人告诉你的事。",
    date: "2 周前",
    category: "随想",
    views: 892,
    comments: 31,
  },
  {
    id: 4,
    title: "React 19 中值得关注的设计模式变化",
    excerpt: "Server Components 和 Actions 正在重塑前端架构，这对设计师和前端开发者意味着什么。",
    date: "2025 年 12 月 18 日",
    category: "技术",
    tags: ["react"],
    views: 2156,
    comments: 12,
  },
  {
    id: 5,
    title: "网页排版中的节奏感：间距与留白",
    excerpt: "好的排版不是对齐和居中，而是建立阅读节奏。从音乐的角度理解视觉设计中的韵律。",
    date: "2025 年 12 月 5 日",
    category: "设计",
    views: 1873,
    comments: 15,
  },
  {
    id: 6,
    title: "用 Framer Motion 做有质感的页面过渡",
    excerpt: "动画不该是装饰，它是信息层级的一部分。分享几个我常用的过渡模式和背后的思考。",
    date: "2025 年 11 月 22 日",
    category: "技术",
    tags: ["animation", "react"],
    views: 4210,
    comments: 37,
  },
  {
    id: 7,
    title: "一个人的工作流：工具、习惯与心态",
    excerpt: "作为独立设计师，我每天的工作流程是怎样的，用了哪些工具，踩过哪些坑。",
    date: "2025 年 11 月 10 日",
    category: "随想",
    views: 625,
    comments: 8,
  },
  {
    id: 8,
    title: "深色模式设计的七个容易忽略的细节",
    excerpt: "深色模式不是简单地把白换成黑。阴影、对比度、色彩饱和度都需要重新审视。",
    date: "2025 年 10 月 28 日",
    category: "设计",
    views: 3140,
    comments: 26,
  },
];

const allCategories = ["全部", ...Array.from(new Set(posts.map((p) => p.category)))];

const Posts = () => {
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState("全部");
  const navigate = useNavigate();

  const filtered = posts.filter((post) => {
    const matchSearch =
      !search ||
      post.title.toLowerCase().includes(search.toLowerCase()) ||
      post.excerpt.toLowerCase().includes(search.toLowerCase());
    const matchCategory = activeCategory === "全部" || post.category === activeCategory;
    return matchSearch && matchCategory;
  });

  return (
    <PageShell
      eyebrow="Journal"
      title="Posts"
      description="文章、设计笔记与前端思考，按主题和节奏慢慢展开。"
      metaDescription="Felix 的文章列表，收纳设计、前端与个人写作。"
      headerAside={
        <span className="text-xs tracking-[0.18em] text-foreground/28">
          {posts.length} 篇文章
        </span>
      }
    >

        {/* Search + Filters */}
        <motion.div
          className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.06, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="relative max-w-xs flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground/25" />
            <input
              type="text"
              placeholder="搜索文章..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-foreground/8 bg-foreground/[0.03] py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-foreground/25 outline-none transition-colors focus:border-foreground/15 focus:bg-foreground/[0.05]"
            />
          </div>

          <div className="flex gap-1.5">
            {allCategories.map((cat) => (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors active:scale-[0.97] ${
                  activeCategory === cat
                    ? "bg-foreground/10 text-foreground"
                    : "text-foreground/35 hover:text-foreground/55"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </motion.div>

        {/* Post list */}
        <div className="mt-8">
          {filtered.map((post, i) => (
            <motion.article
              key={post.id}
              className="group cursor-pointer border-t border-foreground/6 py-6 transition-colors first:border-t-0 hover:bg-foreground/[0.02]"
              onClick={() => navigate(`/posts/${post.id}`)}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: 0.4,
                delay: 0.1 + i * 0.04,
                ease: [0.16, 1, 0.3, 1],
              }}
            >
              <h2 className="text-base font-medium leading-snug text-foreground/90 transition-colors group-hover:text-foreground sm:text-lg">
                {post.title}
              </h2>
              <p className="mt-2 line-clamp-1 text-sm leading-relaxed text-foreground/35">
                {post.excerpt}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-foreground/25">
                <span>{post.date}</span>
                <span>{post.category}</span>
                {post.tags?.map((tag) => (
                  <span key={tag} className="text-foreground/20">
                    /{tag}
                  </span>
                ))}
                <span className="ml-auto flex items-center gap-1">
                  <Eye className="h-3 w-3" />
                  {post.views.toLocaleString()}
                </span>
                <span className="flex items-center gap-1">
                  <MessageCircle className="h-3 w-3" />
                  {post.comments}
                </span>
              </div>
            </motion.article>
          ))}

          {filtered.length === 0 && (
            <p className="py-16 text-center text-sm text-foreground/25">没有找到匹配的文章</p>
          )}
        </div>
    </PageShell>
  );
};

export default Posts;
