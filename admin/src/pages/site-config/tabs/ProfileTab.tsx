import { useState, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  updateProfileApiV1AdminSiteConfigProfilePut,
  useGetProfileApiV1AdminSiteConfigProfileGet,
  useUpdateProfileApiV1AdminSiteConfigProfilePut,
  getGetProfileApiV1AdminSiteConfigProfileGetQueryKey,
} from "@serino/api-client/admin";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { ResourceUploadField } from "@/components/ResourceUploadField";
import { DirtySaveButton, PendingSaveBadge } from "@/components/ui/DirtySaveButton";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { toast } from "sonner";
import type { SiteProfileAdminRead, SiteProfileUpdate } from "@serino/api-client/models";

type BaseProfileFieldKey =
  | "name"
  | "role"
  | "bio"
  | "filing_info"
  | "hero_image_url"
  | "hero_poster_url"
  | "hero_video_url"
  | "og_image"
  | "site_icon_url";

type SearchOptimizationFieldKey =
  | "search_real_name"
  | "search_english_name"
  | "search_meta_title"
  | "search_meta_description"
  | "search_keywords"
  | "search_llm_summary"
  | "search_expertise"
  | "search_same_as"
  | "search_canonical_url";

type ProfileFieldKey = BaseProfileFieldKey | SearchOptimizationFieldKey;
type ProfileCopyFieldKey = Exclude<ProfileFieldKey, "search_english_name">;

type FieldHelpCopy = {
  label: string;
  title: string;
  description: string;
  usageTitle: string;
  usageItems: string[];
  placeholder?: string;
  note?: string;
};

export type ProfileFormState = Record<ProfileFieldKey, string>;

const SEARCH_OPTIMIZATION_FLAG_KEY = "search_optimization";

const BASE_PROFILE_FIELDS = [
  "name",
  "role",
  "bio",
  "filing_info",
  "hero_image_url",
  "hero_poster_url",
  "hero_video_url",
  "og_image",
  "site_icon_url",
] as const satisfies readonly BaseProfileFieldKey[];

const SEARCH_OPTIMIZATION_FIELDS = [
  "search_real_name",
  "search_english_name",
  "search_meta_title",
  "search_meta_description",
  "search_keywords",
  "search_llm_summary",
  "search_expertise",
  "search_same_as",
  "search_canonical_url",
] as const satisfies readonly SearchOptimizationFieldKey[];

const PROFILE_FORM_FIELDS = [
  ...BASE_PROFILE_FIELDS,
  ...SEARCH_OPTIMIZATION_FIELDS,
] as const satisfies readonly ProfileFieldKey[];

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const readText = (value: unknown): string => (typeof value === "string" ? value : "");

const readList = (value: unknown, separator: string): string => {
  if (Array.isArray(value)) {
    return value
      .filter((item): item is string => typeof item === "string")
      .map((item) => item.trim())
      .filter(Boolean)
      .join(separator);
  }
  return typeof value === "string" ? value : "";
};

const readDelimitedTextList = (value: unknown): string => readList(value, ", ");
const readLineTextList = (value: unknown): string => readList(value, "\n");

const splitDelimitedList = (value: string): string[] =>
  value
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean);

const splitLineList = (value: string): string[] =>
  value
    .split(/\n/)
    .map((item) => item.trim())
    .filter(Boolean);

const readFeatureFlags = (profile?: SiteProfileAdminRead | null): Record<string, unknown> => {
  const featureFlags = profile?.feature_flags;
  return isRecord(featureFlags) ? { ...featureFlags } : {};
};

const readSearchOptimization = (
  profile?: SiteProfileAdminRead | null,
): Record<SearchOptimizationFieldKey, string> => {
  const raw = readFeatureFlags(profile)[SEARCH_OPTIMIZATION_FLAG_KEY];
  const config = isRecord(raw) ? raw : {};
  return {
    search_real_name: readText(config.real_name),
    search_english_name: readText(config.english_name),
    search_meta_title: readText(config.meta_title),
    search_meta_description: readText(config.meta_description),
    search_keywords: readDelimitedTextList(config.keywords),
    search_llm_summary: readText(config.llm_summary),
    search_expertise: readDelimitedTextList(config.expertise),
    search_same_as: readLineTextList(config.same_as),
    search_canonical_url: readText(config.canonical_url),
  };
};

