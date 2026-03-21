import { SITE_NAME } from "./site";

export type PageWidth = "narrow" | "content" | "wide";

export interface PageMotionConfig {
  duration: number;
  delay: number;
  stagger: number;
}

export interface ResumeExperienceConfig {
  role: string;
  org: string;
  period: string;
  desc: string;
}

export const pageConfig = {
  home: {
    dashboardLabel: "Dashboard",
    title: "Recent Pulse",
    description: "把常看的小站、最近更新和内容脉络轻轻放在一起。",
  },
  notFound: {
    eyebrow: "404",
    title: "页面不在这里",
    description: "不属于当前网站壳层。先回到首页，再从主导航继续。",
    metaTitle: "页面未找到",
    metaDescription: "你访问的页面不存在，返回 Felix 的个人网站继续浏览。",
  },
  posts: {
    eyebrow: "Journal",
    title: "Posts",
    description: "文章、设计笔记与前端思考，按主题和节奏慢慢展开。",
    metaDescription: `${SITE_NAME} 的文章列表，收纳设计、前端与个人写作。`,
    width: "content" as PageWidth,
    headerCountLabel: (count: number) => `${count} 篇文章`,
    searchPlaceholder: "搜索文章...",
    emptyMessage: "没有找到匹配的文章",
    categories: { all: "全部" },
    motion: { duration: 0.4, delay: 0.06, stagger: 0.04 },
  },
  diary: {
    eyebrow: "Diary",
    title: "日记",
    description: "每天一点点，记录生活的温度，也记录节奏如何从一天里慢慢长出来。",
    metaDescription: `${SITE_NAME} 的日记列表，记录天气、心情与每天的生活片段。`,
    width: "narrow" as PageWidth,
    motion: { duration: 0.4, delay: 0.06, stagger: 0.04 },
  },
  friends: {
    eyebrow: "Circle",
    title: "朋友们",
    description: "海内存知己，天涯若比邻。把常看的小站和最近的回响轻轻放在一起。",
    metaDescription: `${SITE_NAME} 的友链与朋友圈，收纳常去的小站与最近更新。`,
    width: "wide" as PageWidth,
    headerCountLabel: (count: number) => `${count} 个站点`,
    circleTitle: "Friend Circle",
    circleSubtitle: (links: number, posts: number) =>
      `${links} links · ${posts} articles in total`,
    statusLabel: "整理中",
    loadMoreLabel: "Load more",
    loadingLabel: "加载中...",
    pageSize: 10,
    motion: { duration: 0.4, delay: 0.08, stagger: 0.04 },
  },
  excerpts: {
    eyebrow: "Reading Room",
    title: "文摘",
    description: "摘录那些让我停下来想一想的文字，留一段回声，也留一点空白。",
    metaDescription: `${SITE_NAME} 的文摘收藏，记录设计、美学与生活阅读中的片段。`,
    width: "content" as PageWidth,
    motion: { duration: 0.4, delay: 0.06, stagger: 0.04 },
    modalCloseLabel: "关闭",
  },
  thoughts: {
    eyebrow: "Dispatches",
    title: "碎碎念",
    description: "短句、片段、当下感受，像是从工作和生活里捞出来的一些微光。",
    metaDescription: `${SITE_NAME} 的碎碎念时间线，记录设计、生活与日常想法。`,
    width: "narrow" as PageWidth,
    motion: { duration: 0.4, delay: 0.08, stagger: 0.04 },
  },
  guestbook: {
    eyebrow: "Guestbook",
    title: "留言板",
    description: "留下一点话语和气味，让这座个人站不只是独白，也有你来过的痕迹。",
    metaDescription: `${SITE_NAME} 的留言板，欢迎留下你的足迹与想法。`,
    width: "narrow" as PageWidth,
    namePlaceholder: "你的名字",
    contentPlaceholder: "写点什么...",
    submitLabel: "发送",
    motion: { duration: 0.45, delay: 0.06, stagger: 0.04 },
  },
  resume: {
    eyebrow: "Profile",
    title: SITE_NAME,
    description: "网页设计与前端开发并行，关注视觉秩序、动效节奏与内容呈现的精度。",
    metaTitle: "简历",
    metaDescription: `${SITE_NAME} 的个人简历，包含设计、前端与工作经历。`,
    width: "content" as PageWidth,
    downloadLabel: "打印 / 导出",
    bio: "我做网页设计，也写前端，专注于将视觉美学与交互体验融合为一体。擅长设计系统搭建、动效设计和响应式开发，追求每一个像素的精确与每一帧动画的流畅。",
    skills: [
      "React",
      "TypeScript",
      "Tailwind CSS",
      "Figma",
      "Framer Motion",
      "Next.js",
      "Vue",
      "Design Systems",
      "Responsive Design",
      "SVG/Canvas",
      "Git",
      "Node.js",
    ],
    experience: [
      {
        role: "独立设计师 & 前端开发",
        org: "Freelance",
        period: "2024 — 至今",
        desc: "为多个品牌和创业团队提供从视觉设计到前端落地的全流程服务，专注个人品牌网站和产品界面设计。",
      },
      {
        role: "前端开发工程师",
        org: "某科技公司",
        period: "2022 — 2024",
        desc: "负责核心产品的前端架构和设计系统搭建，主导了暗色模式适配和动效体系的建立。",
      },
      {
        role: "UI/UX 设计实习",
        org: "某设计工作室",
        period: "2021 — 2022",
        desc: "参与多个 B 端产品的界面设计，学习了从用户调研到交付的完整设计流程。",
      },
      {
        role: "数字媒体艺术",
        org: "某大学",
        period: "2018 — 2022",
        desc: "系统学习了视觉传达、交互设计和前端开发，毕业设计获院级优秀作品。",
      },
    ] as ResumeExperienceConfig[],
    motion: { duration: 0.45, delay: 0.06, stagger: 0.04 },
  },
  calendar: {
    eyebrow: "Calendar",
    title: "日历",
    description: "把帖子、日记和文摘按日期铺开，回看最近一段时间的节奏变化。",
    metaDescription: `${SITE_NAME} 的内容日历，按日期浏览帖子、日记与文摘。`,
    width: "wide" as PageWidth,
    monthLabels: ["一月", "二月", "三月", "四月", "五月", "六月", "七月", "八月", "九月", "十月", "十一月", "十二月"],
    weekdayLabels: ["一", "二", "三", "四", "五", "六", "日"],
    motion: { duration: 0.5, delay: 0.08, stagger: 0.05 },
  },
  activity: {
    dashboardLabel: "Dashboard",
    title: "Recent Pulse",
  },
} as const;

export type PageConfigMap = typeof pageConfig;
