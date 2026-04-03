export type FieldInputKind = "text" | "textarea" | "number" | "select" | "list";
export type FieldSource = "base" | "extra";

export interface PageFieldDefinition {
  key: string;
  source: FieldSource;
  input: FieldInputKind;
  label: string;
  helpTitle: string;
  helpDescription: string;
  usageItems: string[];
  optional?: boolean;
  placeholder?: string;
  options?: Array<{ value: string; label: string }>;
}

export const WIDTH_OPTIONS = [
  { value: "", label: "自动跟随默认宽度" },
  { value: "max-w-2xl", label: "窄版内容宽度" },
  { value: "max-w-3xl", label: "标准内容宽度" },
  { value: "max-w-4xl", label: "宽版内容宽度" },
];

const baseField = (
  key: string,
  input: FieldInputKind,
  label: string,
  helpTitle: string,
  helpDescription: string,
  usageItems: string[],
  optional = true,
  options?: PageFieldDefinition["options"],
): PageFieldDefinition => ({
  key,
  source: "base",
  input,
  label,
  helpTitle,
  helpDescription,
  usageItems,
  optional,
  ...(options ? { options } : {}),
});

const extraField = (
  key: string,
  input: FieldInputKind,
  label: string,
  helpTitle: string,
  helpDescription: string,
  usageItems: string[],
  placeholder?: string,
  optional = true,
): PageFieldDefinition => ({
  key,
  source: "extra",
  input,
  label,
  helpTitle,
  helpDescription,
  usageItems,
  optional,
  ...(placeholder ? { placeholder } : {}),
});

const TITLE_FIELD = baseField(
  "title",
  "text",
  "页面主标题",
  "页面最醒目的标题",
  "这是当前页面或模块真正展示给访客的主标题。",
  ["页面主标题"],
  false,
);

const SUBTITLE_FIELD = baseField(
  "subtitle",
  "textarea",
  "页面导语",
  "页面标题下方的说明文案",
  "这段文案会直接显示在页面头部，用来解释页面内容和语气。",
  ["页面头部说明文案"],
);

const EYEBROW_FIELD = extraField(
  "eyebrow",
  "text",
  "标题上方小标签",
  "页面标题上方的小号标签",
  "适合放栏目名、英文短词或气氛说明。",
  ["页面标题上方小标签"],
);

const META_TITLE_FIELD = extraField(
  "metaTitle",
  "text",
  "SEO / 分享标题",
  "浏览器标题和分享标题",
  "会影响标签页标题和分享卡片标题。",
  ["页面浏览器标题", "分享卡片标题"],
);

const META_DESCRIPTION_FIELD = extraField(
  "metaDescription",
  "textarea",
  "SEO / 分享描述",
  "分享和搜索结果里的简介",
  "不会显示在页面正文里，主要用于分享卡片和 SEO 描述。",
  ["页面 SEO 描述", "分享卡片描述"],
);

const SEARCH_PLACEHOLDER_FIELD = baseField(
  "search_placeholder",
  "text",
  "搜索框提示词",
  "搜索输入框 placeholder",
  "会直接出现在列表页搜索框里。",
  ["页面搜索框 placeholder"],
);

const EMPTY_MESSAGE_FIELD = baseField(
  "empty_message",
  "textarea",
  "空状态文案",
  "没有内容时显示的提示",
  "当列表为空或筛选无结果时显示。",
  ["页面空状态提示"],
);

const WIDTH_FIELD = baseField(
  "max_width",
  "select",
  "页面内容宽度",
  "页面主体区域的宽度",
  "控制页面内容区域更偏阅读还是更偏展示。",
  ["页面主体宽度"],
  true,
  WIDTH_OPTIONS,
);

const PAGE_SIZE_FIELD = baseField(
  "page_size",
  "number",
  "每次加载条数",
  "列表页每次请求的条数",
  "适用于分页或无限滚动列表页。",
  ["列表页分页大小"],
);