export function createProfileForm(profile?: SiteProfileAdminRead | null): ProfileFormState {
  return {
    name: profile?.name ?? "",
    bio: profile?.bio ?? "",
    role: profile?.role ?? "",
    filing_info: profile?.filing_info ?? "",
    og_image: profile?.og_image ?? "",
    site_icon_url: profile?.site_icon_url ?? "",
    hero_image_url: profile?.hero_image_url ?? "",
    hero_poster_url: profile?.hero_poster_url ?? "",
    hero_video_url: profile?.hero_video_url ?? "",
    ...readSearchOptimization(profile),
  };
}

export const serializeSearchOptimization = (form: ProfileFormState) => ({
  real_name: form.search_real_name.trim(),
  english_name: form.search_english_name.trim(),
  meta_title: form.search_meta_title.trim(),
  meta_description: form.search_meta_description.trim(),
  keywords: splitDelimitedList(form.search_keywords),
  llm_summary: form.search_llm_summary.trim(),
  expertise: splitDelimitedList(form.search_expertise),
  same_as: splitLineList(form.search_same_as),
  canonical_url: form.search_canonical_url.trim(),
});

const hasSearchOptimizationValue = (value: ReturnType<typeof serializeSearchOptimization>) =>
  Boolean(
    value.real_name ||
      value.english_name ||
      value.meta_title ||
      value.meta_description ||
      value.keywords.length ||
      value.llm_summary ||
      value.expertise.length ||
      value.same_as.length ||
      value.canonical_url,
  );

export const isCanonicalUrlValid = (value: string) => {
  const candidate = value.trim();
  if (!candidate) return true;
  if (/[\\\s]/.test(candidate)) return false;

  try {
    const parsed = new URL(candidate);
    return (
      ["http:", "https:"].includes(parsed.protocol) &&
      Boolean(parsed.hostname) &&
      !parsed.username &&
      !parsed.password &&
      (parsed.pathname === "" || parsed.pathname === "/") &&
      !parsed.search &&
      !parsed.hash
    );
  } catch {
    return false;
  }
};

const isSearchIdentityValid = (value: ReturnType<typeof serializeSearchOptimization>) =>
  !hasSearchOptimizationValue(value) || Boolean(value.real_name && value.english_name);

export const isSearchOptimizationValid = (value: ReturnType<typeof serializeSearchOptimization>) =>
  isSearchIdentityValid(value) && isCanonicalUrlValid(value.canonical_url);

export const buildSiteBrandTitle = (form: ProfileFormState) => {
  const displayName = form.name.trim();
  const realName = form.search_real_name.trim();
  const englishName = form.search_english_name.trim();
  return displayName && realName && englishName
    ? `${displayName} - ${realName}(${englishName})`
    : displayName;
};

export const hasSearchOptimizationChanges = (
  form: ProfileFormState,
  savedForm: ProfileFormState,
) => SEARCH_OPTIMIZATION_FIELDS.some((key) => form[key] !== savedForm[key]);

export const shouldBlockSearchOptimizationSave = (
  form: ProfileFormState,
  savedForm: ProfileFormState,
) =>
  hasSearchOptimizationChanges(form, savedForm) &&
  !isSearchOptimizationValid(serializeSearchOptimization(form));

export const buildProfilePayload = (
  form: ProfileFormState,
  profile?: SiteProfileAdminRead,
): SiteProfileUpdate => {
  const payload = Object.fromEntries(
    BASE_PROFILE_FIELDS.map((key) => [key, form[key]]),
  ) as SiteProfileUpdate;
  const featureFlags = readFeatureFlags(profile);
  const searchOptimization = serializeSearchOptimization(form);

  payload.title = buildSiteBrandTitle(form);

  if (hasSearchOptimizationValue(searchOptimization)) {
    featureFlags[SEARCH_OPTIMIZATION_FLAG_KEY] = searchOptimization;
  } else {
    delete featureFlags[SEARCH_OPTIMIZATION_FLAG_KEY];
  }

  payload.feature_flags = featureFlags;
  return payload;
};

