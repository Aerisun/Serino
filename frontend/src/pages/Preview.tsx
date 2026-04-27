import { Suspense, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "motion/react";
import {
  Clock,
  Eye,
  MessageCircle,
  Tag,
  Cloud,
  CloudDrizzle,
  CloudFog,
  CloudHail,
  CloudLightning,
  CloudRain,
  CloudRainWind,
  CloudSnow,
  CloudSunRain,
  Haze,
  Snowflake,
  Sun,
  Wind,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import FallingPetals from "@/components/FallingPetals";
import BackToTop from "@/components/BackToTop";
import DecorativeVineLine from "@/components/DecorativeVineLine";
import PageShell from "@/components/PageShell";
import TableOfContents from "@/components/TableOfContents";
import { useFeatureFlags, usePageConfig } from "@/contexts/runtime-config";
import { useFrontendI18n, type FrontendLang } from "@/i18n";
import EmbeddedResume from "@/components/EmbeddedResume";
import PreviewModeBadge from "@/components/PreviewModeBadge";
import { lazyWithPreload } from "@/lib/lazy";
import { usePreviewChannel, type ContentPreviewData } from "@/lib/preview";
import { formatDateInBeijing } from "@/lib/time";

const ArticleMarkdownRenderer = lazyWithPreload(() => import("@/components/ArticleMarkdownRenderer"));

const estimateReadTime = (value: string, lang: FrontendLang, minuteLabel: string) =>
  `${Math.max(1, Math.ceil(value.length / 180)).toLocaleString(lang === "zh" ? "zh-CN" : "en-US")} ${minuteLabel}`;

const weatherIcons: Record<string, typeof Sun> = {
  sunny: Sun,
  cloudy: Cloud,
  fog: CloudFog,
  haze: Haze,
  light_rain: CloudDrizzle,
  shower: CloudSunRain,
  rainy: CloudRain,
  heavy_rain: CloudRainWind,
  light_snow: CloudSnow,
  snowy: CloudSnow,
  heavy_snow: Snowflake,
  sleet: CloudHail,
  stormy: CloudLightning,
  windy: Wind,
};

const weatherLabelKeys: Record<string, string> = {
  sunny: "diary.weather.sunny",
  cloudy: "diary.weather.cloudy",
  fog: "diary.weather.fog",
  haze: "diary.weather.haze",
  light_rain: "diary.weather.lightRain",
  shower: "diary.weather.shower",
  rainy: "diary.weather.rainy",
  heavy_rain: "diary.weather.heavyRain",
  light_snow: "diary.weather.lightSnow",
  snowy: "diary.weather.snowy",
  heavy_snow: "diary.weather.heavySnow",
  sleet: "diary.weather.sleet",
  stormy: "diary.weather.stormy",
  windy: "diary.weather.windy",
};

const formatEnglishHeaderDate = (
  value: string | null | undefined,
  t: (key: string, values?: Record<string, string | number>, fallback?: string) => string,
) => {
  return value
    ? formatDateInBeijing(value, "en-US", {
        weekday: "short",
        month: "long",
        day: "numeric",
        year: "numeric",
      })
    : t("common.draft");
};

function PostPreview({ data }: { data: ContentPreviewData }) {
  const { t, lang } = useFrontendI18n();
  const featureFlags = useFeatureFlags();
  const pages = usePageConfig();
  const postsConfig = (pages.posts ?? {}) as {
    categories?: { fallback?: string };
  };
  const fallbackCategoryLabel = postsConfig.categories?.fallback ?? t("posts.fallbackCategory");
  const articleRef = useRef<HTMLElement>(null);

  useEffect(() => {
    void ArticleMarkdownRenderer.preload();
  }, []);

  const category = data.category || fallbackCategoryLabel;
  const readTime = estimateReadTime(data.body || "", lang, t("common.minutes"));

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="mb-4 flex flex-wrap items-center gap-3 text-xs font-body text-foreground/25">
          <span>
            {data.published_at
              ? formatDateInBeijing(
                  data.published_at,
                  lang === "zh" ? "zh-CN" : "en-US",
                  { year: "numeric", month: "2-digit", day: "2-digit" },
                )
              : t("common.draft")}
          </span>
          <span className="rounded-md border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-[rgb(var(--shiro-panel-rgb)/0.28)] px-2 py-0.5 text-[rgb(var(--shiro-accent-rgb)/0.72)]">
            {category}
          </span>
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {readTime}
          </span>
          <span className="flex items-center gap-1">
            <Eye className="h-3 w-3" />0
          </span>
          <span className="flex items-center gap-1">
            <MessageCircle className="h-3 w-3" />0
          </span>
        </div>

        <h1 className="text-2xl sm:text-3xl font-heading italic tracking-tight text-foreground leading-tight">
          {data.title || t("common.untitled")}
        </h1>

        {data.tags && data.tags.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {data.tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 rounded-lg border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-foreground/5 px-2.5 py-1 text-[11px] font-body text-foreground/30 transition-colors hover:border-[rgb(var(--shiro-accent-rgb)/0.28)] hover:text-[rgb(var(--shiro-accent-rgb)/0.78)]"
              >
                <Tag className="h-3 w-3" />
                {tag}
              </span>
            ))}
          </div>
        )}
      </motion.div>

      <motion.article
        ref={articleRef}
        className="mt-10"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
      >
        <Suspense
          fallback={
            <div className="space-y-4">
              <div className="h-4 w-full rounded-full bg-foreground/[0.035]" />
              <div className="h-4 w-[88%] rounded-full bg-foreground/[0.03]" />
              <div className="h-4 w-[76%] rounded-full bg-foreground/[0.03]" />
            </div>
          }
        >
          <ArticleMarkdownRenderer content={data.body || ""} />
        </Suspense>
      </motion.article>

      {featureFlags.toc && (
        <TableOfContents
          containerRef={articleRef}
          content={[data.body || ""]}
        />
      )}

      <div className="mt-12 border-t border-[rgb(var(--shiro-divider-rgb)/0.26)] pt-8">
        <p className="text-center text-xs font-body text-foreground/20">
          {t("postDetail.endLabel")}
        </p>
      </div>
    </>
  );
}