const PAGE_FIELDS: Record<string, PageFieldDefinition[]> = {
  activity: [
    TITLE_FIELD,
    extraField("dashboardLabel", "text", "首页活动区眉标题", "首页活动区小标签", "显示在活动区标题上方。", ["首页活动区小标签"]),
    extraField("friendCircleTitle", "text", "首页友邻区标题", "首页友邻卡片标题", "控制首页友邻卡片标题。", ["首页友邻卡片标题"]),
    extraField("friendCircleViewAllLabel", "text", "首页友邻区「查看全部」按钮", "友邻卡片跳转按钮文案", "点击后进入完整友链页。", ["首页友邻卡片按钮"]),
    extraField("friendCircleErrorTitle", "text", "首页友邻区加载失败标题", "友邻动态请求失败标题", "友邻动态加载失败时显示。", ["首页友邻卡片错误标题"]),
    extraField("friendCircleRetryLabel", "text", "首页友邻区重试按钮", "友邻动态重试按钮文案", "友邻动态加载失败时的按钮文案。", ["首页友邻卡片错误按钮"]),
    extraField("friendCircleEmptyMessage", "textarea", "首页友邻区空状态文案", "友邻动态为空时的提示", "没有公开友邻动态时显示。", ["首页友邻卡片空状态"]),
    extraField("recentActivityTitle", "text", "首页最近动态标题", "最近动态卡片标题", "控制最近动态卡片标题。", ["首页最近动态卡片标题"]),
    extraField("recentActivityErrorTitle", "text", "首页最近动态加载失败标题", "最近动态请求失败标题", "最近动态加载失败时显示。", ["首页最近动态卡片错误标题"]),
    extraField("recentActivityRetryLabel", "text", "首页最近动态重试按钮", "最近动态重试按钮文案", "最近动态加载失败时的按钮文案。", ["首页最近动态卡片错误按钮"]),
    extraField("recentActivityEmptyMessage", "textarea", "首页最近动态空状态文案", "最近动态为空时的提示", "没有可展示动态时显示。", ["首页最近动态卡片空状态"]),
    extraField("heatmapTitle", "text", "热力图标题", "热力图模块标题", "控制首页底部热力图模块的标题。", ["首页热力图标题"]),
    extraField("heatmapThisWeekLabel", "text", "热力图「本周」标签", "热力图统计项名称", "用于第一项统计指标。", ["首页热力图统计标签"]),
    extraField("heatmapPeakWeekLabel", "text", "热力图「峰值周」标签", "热力图统计项名称", "用于第二项统计指标。", ["首页热力图统计标签"]),
    extraField("heatmapAverageWeekLabel", "text", "热力图「周平均」标签", "热力图统计项名称", "用于第三项统计指标。", ["首页热力图统计标签"]),
  ],
  notFound: [
    TITLE_FIELD,
    SUBTITLE_FIELD,
    META_TITLE_FIELD,
    META_DESCRIPTION_FIELD,
    extraField("badgeLabel", "text", "404 徽标文字", "404 页面顶部小标签", "通常是很短的标识，例如 404。", ["404 页面顶部徽标"]),
    extraField("homeLabel", "text", "404「返回首页」按钮", "404 页面主按钮文案", "控制返回首页按钮文字。", ["404 页面主按钮"]),
    extraField("backLabel", "text", "404「返回上页」按钮", "404 页面次按钮文案", "控制返回上页按钮文字。", ["404 页面次按钮"]),
  ],
  posts: [
    TITLE_FIELD,
    SUBTITLE_FIELD,
    EYEBROW_FIELD,
    META_DESCRIPTION_FIELD,
    SEARCH_PLACEHOLDER_FIELD,
    EMPTY_MESSAGE_FIELD,
    WIDTH_FIELD,
    PAGE_SIZE_FIELD,
    extraField("errorTitle", "text", "文章页加载失败标题", "文章列表错误标题", "文章列表加载失败时显示。", ["文章列表错误标题", "文章详情错误标题"]),
    extraField("retryLabel", "text", "文章页重试按钮", "文章错误状态按钮文案", "用于文章列表和文章详情错误状态。", ["文章列表错误按钮", "文章详情错误按钮"]),
    extraField("loadMoreLabel", "text", "文章页加载更多文案", "文章列表加载更多提示", "列表继续加载时显示。", ["文章列表底部加载提示"]),
    extraField("category_all_label", "text", "文章分类「全部」标签", "文章分类筛选里的全部标签", "控制分类筛选的第一个选项名称。", ["文章分类筛选"]),
    extraField("category_fallback_label", "text", "文章分类缺省标签", "文章没有分类时的兜底名称", "用于没有分类的文章卡片和详情页。", ["文章分类兜底"]),
    extraField("detailBackLabel", "text", "文章详情返回按钮", "文章详情页顶部返回按钮", "控制文章详情页左上角返回按钮文案。", ["文章详情页顶部返回按钮"]),
    extraField("detailListLabel", "text", "文章详情「返回列表」按钮", "文章详情空状态按钮", "文章不存在时的返回列表按钮文案。", ["文章详情空状态按钮"]),
    extraField("detailMissingTitle", "text", "文章详情不存在标题", "文章详情空状态标题", "找不到文章时显示。", ["文章详情空状态标题"]),
    extraField("detailMissingDescription", "textarea", "文章详情不存在说明", "文章详情空状态说明", "找不到文章时的补充说明。", ["文章详情空状态说明"]),
    extraField("detailEndLabel", "text", "文章详情结尾文案", "文章正文结束后的短句", "显示在文章正文底部。", ["文章详情正文结尾"]),
  ],
  diary: [
    TITLE_FIELD,
    SUBTITLE_FIELD,
    EYEBROW_FIELD,
    META_DESCRIPTION_FIELD,
    SEARCH_PLACEHOLDER_FIELD,
    EMPTY_MESSAGE_FIELD,
    WIDTH_FIELD,
    PAGE_SIZE_FIELD,
    extraField("errorTitle", "text", "日记页加载失败标题", "日记列表错误标题", "日记列表加载失败时显示。", ["日记列表错误标题", "日记详情错误标题"]),
    extraField("retryLabel", "text", "日记页重试按钮", "日记错误状态按钮文案", "用于日记列表和日记详情错误状态。", ["日记列表错误按钮", "日记详情错误按钮"]),
    extraField("loadMoreLabel", "text", "日记页加载更多文案", "日记列表加载更多提示", "列表继续加载时显示。", ["日记列表底部加载提示"]),
    extraField("detailCtaLabel", "text", "日记卡片「查看详情」按钮", "日记卡片跳转按钮文案", "用于日记列表卡片。", ["日记列表卡片按钮"]),
    extraField("detailBackLabel", "text", "日记详情返回按钮", "日记详情页顶部返回按钮", "控制日记详情页左上角返回按钮文案。", ["日记详情页顶部返回按钮"]),
    extraField("detailListLabel", "text", "日记详情「返回列表」按钮", "日记详情空状态按钮", "找不到日记时的返回列表按钮文案。", ["日记详情空状态按钮"]),
    extraField("detailMissingTitle", "text", "日记详情不存在标题", "日记详情空状态标题", "找不到日记时显示。", ["日记详情空状态标题"]),
    extraField("detailMissingDescription", "textarea", "日记详情不存在说明", "日记详情空状态说明", "找不到日记时的补充说明。", ["日记详情空状态说明"]),
    extraField("detailEndLabel", "text", "日记详情结尾文案", "日记正文结束后的短句", "显示在日记正文底部。", ["日记详情正文结尾"]),
  ],
  friends: [
    TITLE_FIELD,
    SUBTITLE_FIELD,
    EYEBROW_FIELD,
    META_DESCRIPTION_FIELD,
    EMPTY_MESSAGE_FIELD,
    WIDTH_FIELD,
    PAGE_SIZE_FIELD,
    extraField("errorTitle", "text", "友链页加载失败标题", "友链页错误标题", "友链页面加载失败时显示。", ["友链页错误标题"]),
    extraField("circle_title", "text", "友链动态区标题", "Friend Circle 区域标题", "控制友链动态区域标题。", ["友链动态区标题"]),
    extraField("loadingLabel", "text", "友链页加载中文案", "友链页加载状态文案", "用于友链动态加载中的提示。", ["友链页加载状态"]),
    extraField("loadMoreLabel", "text", "友链页加载更多按钮", "友链页继续加载按钮文案", "还有更多动态时显示。", ["友链页底部按钮"]),
    extraField("retryLabel", "text", "友链页重试按钮", "友链页错误状态按钮", "友链页加载失败时显示。", ["友链页错误按钮"]),
    extraField("refreshLabel", "text", "友链页刷新按钮", "友链动态区刷新按钮文案", "用于刷新友链动态。", ["友链页刷新按钮"]),
    extraField("refreshAriaLabel", "text", "友链页刷新按钮辅助文案", "友链刷新按钮辅助说明", "用于 aria-label 和鼠标悬停提示。", ["友链页刷新按钮辅助文案"]),
    extraField("randomPickerLabel", "text", "友链随机推荐说明", "随机推荐区域说明模板", "支持 `{days}` 占位符。", ["友链随机推荐说明"], "从最近 {days} 天里随机挑一篇"),
    extraField("randomRefreshLabel", "text", "友链随机推荐刷新按钮", "随机推荐区域按钮文案", "点击后重新抽取一篇文章。", ["友链随机推荐按钮"]),
    extraField("randomEmptyTemplate", "text", "友链随机推荐空状态模板", "随机推荐为空时的提示模板", "支持 `{days}` 占位符。", ["友链随机推荐空状态"], "最近 {days} 天还没有可展示的友链文章"),
    extraField("summaryTemplate", "text", "友链动态区摘要模板", "友链动态区统计文案模板", "支持 `{sites}` 和 `{articles}` 占位符。", ["友链动态区摘要"], "{sites} 个站点 · 共 {articles} 条动态"),
    extraField("footerSummaryTemplate", "text", "友链页底部摘要模板", "友链页底部总结文案模板", "支持 `{sites}` 和 `{articles}` 占位符。", ["友链页底部总结"], "已连接 {sites} 个站点，最近抓取 {articles} 条公开动态"),
  ],
  excerpts: [
    TITLE_FIELD,
    SUBTITLE_FIELD,
    EYEBROW_FIELD,
    META_DESCRIPTION_FIELD,
    SEARCH_PLACEHOLDER_FIELD,
    EMPTY_MESSAGE_FIELD,
    WIDTH_FIELD,
    PAGE_SIZE_FIELD,
    extraField("errorTitle", "text", "文摘页加载失败标题", "文摘列表错误标题", "文摘页加载失败时显示。", ["文摘页错误标题"]),
    extraField("retryLabel", "text", "文摘页重试按钮", "文摘页错误状态按钮", "文摘页加载失败时显示。", ["文摘页错误按钮"]),
    extraField("loadMoreLabel", "text", "文摘页加载更多文案", "文摘列表加载更多提示", "列表继续加载时显示。", ["文摘页底部加载提示"]),
    extraField("modalCloseLabel", "text", "文摘弹窗关闭提示", "文摘弹窗关闭按钮辅助文案", "用于关闭按钮的 aria-label。", ["文摘详情弹窗关闭按钮"]),
    extraField("commentsOpenLabel", "text", "文摘弹窗「查看评论」按钮", "文摘弹窗评论展开按钮文案", "会自动拼接评论数量。", ["文摘详情弹窗评论按钮"]),
    extraField("commentsCloseLabel", "text", "文摘弹窗「收起评论」按钮", "文摘弹窗评论收起按钮文案", "评论区已展开时显示。", ["文摘详情弹窗评论按钮"]),
  ],
  thoughts: [
    TITLE_FIELD,
    SUBTITLE_FIELD,
    EYEBROW_FIELD,
    META_DESCRIPTION_FIELD,
    SEARCH_PLACEHOLDER_FIELD,
    EMPTY_MESSAGE_FIELD,
    WIDTH_FIELD,
    PAGE_SIZE_FIELD,
    extraField("errorTitle", "text", "碎碎念页加载失败标题", "碎碎念列表错误标题", "碎碎念页加载失败时显示。", ["碎碎念页错误标题"]),
    extraField("retryLabel", "text", "碎碎念页重试按钮", "碎碎念页错误状态按钮", "碎碎念页加载失败时显示。", ["碎碎念页错误按钮"]),
    extraField("loadMoreLabel", "text", "碎碎念页加载更多文案", "碎碎念列表加载更多提示", "列表继续加载时显示。", ["碎碎念页底部加载提示"]),
  ],
  guestbook: [
    TITLE_FIELD,
    SUBTITLE_FIELD,
    EYEBROW_FIELD,
    META_DESCRIPTION_FIELD,
    EMPTY_MESSAGE_FIELD,
    WIDTH_FIELD,
    extraField("contentPlaceholder", "text", "留言板正文占位词", "留言输入框 placeholder", "直接影响留言正文输入框提示。", ["留言输入框 placeholder"]),
    extraField("submitLabel", "text", "留言板提交按钮", "留言提交按钮文案", "直接影响留言提交按钮文本。", ["留言提交按钮"]),
    extraField("submittingLabel", "text", "留言板提交中按钮文案", "留言提交中的按钮文案", "留言提交进行中时显示。", ["留言提交中状态"]),
    extraField("loadingLabel", "text", "留言板加载中文案", "留言列表加载中的提示", "留言板列表还在加载时显示。", ["留言列表加载状态"]),
    extraField("retryLabel", "text", "留言板重试按钮", "留言板错误状态按钮", "留言板加载失败时显示。", ["留言板错误按钮"]),
  ],
  calendar: [
    TITLE_FIELD,
    SUBTITLE_FIELD,
    EYEBROW_FIELD,
    META_DESCRIPTION_FIELD,
    EMPTY_MESSAGE_FIELD,
    WIDTH_FIELD,
    extraField("loadingLabel", "text", "日历加载中文案", "日历页加载中的提示", "日历页面还在加载时显示。", ["日历页加载状态"]),
    extraField("retryLabel", "text", "日历重试按钮", "日历页错误状态按钮", "日历页加载失败时显示。", ["日历页错误按钮"]),
    extraField("todayLabel", "text", "日历「今日」标签", "日历侧栏默认标题", "未选中具体日期时显示。", ["日历页侧栏标题"]),
    extraField("errorTitle", "text", "日历加载失败标题", "日历页错误标题", "日历页加载失败时显示。", ["日历页错误标题"]),
    extraField("selectedEmptyMessage", "textarea", "日历日期无记录文案", "某一天没有内容时的提示", "选中某一天但没有内容时显示。", ["日历页日期空状态"]),
    extraField("postTypeLabel", "text", "日历「帖子」类型标签", "日历事件类型名称", "用于图例和事件卡片。", ["日历页类型标签"]),
    extraField("diaryTypeLabel", "text", "日历「日记」类型标签", "日历事件类型名称", "用于图例和事件卡片。", ["日历页类型标签"]),
    extraField("excerptTypeLabel", "text", "日历「文摘」类型标签", "日历事件类型名称", "用于图例和事件卡片。", ["日历页类型标签"]),
    extraField("weekdayLabels", "list", "星期标签列表", "日历顶栏的星期标题", "用换行或英文逗号分隔，顺序为周一到周日。", ["日历页星期表头"], "周一\n周二\n周三\n周四\n周五\n周六\n周日"),
    extraField("monthLabels", "list", "月份标签列表", "日历页的 12 个月份标题", "用换行或英文逗号分隔，顺序为 1 月到 12 月。", ["日历页月份标题"], "1月\n2月\n3月\n4月\n5月\n6月\n7月\n8月\n9月\n10月\n11月\n12月"),
  ],
};

