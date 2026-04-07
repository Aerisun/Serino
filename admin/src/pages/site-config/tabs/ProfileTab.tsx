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
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { toast } from "sonner";
import type { SiteProfileAdminRead } from "@serino/api-client/models";

type ProfileFieldKey =
  | "name"
  | "title"
  | "role"
  | "bio"
  | "filing_info"
  | "hero_image_url"
  | "hero_poster_url"
  | "hero_video_url"
  | "og_image"
  | "site_icon_url";

type FieldHelpCopy = {
  label: string;
  title: string;
  description: string;
  usageTitle: string;
  usageItems: string[];
  placeholder?: string;
  note?: string;
};

type ProfileFormState = Record<ProfileFieldKey, string>;

const PROFILE_FORM_FIELDS = [
  "name",
  "title",
  "role",
  "bio",
  "filing_info",
  "hero_image_url",
  "hero_poster_url",
  "hero_video_url",
  "og_image",
  "site_icon_url",
] as const satisfies readonly ProfileFieldKey[];

function createProfileForm(profile?: SiteProfileAdminRead | null): ProfileFormState {
  return {
    name: profile?.name ?? "",
    title: profile?.title ?? "",
    bio: profile?.bio ?? "",
    role: profile?.role ?? "",
    filing_info: profile?.filing_info ?? "",
    og_image: profile?.og_image ?? "",
    site_icon_url: profile?.site_icon_url ?? "",
    hero_image_url: profile?.hero_image_url ?? "",
    hero_poster_url: profile?.hero_poster_url ?? "",
    hero_video_url: profile?.hero_video_url ?? "",
  };
}

const PROFILE_FIELD_COPY: Record<"zh" | "en", Record<ProfileFieldKey, FieldHelpCopy>> = {
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
    title: {
      label: "站点品牌标题",
      title: "更偏“这个站点叫什么”的标题字段",
      description: "适合填写品牌名、项目名或站名，比如 Aerisun。现在它会优先作为浏览器标题和分享标题使用。",
      usageTitle: "会影响这些位置",
      usageItems: [
        "浏览器标签页标题",
        "页面 SEO / 分享标题",
        "Open Graph 的 site_name",
        "部分管理员公开身份显示链路",
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
    title: {
      label: "Site Brand Title",
      title: "The field for what the site is called",
      description: "Use this for a brand, project, or site title such as Aerisun. It now drives the browser title and sharing title first.",
      usageTitle: "Used in",
      usageItems: [
        "Browser tab titles",
        "SEO and social sharing titles",
        "Open Graph site_name",
        "Some public admin identity flows",
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
  const updateField = (key: ProfileFieldKey, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
  };
  const renderHelpLabel = (key: ProfileFieldKey) => (
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
    <Card className="mt-4 max-w-2xl">
      <CardHeader className="gap-4 border-b border-border/60 pb-5 sm:flex-row sm:items-start sm:justify-between sm:space-y-0">
        <div className="space-y-1">
          <h3 className="text-lg font-semibold text-foreground">{t("siteConfig.profile")}</h3>
          <p className="text-sm text-muted-foreground">{t("siteConfig.sectionDescriptions.profile")}</p>
        </div>
        <div className="flex items-center gap-2 self-start">
          {hasChanges ? <PendingSaveBadge /> : null}
          <DirtySaveButton
            dirty={hasChanges}
            saving={save.isPending}
            onClick={() => save.mutate({ data: form })}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pt-6">
        {(["name", "title", "role"] as const).map((key) => (
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
      </CardContent>
    </Card>
  );
}
