import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowLeft, Eye, MessageCircle, Clock, Tag } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import FallingPetals from "@/components/FallingPetals";
import CommentSection from "@/components/CommentSection";
import PageMeta from "@/components/PageMeta";
import { fetchPublicContentEntry, formatPublishedDate, splitContentParagraphs, type PublicContentEntry } from "@/lib/api";

interface PostData {
  slug: string;
  title: string;
  date: string;
  category: string;
  tags: string[];
  views: number;
  comments: number;
  readTime: string;
  content: string[];
}

const postsData: Record<string, PostData> = {
  "1": {
    slug: "from-zero-design-system",
    title: "从零搭建个人设计系统的完整思路",
    date: "2026 年 3 月 18 日",
    category: "设计",
    tags: ["design-system", "ui"],
    views: 1247,
    comments: 18,
    readTime: "12 分钟",
    content: [
      "设计系统不只是组件库，它是一套关于一致性、效率和沟通的方法论。过去半年，我从零开始构建了自己的设计系统，这篇文章记录了完整的过程。",
      "## 为什么需要设计系统",
      "当项目规模增长到一定程度，你会发现同样的按钮样式被写了五遍，同样的间距在不同页面有三种不同的值。设计系统的核心目的，是把这些隐性的决策显性化。",
      "我的方法是先从「设计代币」开始——颜色、字号、间距、圆角这些最基础的变量。它们是整个系统的基因。选定一套色板后，所有组件的颜色都从这里派生，这样换肤就变成了换一组变量的事。",
      "## 从原子到分子",
      "Brad Frost 的 Atomic Design 给了我很大启发。我把组件分成了三层：基础元素（按钮、输入框、标签）、组合组件（搜索栏、卡片、导航项）、页面模板。每一层只依赖下一层，保持单向数据流。",
      "实际操作中最大的挑战是「什么时候该抽象」。太早抽象会过度工程化，太晚又会导致大量重复代码。我的经验是：当同一个模式出现第三次时，就是抽象的好时机。",
      "## 文档比代码更重要",
      "组件写好了不等于设计系统就建好了。最关键的一环是文档。每个组件需要说明：什么时候用、什么时候不用、有哪些变体、交互状态是什么。没有文档的组件库，只是一个文件夹。",
      "## 回顾与思考",
      "做设计系统最大的收获，不是那些漂亮的组件，而是重新审视了「一致性」这个概念。一致性不是机械的统一，而是让用户在不同场景下都能感受到同一种设计语言。",
    ],
  },
  "2": {
    slug: "liquid-glass-css-notes",
    title: "液态玻璃效果的 CSS 实现与优化",
    date: "2026 年 3 月 12 日",
    category: "技术",
    tags: ["css", "performance"],
    views: 3082,
    comments: 24,
    readTime: "8 分钟",
    content: [
      "Apple 在 visionOS 中引入了一种全新的视觉语言——液态玻璃（Liquid Glass）。这种半透明、带模糊、有折射感的材质效果，正在重新定义界面设计的可能性。",
      "## 基础实现",
      "最基本的液态玻璃效果，核心就是三个 CSS 属性的组合：backdrop-filter: blur()、半透明背景色、以及微妙的边框。",
      "但这只是起点。真正好看的液态玻璃效果，还需要考虑光照模拟、内阴影、以及不同背景下的适配。",
      "## 性能优化",
      "backdrop-filter 是 GPU 密集型操作。在低端设备上，大面积使用会导致明显的掉帧。我的优化策略包括减少模糊半径、限制使用面积、使用 will-change 以及提供降级方案。",
      "## 动态效果",
      "静态的毛玻璃效果很容易显得呆板。加入微妙的动态——比如随鼠标位置变化的光泽、滚动时的透明度渐变——可以让效果更生动。但要克制，过多的动效会让界面显得浮躁。",
    ],
  },
  "3": {
    slug: "why-i-choose-indie-design",
    title: "为什么我选择做独立设计师",
    date: "2026 年 3 月 7 日",
    category: "随想",
    tags: ["career", "freelance"],
    views: 892,
    comments: 31,
    readTime: "10 分钟",
    content: [
      "离开团队已经一年了。这一年里经历了很多以前想象不到的事情——自由、焦虑、成长，以及那些没人提前告诉你的坑。",
      "## 自由的代价",
      "自由是独立工作最大的吸引力，但自由也意味着没人帮你做决定。每天早上醒来，你得自己决定今天做什么、先做哪个、做到什么程度算完成。这种自主权一开始让人兴奋，但很快就会变成一种隐形的压力。",
      "## 关于收入",
      "独立设计师的收入不稳定是老生常谈了。好的月份可能比上班时赚得多，但差的月份可能几乎没有进账。我学会了提前规划三个月的生活费用，把每个项目的收入分成「生活」「储蓄」「投资自己」三份。",
      "## 成长比想象中快",
      "当你没有团队可以依赖的时候，你会被迫学习很多以前不碰的东西——谈判、合同、财务、营销。这些技能在团队里有专人负责，独立后全部得自己来。累，但成长速度是之前的好几倍。",
      "## 写在最后",
      "如果你也在考虑独立，我的建议是：先攒半年的生活费，然后跳。不要等到「准备好了」再开始，因为你永远不会觉得准备好了。",
    ],
  },
  "4": {
    slug: "react-19-design-pattern-shifts",
    title: "React 19 中值得关注的设计模式变化",
    date: "2025 年 12 月 18 日",
    category: "技术",
    tags: ["react", "architecture"],
    views: 2156,
    comments: 12,
    readTime: "9 分钟",
    content: [
      "React 19 带来了 Server Components 和 Actions，这两个特性正在根本性地重塑前端架构。对于设计师和前端开发者来说，这意味着什么？",
      "## Server Components 的设计影响",
      "Server Components 让我们可以在服务端渲染组件，这意味着初始加载速度更快，JavaScript bundle 更小。从设计角度看，这让我们可以更大胆地使用复杂的布局，因为性能成本降低了。",
      "## Actions 简化了交互",
      "以前处理表单提交需要写很多 state 管理的代码，现在 Actions 让这一切变得简洁。对于设计师来说，这意味着可以更快速地把设计稿变成可交互的原型。",
      "## 总结",
      "React 19 的变化本质上是在降低前端开发的复杂度。作为设计师，我们应该拥抱这种变化，因为它让设计到实现的距离更短了。",
    ],
  },
  "5": {
    slug: "typographic-rhythm-and-spacing",
    title: "网页排版中的节奏感：间距与留白",
    date: "2025 年 12 月 5 日",
    category: "设计",
    tags: ["typography", "layout"],
    views: 1873,
    comments: 15,
    readTime: "7 分钟",
    content: [
      "好的排版不是对齐和居中，而是建立阅读节奏。这个概念听起来抽象，但其实可以从音乐的角度来理解。",
      "## 节奏的基本单位",
      "在音乐中，节奏由拍子构成。在排版中，「拍子」就是你的基础间距单位。我通常用 4px 作为最小单位，所有间距都是 4 的倍数：4、8、12、16、24、32、48、64。这样做的好处是视觉上会有一种和谐感，就像音乐里的节拍器。",
      "## 留白是无声的段落",
      "留白不是「什么都没有」，它是内容之间的呼吸。太紧凑的排版会让读者感到窒息，太松散又会失去凝聚力。找到这个平衡点，就是排版的核心功力。",
      "## 垂直节奏",
      "段落之间的间距应该大于行间距，标题上方的间距应该大于标题下方的间距。这些规则听起来简单，但真正做到位需要反复调整。",
    ],
  },
  "6": {
    slug: "framer-motion-page-transitions",
    title: "用 Framer Motion 做有质感的页面过渡",
    date: "2025 年 11 月 22 日",
    category: "技术",
    tags: ["animation", "react"],
    views: 4210,
    comments: 37,
    readTime: "11 分钟",
    content: [
      "动画不该是装饰，它是信息层级的一部分。当一个元素出现在屏幕上时，它出现的方式会影响用户对这个元素重要性的判断。",
      "## 入场动画的原则",
      "入场动画的核心原则是「从哪里来」。一个从下方滑入的卡片，暗示着它是新产生的内容；一个从右侧滑入的面板，暗示着它是一个新的层级。方向传递信息。",
      "## 常用的过渡模式",
      "我最常用的三种模式：淡入上移（通用）、滑入（导航相关）、缩放（焦点切换）。每种模式都有其适用场景，混用会让界面显得混乱。",
      "## 时间和缓动",
      "200-300ms 是大多数过渡动画的最佳时长。太短用户看不到，太长会觉得拖沓。缓动曲线我推荐 cubic-bezier(0.16, 1, 0.3, 1)——快入慢出，感觉非常自然。",
    ],
  },
  "7": {
    slug: "solo-workflow-tools-and-rhythm",
    title: "一个人的工作流：工具、习惯与心态",
    date: "2025 年 11 月 10 日",
    category: "随想",
    tags: ["workflow", "productivity"],
    views: 625,
    comments: 8,
    readTime: "6 分钟",
    content: [
      "作为独立设计师，我的工作流程和在团队里完全不同。没有晨会，没有项目管理工具的提醒，一切靠自驱。",
      "## 工具链",
      "设计用 Figma，代码用 VS Code，写作用 Obsidian，项目管理用 Linear（虽然只有一个人用）。工具不在多，在于用得顺手。我花了很长时间才摆脱「工具焦虑」——总觉得换一个工具就能提高效率。",
      "## 时间管理",
      "我把一天分成三个块：上午做创造性工作（设计、写作），下午做执行性工作（编码、沟通），晚上做学习和反思。这个节奏不是一开始就找到的，是试了很多种安排后慢慢稳定下来的。",
      "## 心态",
      "最重要的一点：不要跟别人比产出。独立工作的节奏是自己的，有的时候一天能完成一周的量，有的时候一周只能完成一天的量。接受这种波动，才能持续下去。",
    ],
  },
  "8": {
    slug: "dark-mode-design-details",
    title: "深色模式设计的七个容易忽略的细节",
    date: "2025 年 10 月 28 日",
    category: "设计",
    tags: ["dark-mode", "ui"],
    views: 3140,
    comments: 26,
    readTime: "8 分钟",
    content: [
      "深色模式不是简单地把白换成黑。很多设计师在做深色模式时会忽略一些关键细节，导致最终效果看起来「对但不舒服」。",
      "## 不要用纯黑",
      "纯黑（#000000）作为背景会让文字和界面元素显得刺眼。建议用深灰，比如 #0a0a0a 或 #111111，这样更柔和。",
      "## 阴影需要重新设计",
      "浅色模式下的阴影是通过暗色来模拟深度的，但在深色背景上，暗色阴影几乎看不见。你可能需要反过来，用微妙的亮色光晕来表示层级。",
      "## 饱和度要降低",
      "在浅色背景上好看的鲜艳色彩，放到深色背景上会显得刺眼。对于重点色彩，建议降低 10-20% 的饱和度，增加一点亮度。",
      "## 对比度的平衡",
      "WCAG 要求文字和背景之间有足够的对比度，但在深色模式下，太高的对比度（白文字+黑背景）反而会导致视觉疲劳。建议主要文字用 rgba(255,255,255,0.87) 而不是纯白。",
      "## 图片和图标",
      "亮色模式下的图片直接放到深色背景上可能会有白边或者整体偏亮。解决方案是给图片加一层轻微的暗化滤镜，或者准备专门的深色模式版本。",
    ],
  },
};