const PAGE_PRIMARY_KEYS: Record<string, string[]> = {
  activity: [
    "title",
    "dashboardLabel",
    "friendCircleTitle",
    "recentActivityTitle",
    "heatmapTitle",
  ],
  notFound: [
    "title",
    "subtitle",
    "badgeLabel",
    "homeLabel",
    "backLabel",
  ],
  posts: [
    "title",
    "subtitle",
    "eyebrow",
    "search_placeholder",
    "empty_message",
    "max_width",
  ],
  diary: [
    "title",
    "subtitle",
    "eyebrow",
    "search_placeholder",
    "empty_message",
    "max_width",
  ],
  friends: [
    "title",
    "subtitle",
    "eyebrow",
    "empty_message",
    "circle_title",
    "max_width",
  ],
  excerpts: [
    "title",
    "subtitle",
    "eyebrow",
    "search_placeholder",
    "empty_message",
    "max_width",
  ],
  thoughts: [
    "title",
    "subtitle",
    "eyebrow",
    "search_placeholder",
    "empty_message",
    "max_width",
  ],
  guestbook: [
    "title",
    "subtitle",
    "eyebrow",
    "empty_message",
    "contentPlaceholder",
    "submitLabel",
    "max_width",
  ],
  calendar: [
    "title",
    "subtitle",
    "eyebrow",
    "empty_message",
    "todayLabel",
    "max_width",
  ],
};

export const getFieldsForPage = (pageKey: string): PageFieldDefinition[] =>
  PAGE_FIELDS[pageKey] ?? [];

export const getPrimaryFieldsForPage = (pageKey: string): PageFieldDefinition[] => {
  const fields = getFieldsForPage(pageKey);
  const primaryKeys = new Set(PAGE_PRIMARY_KEYS[pageKey] ?? []);
  return fields.filter((field) => primaryKeys.has(field.key));
};

export const getAdvancedFieldsForPage = (pageKey: string): PageFieldDefinition[] => {
  const fields = getFieldsForPage(pageKey);
  const primaryKeys = new Set(PAGE_PRIMARY_KEYS[pageKey] ?? []);
  return fields.filter((field) => !primaryKeys.has(field.key));
};