const PROFILE_FIELD_COPY: Record<"zh" | "en", Record<ProfileCopyFieldKey, FieldHelpCopy>> = {
  zh: {
    name: {
      label: "主页显示名",
      title: "更偏“你是谁”的名字字段",
      description: "适合填写人物名或最常见的对外称呼，比如 Felix。它主要影响首页和页脚里直接面对访客的名字显示。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "首页 Hero 中央圆形卡片正面的名字",
        "页脚主名称",
        "图片替代文本，以及部分作者信息的兜底文案",
      ],
    },
    role: {
      label: "首页角色标签",
      title: "首页首屏顶部的小号职业说明",
      description: "这是一句较短的身份标签，建议保持在一行内，适合写职业、方向或擅长领域。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "首页 Hero 顶部的小字标签",
        "页脚名称下方的身份说明",
      ],
    },
    filing_info: {
      label: "备案信息",
      title: "页脚第一行展示的备案或登记信息",
      description: "适合填写 ICP / 公安备案 / 站点登记号等信息。会显示在页脚第一行的作者名后面。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "全站页脚第一行中的备案信息",
      ],
    },
    hero_image_url: {
      label: "Hero 翻转视觉图",
      title: "首页中央圆形卡片翻面后显示的图片",
      description: "这是首页最核心的视觉资源之一，用在 Hero 主视觉的翻转效果里。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "首页 Hero 中央圆形卡片背面",
        "管理员评论头像同步时的首选图源",
      ],
      placeholder: "上传或填写 Hero 翻转视觉图地址",
      note: "首页 Hero 翻转视觉图",
    },
    hero_poster_url: {
      label: "首页视频封面图",
      title: "背景视频开始播放前显示的静态封面",
      description: "建议使用与视频风格一致的静帧，避免首屏在慢网速下出现空白感。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "首页背景视频的 poster 封面",
        "视频加载前的首屏观感",
      ],
      placeholder: "上传或填写首页视频封面图地址",
      note: "首页 Hero 视频封面图",
    },
    hero_video_url: {
      label: "首页背景视频",
      title: "首页首屏铺满背景的视频资源",
      description: "如果填写这里，首页会优先显示视频背景；如果视频缺失或加载失败，会回退到下面的静态背景图。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "首页首屏背景媒体",
        "首页进入时的整体氛围和节奏",
      ],
      placeholder: "上传或填写首页背景视频地址",
      note: "首页 Hero 背景视频",
    },
    og_image: {
      label: "分享图 / 首页背景兜底图",
      title: "分享用图，同时也是首页背景的静态兜底",
      description: "这个字段不只是 SEO 图片。当前也会在首页背景视频不可用时作为静态背景图使用，并在 Hero 视觉图为空时参与兜底。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "Open Graph 分享图",
        "Twitter 分享图",
        "首页背景视频缺失或报错时的背景图",
        "Hero 翻转视觉图为空时的图片兜底",
      ],
      placeholder: "上传或填写分享图 / 首页背景兜底图地址",
      note: "站点分享图与首页背景兜底图",
    },
    site_icon_url: {
      label: "浏览器标签图标",
      title: "浏览器标签页左侧的小图标",
      description: "这是常说的 favicon。建议上传简洁、识别度高的小图标，优先使用正方形图形。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "浏览器标签页左侧图标",
        "书签和快捷方式图标",
        "部分浏览器的历史记录或地址栏小图标",
      ],
      placeholder: "上传或填写浏览器标签图标地址",
      note: "站点标签页图标",
    },
    bio: {
      label: "首页简介文案",
      title: "首页主视觉下方的核心介绍文字",
      description: "适合用 1 到 3 句话讲清楚你在做什么、站点想传达什么。这里是首页最主要的说明文案。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "首页 Hero 主文案",
      ],
    },
    search_real_name: {
      label: "真实姓名 *",
      title: "搜索实体使用的中英文姓名",
      description: "左侧填写中文主姓名，右侧填写英文公开姓名。搜索引擎和 AI 搜索会用它们确认两种写法属于同一个人，不会替换首页显示名。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "Person 结构化数据 name",
        "Person 结构化数据 alternateName",
        "页面 author 元信息",
        "/resume 简历 ProfilePage 的主实体",
      ],
    },
    search_meta_title: {
      label: "搜索标题",
      title: "给搜索结果和 AI 搜索引用的站点标题",
      description: "建议写成“姓名 / 品牌 + 核心身份或领域”。它用于分享标题和搜索辅助元信息，不会覆盖浏览器标签页标题。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "Open Graph / Twitter 分享标题",
        "链接分享到社交平台时的标题",
        "搜索系统可参考的首页补充标题信号",
      ],
    },
    search_meta_description: {
      label: "搜索摘要",
      title: "给搜索结果摘要的短描述",
      description: "用一两句话说明你是谁、提供什么内容、为什么值得被访问。Google 可能按查询重写摘要，但高质量描述仍能帮助理解页面。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "首页 meta description",
        "Open Graph / Twitter 摘要",
        "WebSite 结构化数据描述",
      ],
    },
    search_keywords: {
      label: "关键词",
      title: "补充主题词，给非 Google 爬虫和站内语义使用",
      description: "用逗号分隔。优先填写姓名、公开别名、学校、专业和长期内容主题；关键词应真实覆盖你的内容，不要堆砌无关热词。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "meta keywords",
        "结构化身份主题的辅助语义",
      ],
    },
    search_llm_summary: {
      label: "大模型摘要",
      title: "GEO 使用的稳定身份说明",
      description: "写给 AI 搜索和问答系统的事实型摘要。建议包含你的身份、长期方向、代表内容或项目，避免广告口吻。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "Person 结构化数据 description",
        "AI 搜索生成答案时的身份参考",
      ],
    },
    search_expertise: {
      label: "擅长领域",
      title: "帮助搜索系统识别你的专业主题",
      description: "用逗号分隔，填写你希望被关联的长期主题，比如 AI Infra、AI Agent、全栈开发或集成电路设计。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "Person 结构化数据 knowsAbout",
        "大模型检索对专业领域的聚类",
      ],
    },
    search_same_as: {
      label: "权威身份链接",
      title: "用来证明这些外部主页与你是同一个实体",
      description: "每行一个 URL，适合填写 GitHub、LinkedIn、Wikipedia、作品集、公司主页等稳定链接。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "Person 结构化数据 sameAs",
        "搜索引擎实体识别",
      ],
    },
    search_canonical_url: {
      label: "规范站点地址",
      title: "你的公开站点首选域名",
      description: "填写正式域名，例如 https://example.com。前台会按当前路径生成 canonical，避免 www、http/https 或镜像域名造成重复。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "页面 canonical 链接",
        "结构化数据 url",
      ],
    },
  },
  en: {
    name: {
      label: "Homepage Display Name",
      title: "The field for who you are",
      description: "Use this for the personal name or public-facing name people should immediately recognize, such as Felix.",
      usageTitle: "Used in",
      usageItems: [
        "The name on the front of the homepage hero coin",
        "The main name in the footer",
        "Metadata author tags and structured data fallbacks",
      ],
    },
    role: {
      label: "Hero Role Label",
      title: "The short profession line above the hero",
      description: "Keep this short. It works best as a one-line role, discipline, or focus statement.",
      usageTitle: "Used in",
      usageItems: [
        "The small label above the homepage hero",
        "The role line under the name in the footer",
      ],
    },
    filing_info: {
      label: "Filing Info",
      title: "The filing or regulatory line shown in the first footer row",
      description: "Use this for ICP, registration, or filing text that should appear after the site owner name in the footer.",
      usageTitle: "Used in",
      usageItems: [
        "The filing segment in the first footer row",
      ],
    },
    hero_image_url: {
      label: "Hero Flip Image",
      title: "The image shown on the back of the hero coin",
      description: "This is one of the main visual assets for the homepage hero interaction.",
      usageTitle: "Used in",
      usageItems: [
        "The back side of the homepage hero coin",
        "The preferred image source for synced admin comment avatars",
      ],
      placeholder: "Upload or paste the hero flip image URL",
      note: "Homepage hero flip image",
    },
    hero_poster_url: {
      label: "Homepage Video Poster",
      title: "The still image shown before the background video plays",
      description: "Use a frame that matches the mood of the video so the hero feels stable on slower connections.",
      usageTitle: "Used in",
      usageItems: [
        "The homepage background video poster",
        "The first visual state before the video starts",
      ],
      placeholder: "Upload or paste the homepage video poster URL",
      note: "Homepage hero video poster",
    },
    hero_video_url: {
      label: "Homepage Background Video",
      title: "The full-bleed video asset for the homepage hero",
      description: "If set, the homepage uses this video first. If it is missing or fails, the fallback background image below is used instead.",
      usageTitle: "Used in",
      usageItems: [
        "The homepage hero background",
        "The overall opening atmosphere of the site",
      ],
      placeholder: "Upload or paste the homepage background video URL",
      note: "Homepage hero background video",
    },
    og_image: {
      label: "Share Image / Background Fallback",
      title: "The sharing image and static hero fallback",
      description: "This is not only for SEO. It also becomes the homepage fallback background when the hero video is unavailable, and it can back up the hero image when needed.",
      usageTitle: "Used in",
      usageItems: [
        "Open Graph share image",
        "Twitter share image",
        "Homepage background when the hero video is missing or fails",
        "Hero image fallback when the flip image is empty",
      ],
      placeholder: "Upload or paste the share image / fallback background URL",
      note: "Site share image and homepage fallback background",
    },
    site_icon_url: {
      label: "Browser Tab Icon",
      title: "The small icon shown to the left of the browser tab title",
      description: "This is the favicon. Use a simple square graphic that still reads well at very small sizes.",
      usageTitle: "Used in",
      usageItems: [
        "Browser tabs",
        "Bookmarks and shortcuts",
        "Some browser history and address-bar icon surfaces",
      ],
      placeholder: "Upload or paste the browser tab icon URL",
      note: "Site tab icon",
    },
    bio: {
      label: "Homepage Intro Copy",
      title: "The main descriptive copy under the hero",
      description: "Use one to three sentences to explain who you are, what you make, and what this site feels like.",
      usageTitle: "Used in",
      usageItems: [
        "The main copy block in the homepage hero",
      ],
    },
    search_real_name: {
      label: "Real Names *",
      title: "Chinese and English names used for search identity",
      description: "Enter the primary Chinese name on the left and the public English name on the right. Search engines and AI search use both to identify the same person without replacing the homepage display name.",
      usageTitle: "Used in",
      usageItems: [
        "Person structured data name",
        "Person structured data alternateName",
        "Page author metadata",
        "The main entity of the /resume ProfilePage",
      ],
    },
    search_meta_title: {
      label: "Search Title",
      title: "The site title for search results and AI search references",
      description: "Use a concise name or brand plus your primary identity or field. It is used for sharing and search-assist metadata, and it does not override the browser tab title.",
      usageTitle: "Used in",
      usageItems: [
        "Open Graph and Twitter sharing titles",
        "The title shown when the homepage is shared",
        "A supplemental homepage title signal for search systems",
      ],
    },
    search_meta_description: {
      label: "Search Summary",
      title: "A short description for search snippets",
      description: "Explain who you are, what visitors can find here, and why the page is useful. Search engines may rewrite snippets, but accurate descriptions still help page understanding.",
      usageTitle: "Used in",
      usageItems: [
        "Homepage meta description",
        "Open Graph and Twitter summaries",
        "WebSite structured data description",
      ],
    },
    search_keywords: {
      label: "Keywords",
      title: "Supplemental topic terms for non-Google crawlers and semantics",
      description: "Separate terms with commas. Prioritize your names, public aliases, school, major, and durable content topics instead of unrelated trending words.",
      usageTitle: "Used in",
      usageItems: [
        "meta keywords",
        "Supporting structured identity semantics",
      ],
    },
    search_llm_summary: {
      label: "AI Search Summary",
      title: "A stable factual identity summary for GEO",
      description: "Write for AI search and answer engines. Include your identity, long-term focus, representative content, or projects without turning it into ad copy.",
      usageTitle: "Used in",
      usageItems: [
        "Person structured data description",
        "Identity context for AI-generated search answers",
      ],
    },
    search_expertise: {
      label: "Expertise Topics",
      title: "The durable topics you want associated with your identity",
      description: "Separate topics with commas, such as AI Infrastructure, AI Agents, full-stack development, or IC design.",
      usageTitle: "Used in",
      usageItems: [
        "Person structured data knowsAbout",
        "Topic clustering for AI retrieval systems",
      ],
    },
    search_same_as: {
      label: "Identity Links",
      title: "Authoritative external pages that identify the same person or brand",
      description: "Enter one URL per line. Good candidates include GitHub, LinkedIn, Wikipedia, portfolio, company, or other stable public profiles.",
      usageTitle: "Used in",
      usageItems: [
        "Person structured data sameAs",
        "Search entity disambiguation",
      ],
    },
    search_canonical_url: {
      label: "Canonical Site URL",
      title: "The preferred public domain for this site",
      description: "Use the official origin, such as https://example.com. The frontend combines it with the current path to avoid duplicate www, http/https, or mirror-domain URLs.",
      usageTitle: "Used in",
      usageItems: [
        "Canonical page links",
        "Structured data URLs",
      ],
    },
  },
};