const fallbackBySlug = Object.fromEntries(
  Object.values(postsData).map((item) => [item.slug, item]),
);

const estimateReadTime = (value: string) => `${Math.max(1, Math.ceil(value.length / 180))} 分钟`;

const buildRemotePost = (entry: PublicContentEntry, fallback?: PostData): PostData => ({
  slug: entry.slug,
  title: entry.title,
  date: formatPublishedDate(entry.published_at) || fallback?.date || "",
  category: fallback?.category ?? "内容",
  tags: entry.tags.length ? entry.tags : (fallback?.tags ?? []),
  views: fallback?.views ?? 0,
  comments: fallback?.comments ?? 0,
  readTime: fallback?.readTime ?? estimateReadTime(entry.body),
  content: splitContentParagraphs(entry.body),
});

const PostDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const initialFallback = (id ? postsData[id] : undefined) ?? (id ? fallbackBySlug[id] : undefined) ?? null;
  const [post, setPost] = useState<PostData | null>(initialFallback);

  useEffect(() => {
    let cancelled = false;

    const fallback = (id ? postsData[id] : undefined) ?? (id ? fallbackBySlug[id] : undefined) ?? null;
    const targetSlug = fallback?.slug ?? id;

    setPost(fallback);

    if (!targetSlug) {
      return () => {
        cancelled = true;
      };
    }

    const loadPost = async () => {
      try {
        const entry = await fetchPublicContentEntry("posts", targetSlug);
        if (cancelled) {
          return;
        }

        setPost(buildRemotePost(entry, fallback ?? undefined));
      } catch {
        if (!cancelled) {
          setPost(fallback);
        }
      }
    };

    void loadPost();

    return () => {
      cancelled = true;
    };
  }, [id]);

  if (!post) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
        <PageMeta title="文章不存在" description="你访问的文章暂时不存在。" />
        <p className="text-foreground/30">文章不存在</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <PageMeta title={post.title} description={post.content[0]} />
      <FallingPetals />
      <Navbar />

      <main className="mx-auto max-w-2xl px-6 pt-28 pb-20 lg:px-8">
        <motion.button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm font-body text-foreground/30 hover:text-foreground/60 transition-colors mb-8 active:scale-95"
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        >
          <ArrowLeft className="h-4 w-4" />
          返回
        </motion.button>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="flex flex-wrap items-center gap-3 text-xs font-body text-foreground/25 mb-4">
            <span>{post.date}</span>
            <span className="px-2 py-0.5 rounded-md bg-foreground/5">{post.category}</span>
            <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{post.readTime}</span>
            <span className="flex items-center gap-1"><Eye className="h-3 w-3" />{post.views.toLocaleString()}</span>
            <span className="flex items-center gap-1"><MessageCircle className="h-3 w-3" />{post.comments}</span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-heading italic tracking-tight text-foreground leading-tight">
            {post.title}
          </h1>

          <div className="flex flex-wrap gap-2 mt-4">
            {post.tags.map((tag) => (
              <span key={tag} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-foreground/5 text-[11px] font-body text-foreground/30">
                <Tag className="h-3 w-3" />
                {tag}
              </span>
            ))}
          </div>
        </motion.div>

        <motion.article
          className="mt-10"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
        >
          {post.content.map((block, i) => {
            if (block.startsWith("## ")) {
              return (
                <h2 key={i} className="text-lg font-heading italic text-foreground/90 mt-10 mb-4">
                  {block.replace("## ", "")}
                </h2>
              );
            }
            return (
              <p key={i} className="text-sm font-body text-foreground/50 leading-[1.85] mb-5">
                {block}
              </p>
            );
          })}
        </motion.article>

        <div className="border-t border-foreground/5 mt-12 pt-8">
          <p className="text-xs font-body text-foreground/20 text-center">— 完 —</p>
        </div>

        <CommentSection
          commentCount={post.comments}
          contentType="posts"
          contentSlug={post.slug}
        />
      </main>
      <Footer />
    </div>
  );
};

export default PostDetail;
