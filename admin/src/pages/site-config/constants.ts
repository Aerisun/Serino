export const PAGE_KEYS = [
  "activity",
  "notFound",
  "posts",
  "diary",
  "friends",
  "excerpts",
  "thoughts",
  "guestbook",
  "calendar",
];

export const LOGIN_MODE_OPTIONS = ["disable", "enable", "force"] as const;
export const AVATAR_STRATEGY_OPTIONS = [
  "identicon",
  "gravatar",
  "library",
] as const;
export const MIGRATION_STATE_OPTIONS = [
  "draft",
  "syncing",
  "ready",
  "done",
] as const;

// --- Human-readable labels for select options ---

type LangLabels = Record<string, { zh: string; en: string }>;

export const LOGIN_MODE_LABELS: LangLabels = {
  disable: { zh: "关闭登录", en: "Login Disabled" },
  enable: { zh: "可选登录", en: "Login Enabled" },
  force: { zh: "必须登录", en: "Login Required" },
};

export const AVATAR_STRATEGY_LABELS: LangLabels = {
  identicon: { zh: "随机图案", en: "Random Pattern" },
  gravatar: { zh: "在线头像", en: "Gravatar" },
  library: { zh: "头像库", en: "Avatar Library" },
};

export const MIGRATION_STATE_LABELS: LangLabels = {
  draft: { zh: "草稿", en: "Draft" },
  syncing: { zh: "同步中", en: "Syncing" },
  ready: { zh: "就绪", en: "Ready" },
  done: { zh: "已完成", en: "Done" },
};

export const MODERATION_MODE_LABELS: LangLabels = {
  all_pending: { zh: "全部待审", en: "All Pending" },
  manual: { zh: "人工审核", en: "Manual" },
  mixed: { zh: "混合模式", en: "Mixed" },
};

export const DEFAULT_SORTING_LABELS: LangLabels = {
  latest: { zh: "最新优先", en: "Newest First" },
  oldest: { zh: "最早优先", en: "Oldest First" },
  hottest: { zh: "最热优先", en: "Hottest First" },
};

export const GUEST_AVATAR_MODE_LABELS: LangLabels = {
  preset: { zh: "预设头像", en: "Preset" },
  identicon: { zh: "随机图案", en: "Random Pattern" },
  gravatar: { zh: "在线头像", en: "Gravatar" },
};

export const SOCIAL_SOFTWARE_OPTIONS = [
  "github",
  "gitlab",
  "gitee",
  "telegram",
  "wechat",
  "qq",
  "feishu",
  "discord",
  "whatsapp",
  "line",
  "facebook",
  "instagram",
  "linkedin",
  "youtube",
  "bilibili",
  "zhihu",
  "juejin",
  "xiaohongshu",
  "weibo",
  "twitter",
  "x",
  "netease",
] as const;

export const SOCIAL_SOFTWARE_LABELS: LangLabels = {
  github: { zh: "GitHub", en: "GitHub" },
  gitlab: { zh: "GitLab", en: "GitLab" },
  gitee: { zh: "Gitee", en: "Gitee" },
  telegram: { zh: "Telegram", en: "Telegram" },
  wechat: { zh: "微信", en: "WeChat" },
  qq: { zh: "QQ", en: "QQ" },
  feishu: { zh: "飞书", en: "Feishu" },
  discord: { zh: "Discord", en: "Discord" },
  whatsapp: { zh: "WhatsApp", en: "WhatsApp" },
  line: { zh: "LINE", en: "LINE" },
  facebook: { zh: "Facebook", en: "Facebook" },
  instagram: { zh: "Instagram", en: "Instagram" },
  linkedin: { zh: "LinkedIn", en: "LinkedIn" },
  youtube: { zh: "YouTube", en: "YouTube" },
  bilibili: { zh: "Bilibili", en: "Bilibili" },
  zhihu: { zh: "知乎", en: "Zhihu" },
  juejin: { zh: "掘金", en: "Juejin" },
  xiaohongshu: { zh: "小红书", en: "RedNote" },
  weibo: { zh: "微博", en: "Weibo" },
  twitter: { zh: "Twitter", en: "Twitter" },
  x: { zh: "X", en: "X" },
  netease: { zh: "网易云", en: "NetEase Cloud Music" },
};

export const PAGE_KEY_LABELS: LangLabels = {
  activity: { zh: "首页活动区", en: "Homepage Activity" },
  notFound: { zh: "404 页面", en: "404 Page" },
  posts: { zh: "文章", en: "Posts" },
  diary: { zh: "日记", en: "Diary" },
  friends: { zh: "友链", en: "Friends" },
  excerpts: { zh: "文摘", en: "Excerpts" },
  thoughts: { zh: "碎碎念", en: "Thoughts" },
  guestbook: { zh: "留言簿", en: "Guestbook" },
  resume: { zh: "简历", en: "Resume" },
  calendar: { zh: "日历", en: "Calendar" },
};

/** Helper: get label for a lang, fallback to raw value */
export function optionLabel(
  labels: LangLabels,
  value: string,
  lang: "zh" | "en",
): string {
  return labels[value]?.[lang] ?? value;
}