function DiaryPreview({ data }: { data: ContentPreviewData }) {
  const { t } = useFrontendI18n();
  const featureFlags = useFeatureFlags();
  const articleRef = useRef<HTMLElement>(null);
  const headerDateLabel = formatEnglishHeaderDate(data.published_at, t);
  const WeatherIcon = data.weather ? weatherIcons[data.weather] : null;
  const weatherLabel =
    data.weather && weatherLabelKeys[data.weather]
      ? t(weatherLabelKeys[data.weather])
      : data.weather || "";

  useEffect(() => {
    void ArticleMarkdownRenderer.preload();
  }, []);

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="mx-auto mb-8 w-[92%] px-2 py-2 sm:w-[90%] sm:px-4 sm:py-3">
          <div className="grid min-h-[3.5rem] grid-cols-[minmax(0,1fr)_auto] items-center gap-3 sm:min-h-[3.75rem] sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
            <div className="col-start-1 min-w-0 sm:col-start-2">
              <div className="flex flex-col items-start gap-2 sm:items-center">
                <div className="flex flex-wrap items-center justify-start gap-2 text-left text-[13px] text-foreground/36 sm:justify-center sm:text-center">
                  <span className="inline-flex flex-col items-start gap-2 sm:items-center">
                  <span
                    className="text-[1.72rem] leading-[0.96] text-[rgb(var(--shiro-accent-rgb)/0.68)] sm:text-[1.92rem]"
                    style={{ fontFamily: "'Pinyon Script', cursive" }}
                  >
                    {headerDateLabel}
                  </span>
                    <DecorativeVineLine />
                  </span>
                </div>
              </div>
            </div>

            <div className="col-start-2 flex shrink-0 items-center justify-self-end self-end gap-1.5 sm:col-start-3 sm:gap-2">
              {data.mood ? (
                <span className="inline-flex h-7 min-w-7 items-center justify-center rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-[rgb(var(--shiro-panel-rgb)/0.2)] px-1.5 text-[0.98rem] leading-none text-foreground/78 sm:h-8 sm:min-w-8 sm:px-1.5 sm:text-[1.05rem]">
                  {data.mood}
                </span>
              ) : null}
              {WeatherIcon ? (
                <span className="inline-flex h-7 items-center gap-1.5 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-[rgb(var(--shiro-panel-rgb)/0.2)] px-2.5 text-[12px] font-body text-foreground/62 sm:h-8 sm:px-3 sm:text-[13px]">
                  <WeatherIcon className="h-[13px] w-[13px] text-[rgb(var(--shiro-accent-rgb)/0.68)] sm:h-[14px] sm:w-[14px]" />
                  {weatherLabel}
                </span>
              ) : null}
            </div>
          </div>
        </div>
      </motion.div>

      <motion.article
        ref={articleRef}
        className="mx-auto mt-6 w-full max-w-[46rem]"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
      >
        <Suspense
          fallback={
            <div className="space-y-4">
              <div className="h-4 w-full rounded-full bg-foreground/[0.035]" />
              <div className="h-4 w-[88%] rounded-full bg-foreground/[0.03]" />
              <div className="h-4 w-[76%] rounded-full bg-foreground/[0.03]" />
            </div>
          }
        >
          <ArticleMarkdownRenderer content={data.body || ""} />
        </Suspense>
      </motion.article>

      {featureFlags.toc && (
        <TableOfContents
          containerRef={articleRef}
          content={[data.body || ""]}
        />
      )}

      {data.poem && (
        <motion.div
          className="mt-12 border-t border-[rgb(var(--shiro-divider-rgb)/0.26)] pt-8 text-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
        >
          <p className="whitespace-pre-line text-sm font-body text-foreground/30 italic">
            {data.poem}
          </p>
        </motion.div>
      )}
    </>
  );
}