export function ProfileTab() {
  const { lang, t } = useI18n();
  const queryClient = useQueryClient();
  const { data: raw, isLoading } =
    useGetProfileApiV1AdminSiteConfigProfileGet();
  const profile = raw?.data as SiteProfileAdminRead | undefined;
  const [form, setForm] = useState<ProfileFormState>(createProfileForm());
  const [savedForm, setSavedForm] = useState<ProfileFormState | null>(null);

  useEffect(() => {
    if (profile && !savedForm) {
      const nextForm = createProfileForm(profile);
      setForm(nextForm);
      setSavedForm(nextForm);
    }
  }, [profile, savedForm]);

  const save = useUpdateProfileApiV1AdminSiteConfigProfilePut({
    mutation: {
      onSuccess: (response) => {
        const nextProfile = response.data as SiteProfileAdminRead | undefined;
        const nextForm = nextProfile ? createProfileForm(nextProfile) : form;
        setForm(nextForm);
        setSavedForm(nextForm);
        queryClient.invalidateQueries({
          queryKey: getGetProfileApiV1AdminSiteConfigProfileGetQueryKey(),
        });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });
  const persistUploadedField = useUpdateProfileApiV1AdminSiteConfigProfilePut();

  if (isLoading && !savedForm)
    return <p className="py-4 text-muted-foreground">{t("common.loading")}</p>;

  const copy = PROFILE_FIELD_COPY[lang];
  const effectiveSavedForm = savedForm ?? createProfileForm(profile);
  const hasChanges = PROFILE_FORM_FIELDS.some((key) => form[key] !== effectiveSavedForm[key]);
  const currentSearchOptimization = serializeSearchOptimization(form);
  const searchOptimizationChanged = hasSearchOptimizationChanges(form, effectiveSavedForm);
  const showSearchIdentityError =
    searchOptimizationChanged &&
    hasSearchOptimizationValue(currentSearchOptimization) &&
    !isSearchIdentityValid(currentSearchOptimization);
  const showCanonicalUrlError =
    searchOptimizationChanged &&
    !isCanonicalUrlValid(currentSearchOptimization.canonical_url);
  const updateField = (key: ProfileFieldKey, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
  };
  const handleSave = () => {
    if (shouldBlockSearchOptimizationSave(form, effectiveSavedForm)) {
      toast.error(
        showCanonicalUrlError
          ? lang === "zh"
            ? "规范网址必须是完整的 HTTP(S) 站点根地址，且不能包含路径、查询参数或片段。"
            : "The canonical URL must be an HTTP(S) site origin without a path, query, or fragment."
          : lang === "zh"
            ? "请同时填写中文名和英文名，再保存搜索优化配置。"
            : "Enter both the Chinese and English names before saving search optimization settings.",
      );
      return;
    }
    save.mutate({ data: buildProfilePayload(form, profile) });
  };
  const renderHelpLabel = (key: ProfileCopyFieldKey) => (
    <LabelWithHelp
      label={copy[key].label}
      title={copy[key].title}
      description={copy[key].description}
      usageTitle={copy[key].usageTitle}
      usageItems={copy[key].usageItems}
    />
  );
  const autoSaveUploadedField = async (
    key: Extract<
      ProfileFieldKey,
      "hero_image_url" | "hero_poster_url" | "hero_video_url" | "og_image" | "site_icon_url"
    >,
    value: string,
  ) => {
    try {
      const response = await persistUploadedField.mutateAsync({
        data: { [key]: value } as Parameters<typeof updateProfileApiV1AdminSiteConfigProfilePut>[0],
      });
      const nextProfile = response.data as SiteProfileAdminRead | undefined;
      const nextSavedForm = nextProfile ? createProfileForm(nextProfile) : effectiveSavedForm;
      setSavedForm(nextSavedForm);
      setForm((current) => ({
        ...current,
        [key]: nextSavedForm[key],
      }));
      queryClient.invalidateQueries({
        queryKey: getGetProfileApiV1AdminSiteConfigProfileGetQueryKey(),
      });
    } catch (error) {
      throw new Error(extractApiErrorMessage(error, t("common.operationFailed")));
    }
  };

  return (
    <Card className="site-config-profile-card mt-4 max-w-2xl overflow-visible rounded-[1.35rem] sm:overflow-hidden sm:rounded-[var(--admin-radius-lg)]">
      <CardHeader className="gap-2 border-b border-border/60 px-4 pb-3 pt-4 sm:gap-3 sm:px-6 sm:pb-5 sm:pt-6">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <h3 className="truncate text-lg font-semibold text-foreground">{t("siteConfig.profile")}</h3>
            <p className="hidden text-sm text-muted-foreground sm:block">{t("siteConfig.sectionDescriptions.profile")}</p>
          </div>
          <div className="flex shrink-0 items-center justify-end gap-2">
            {hasChanges ? <PendingSaveBadge /> : null}
            <DirtySaveButton
              dirty={hasChanges}
              saving={save.isPending}
              onClick={handleSave}
            />
          </div>
        </div>
        <p className="text-sm leading-5 text-muted-foreground sm:hidden">{t("siteConfig.sectionDescriptions.profile")}</p>
      </CardHeader>
      <CardContent className="space-y-4 px-4 pt-3 sm:px-6 sm:pt-6">
        {(["name", "role"] as const).map((key) => (
          <div key={key} className="space-y-2">
            {renderHelpLabel(key)}
            <Input
              value={form[key]}
              onChange={(e) => updateField(key, e.target.value)}
            />
          </div>
        ))}
        <div className="space-y-2">
          {renderHelpLabel("bio")}
          <Textarea
            value={form.bio}
            onChange={(e) => updateField("bio", e.target.value)}
            rows={4}
          />
        </div>
        <div className="space-y-2">
          {renderHelpLabel("filing_info")}
          <Input
            value={form.filing_info}
            onChange={(e) => updateField("filing_info", e.target.value)}
          />
        </div>
        <ResourceUploadField
          label={renderHelpLabel("hero_image_url")}
          value={form.hero_image_url}
          category="hero-image"
          accept="image/*"
          placeholder={copy.hero_image_url.placeholder}
          note={copy.hero_image_url.note}
          uniqueByCategory
          onChange={(value) => updateField("hero_image_url", value)}
          onUploadPersist={(value) => autoSaveUploadedField("hero_image_url", value)}
        />
        <ResourceUploadField
          label={renderHelpLabel("hero_poster_url")}
          value={form.hero_poster_url}
          category="hero-poster"
          accept="image/*"
          placeholder={copy.hero_poster_url.placeholder}
          note={copy.hero_poster_url.note}
          uniqueByCategory
          onChange={(value) => updateField("hero_poster_url", value)}
          onUploadPersist={(value) => autoSaveUploadedField("hero_poster_url", value)}
        />
        <ResourceUploadField
          label={renderHelpLabel("hero_video_url")}
          value={form.hero_video_url}
          category="hero-video"
          accept="image/*,video/*"
          placeholder={copy.hero_video_url.placeholder}
          note={copy.hero_video_url.note}
          uniqueByCategory
          onChange={(value) => updateField("hero_video_url", value)}
          onUploadPersist={(value) => autoSaveUploadedField("hero_video_url", value)}
        />
        <ResourceUploadField
          label={renderHelpLabel("og_image")}
          value={form.og_image}
          category="site-og"
          accept="image/*"
          placeholder={copy.og_image.placeholder}
          note={copy.og_image.note}
          uniqueByCategory
          onChange={(value) => updateField("og_image", value)}
          onUploadPersist={(value) => autoSaveUploadedField("og_image", value)}
        />
        <ResourceUploadField
          label={renderHelpLabel("site_icon_url")}
          value={form.site_icon_url}
          category="site-icon"
          accept="image/*,.ico"
          placeholder={copy.site_icon_url.placeholder}
          note={copy.site_icon_url.note}
          uniqueByCategory
          onChange={(value) => updateField("site_icon_url", value)}
          onUploadPersist={(value) => autoSaveUploadedField("site_icon_url", value)}
        />
        <CollapsibleSection
          title={lang === "zh" ? "搜索优化" : "Search Optimization"}
          badge="SEO / GEO"
          className="overflow-visible border border-border/60 bg-background/35"
        >
          <div className="space-y-4 pt-1">
            <div className="space-y-2">
              {renderHelpLabel("search_real_name")}
              <div
                className={`grid min-h-[2.75rem] grid-cols-2 divide-x divide-border/60 overflow-hidden rounded-[var(--admin-radius-md)] admin-glass-input ring-offset-background transition-[border,box-shadow] focus-within:outline-none focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 ${
                  showSearchIdentityError ? "!border-destructive focus-within:ring-destructive/30" : ""
                }`}
              >
                <input
                  value={form.search_real_name}
                  onChange={(e) => updateField("search_real_name", e.target.value)}
                  aria-label={lang === "zh" ? "中文名" : "Chinese name"}
                  aria-invalid={showSearchIdentityError}
                  aria-describedby={showSearchIdentityError ? "search-identity-error" : undefined}
                  placeholder={lang === "zh" ? "中文名" : "Chinese name"}
                  autoComplete="name"
                  className="min-w-0 bg-transparent px-3 py-2 text-sm text-foreground outline-none placeholder:text-muted-foreground/90"
                  required
                />
                <input
                  value={form.search_english_name}
                  onChange={(e) => updateField("search_english_name", e.target.value)}
                  aria-label={lang === "zh" ? "英文名" : "English name"}
                  aria-invalid={showSearchIdentityError}
                  aria-describedby={showSearchIdentityError ? "search-identity-error" : undefined}
                  placeholder="English name"
                  autoComplete="name"
                  className="min-w-0 bg-transparent px-3 py-2 text-sm text-foreground outline-none placeholder:text-muted-foreground/90"
                  required
                />
              </div>
              {showSearchIdentityError ? (
                <p id="search-identity-error" className="text-xs leading-5 text-destructive">
                  {lang === "zh"
                    ? "请同时填写中文名和英文名，再保存搜索优化配置。"
                    : "Enter both the Chinese and English names before saving search optimization settings."}
                </p>
              ) : null}
            </div>
            <div className="space-y-2">
              {renderHelpLabel("search_meta_title")}
              <Input
                value={form.search_meta_title}
                onChange={(e) => updateField("search_meta_title", e.target.value)}
                placeholder={lang === "zh" ? "例如：Rowan - 前端与 AI 自动化" : "Example: Rowan - Frontend and AI Automation"}
              />
            </div>
            <div className="space-y-2">
              {renderHelpLabel("search_meta_description")}
              <Textarea
                value={form.search_meta_description}
                onChange={(e) => updateField("search_meta_description", e.target.value)}
                rows={3}
                placeholder={
                  lang === "zh"
                    ? "用一两句话说明你是谁、这里有什么内容、适合谁访问。"
                    : "Explain who you are, what this site contains, and who it helps."
                }
              />
            </div>
            <div className="space-y-2">
              {renderHelpLabel("search_keywords")}
              <Input
                value={form.search_keywords}
                onChange={(e) => updateField("search_keywords", e.target.value)}
                placeholder={
                  lang === "zh"
                    ? "杨汶帛, Wenbo Yang, Aerisun, 北京大学, 集成电路, 人工智能"
                    : "Wenbo Yang, Aerisun, Peking University, AI Infrastructure"
                }
              />
            </div>
            <div className="space-y-2">
              {renderHelpLabel("search_llm_summary")}
              <Textarea
                value={form.search_llm_summary}
                onChange={(e) => updateField("search_llm_summary", e.target.value)}
                rows={4}
                placeholder={
                  lang === "zh"
                    ? "事实型描述你的身份、长期方向、代表项目或内容。"
                    : "Describe your identity, durable focus, representative projects, or content."
                }
              />
            </div>
            <div className="space-y-2">
              {renderHelpLabel("search_expertise")}
              <Input
                value={form.search_expertise}
                onChange={(e) => updateField("search_expertise", e.target.value)}
                placeholder={
                  lang === "zh"
                    ? "AI Infra, AI Agent, 全栈开发, 集成电路设计"
                    : "AI Infrastructure, AI Agents, Full-stack Development, IC Design"
                }
              />
            </div>
            <div className="space-y-2">
              {renderHelpLabel("search_same_as")}
              <Textarea
                value={form.search_same_as}
                onChange={(e) => updateField("search_same_as", e.target.value)}
                rows={3}
                placeholder={"https://github.com/your-name\nhttps://www.linkedin.com/in/your-name"}
              />
            </div>
            <div className="space-y-2">
              {renderHelpLabel("search_canonical_url")}
              <Input
                type="url"
                value={form.search_canonical_url}
                onChange={(e) => updateField("search_canonical_url", e.target.value)}
                placeholder="https://example.com"
                aria-invalid={showCanonicalUrlError}
                aria-describedby={showCanonicalUrlError ? "search-canonical-url-error" : undefined}
              />
              {showCanonicalUrlError ? (
                <p id="search-canonical-url-error" className="text-xs leading-5 text-destructive">
                  {lang === "zh"
                    ? "请输入完整的 HTTP(S) 站点根地址，不要包含路径、?query 或 #fragment。"
                    : "Enter an HTTP(S) site origin without a path, ?query, or #fragment."}
                </p>
              ) : null}
            </div>
          </div>
        </CollapsibleSection>
      </CardContent>
    </Card>
  );
}