function FragmentPreview({ data }: { data: ContentPreviewData }) {
  const { t, lang } = useFrontendI18n();
  const featureFlags = useFeatureFlags();
  const articleRef = useRef<HTMLElement>(null);
  const dateLabel = data.published_at
    ? formatDateInBeijing(data.published_at, lang === "zh" ? "zh-CN" : "en-US", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      })
    : t("common.draft");
  const secondaryMeta = data.type === "thoughts"
    ? [data.category, data.mood].filter(Boolean)
    : [data.category, data.author_name, data.source].filter(Boolean);

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="liquid-glass rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.14)] p-6">
          <p className="text-xs font-body text-foreground/25">
            {dateLabel}
          </p>
          {secondaryMeta.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {secondaryMeta.map((value) => (
                <span
                  key={value}
                  className="rounded-md border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-[rgb(var(--shiro-panel-rgb)/0.24)] px-2 py-0.5 text-[11px] font-body text-foreground/46"
                >
                  {value}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </motion.div>

      <motion.article
        ref={articleRef}
        className="mt-8"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
      >
        {data.body ? (
          <MarkdownRenderer content={data.body} />
        ) : (
          <p className="text-sm font-body text-foreground/40">{t("common.empty")}</p>
        )}
      </motion.article>

      {featureFlags.toc && data.body ? (
        <TableOfContents
          containerRef={articleRef}
          content={[data.body]}
        />
      ) : null}
    </>
  );
}

function ResumePreview({ data }: { data: ContentPreviewData }) {
  const { t } = useFrontendI18n();
  return (
    <PageShell
      eyebrow=""
      title=""
      description=""
      width="wide"
      contentClassName="mt-0"
      compactHeader
    >
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.06, ease: [0.16, 1, 0.3, 1] }}
      >
        <EmbeddedResume
          name={data.title || t("preview.defaultName")}
          content={data.summary || ""}
          profileImageUrl={data.profile_image_url}
          contacts={{
            location: data.location,
            email: data.email,
          }}
        />
      </motion.div>
    </PageShell>
  );
}

export default function Preview() {
  const { t } = useFrontendI18n();
  const [params] = useSearchParams();
  const storageKey = params.get("storageKey") || "";
  const { data, isLoading } = usePreviewChannel(storageKey);

  if (isLoading || !data) {
    return (
      <div className="min-h-screen bg-background text-foreground">
        <FallingPetals />
        <Navbar />
        <main className="mx-auto max-w-2xl px-6 pt-28 pb-20 lg:px-8">
          <p className="text-sm font-body text-foreground/40">
            {storageKey && isLoading
              ? t("preview.loadingData")
              : t("preview.missingParam")}
          </p>
        </main>
        <Footer />
      </div>
    );
  }

  if (data.type === "resume") {
    return (
      <>
        <PreviewModeBadge />
        <ResumePreview data={data} />
      </>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <FallingPetals />
      <Navbar />

      <PreviewModeBadge />

      <main className="mx-auto max-w-2xl px-6 pt-28 pb-20 lg:px-8">
        {data.type === "diary" ? (
          <DiaryPreview data={data} />
        ) : data.type === "thoughts" || data.type === "excerpts" ? (
          <FragmentPreview data={data} />
        ) : (
          <PostPreview data={data} />
        )}
      </main>

      <BackToTop />
      <Footer />
    </div>
  );
}
