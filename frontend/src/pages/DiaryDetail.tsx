import { Suspense, useEffect, useRef } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "motion/react";
import {
  ArrowLeft,
  Cloud,
  CloudDrizzle,
  CloudFog,
  CloudLightning,
  CloudRain,
  CloudRainWind,
  CloudSnow,
  CloudSunRain,
  CloudHail,
  Haze,
  Snowflake,
  Sun,
  Wind,
} from "lucide-react";
import ArchiveBadge from "@/components/ArchiveBadge";
import DecorativeVineLine from "@/components/DecorativeVineLine";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import FallingPetals from "@/components/FallingPetals";

import PageMeta from "@/components/PageMeta";
import JsonLd from "@/components/JsonLd";
import PreviewModeBadge from "@/components/PreviewModeBadge";
import LazyOnVisible from "@/components/LazyOnVisible";
import ArticleEnhancements from "@/components/ArticleEnhancements";
import { useFeatureFlags, usePageConfig } from "@/contexts/runtime-config";
import { useFrontendI18n, type FrontendLang } from "@/i18n";
import { formatPublishedDate } from "@/lib/api/utils";
import { usePreviewChannel, type ContentPreviewData } from "@/lib/preview";
import { formatDateInBeijing } from "@/lib/time";
import { useReadDiaryEntryApiV1SiteDiarySlugGet } from "@serino/api-client/site";
import type { ContentEntryRead } from "@serino/api-client/models";
import type { BaseViewPageConfig } from "@/lib/page-config";
import { lazyWithPreload } from "@/lib/lazy";

const CommentSection = lazyWithPreload(() => import("@/components/CommentSection"));
const ArticleMarkdownRenderer = lazyWithPreload(() => import("@/components/ArticleMarkdownRenderer"));

type Weather =
  | "sunny"
  | "cloudy"
  | "fog"
  | "haze"
  | "light_rain"
  | "shower"
  | "rainy"
  | "heavy_rain"
  | "light_snow"
  | "snowy"
  | "heavy_snow"
  | "sleet"
  | "stormy"
  | "windy";

const weatherIcons: Record<Weather, typeof Sun> = {
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

const weatherLabelKeys: Record<Weather, string> = {
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

interface DiaryData {
  slug: string;
  date: string;
  weekday: string;
  headerDate: string;
  isArchived: boolean;
  weather?: Weather;
  mood?: string;
  title: string;
  body: string;
  poem?: string;
  likes: number | null;
  comments: number | null;
}

interface DiaryDetailPageConfig extends BaseViewPageConfig {
  detailBackLabel?: string;
  detailListLabel?: string;
  detailMissingTitle?: string;
  detailMissingDescription?: string;
  detailEndLabel?: string;
}

const formatWeekday = (value: string | null, lang: FrontendLang) => {
  return value
    ? formatDateInBeijing(value, lang === "zh" ? "zh-CN" : "en-US", { weekday: "short" })
    : "";
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

const buildRemoteDiaryEntry = (
  entry: ContentEntryRead,
  lang: FrontendLang,
  t: (key: string, values?: Record<string, string | number>, fallback?: string) => string,
): DiaryData => ({
  slug: entry.slug,
  date: formatPublishedDate(entry.published_at) || "",
  weekday: formatWeekday(entry.published_at, lang),
  headerDate: formatEnglishHeaderDate(entry.published_at, t),
  isArchived: entry.status === "archived",
  weather: entry.weather as Weather | undefined,
  mood: entry.mood ?? undefined,
  title: entry.title,
  body: entry.body,
  poem: entry.poem ?? undefined,
  likes: entry.like_count ?? null,
  comments: entry.comment_count ?? null,
});

const buildPreviewDiaryEntry = (
  preview: ContentPreviewData,
  lang: FrontendLang,
  t: (key: string, values?: Record<string, string | number>, fallback?: string) => string,
): DiaryData => ({
  slug: preview.slug || "",
  date: formatPublishedDate(preview.published_at) || t("common.draft"),
  weekday: formatWeekday(preview.published_at ?? null, lang),
  headerDate: formatEnglishHeaderDate(preview.published_at, t),
  isArchived: false,
  weather: preview.weather as Weather | undefined,
  mood: preview.mood ?? undefined,
  title: preview.title,
  body: preview.body || "",
  poem: preview.poem ?? undefined,
  likes: 0,
  comments: 0,
});

const buildDiaryPublicLabel = (entry: DiaryData | null, fallback: string) => {
  if (!entry) {
    return fallback;
  }
  return entry.weekday ? `${entry.weekday} · ${entry.date}` : entry.date || fallback;
};

const DiaryDetail = () => {
  const { t, lang } = useFrontendI18n();
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const featureFlags = useFeatureFlags();
  const diaryConfig = (usePageConfig().diary ?? {}) as DiaryDetailPageConfig;
  const detailBackLabel = diaryConfig.detailBackLabel ?? t("diaryDetail.back");
  const detailListLabel = diaryConfig.detailListLabel ?? t("diaryDetail.backToList");
  const detailMissingTitle = diaryConfig.detailMissingTitle ?? t("diaryDetail.missingTitle");
  const detailMissingDescription =
    diaryConfig.detailMissingDescription ?? t("diaryDetail.missingDescription");
  const detailEndLabel = diaryConfig.detailEndLabel ?? t("diaryDetail.endLabel");
  const errorTitle = diaryConfig.errorTitle ?? t("diary.errorTitle");
  const retryLabel = diaryConfig.retryLabel ?? t("common.retry");
  const articleRef = useRef<HTMLDivElement>(null);
  const previewStorageKey = searchParams.get("previewStorageKey") || "";

  const slug = id ? decodeURIComponent(id) : "";
  const { data: previewData, isLoading: isPreviewLoading } =
    usePreviewChannel(previewStorageKey);
  const {
    data: response,
    isLoading,
    isError,
    error,
    refetch,
  } = useReadDiaryEntryApiV1SiteDiarySlugGet(slug, {
    query: {
      enabled: !!id,
      staleTime: 5 * 60_000,
      gcTime: 20 * 60_000,
    },
  });

  const previewEntry =
    previewData?.type === "diary" ? buildPreviewDiaryEntry(previewData, lang, t) : null;
  const entry =
    previewEntry ??
    (response?.data ? buildRemoteDiaryEntry(response.data, lang, t) : null);
  const is404 =
    isError &&
    error != null &&
    typeof error === "object" &&
    "response" in error &&
    (error as { response?: { status?: number } }).response?.status === 404;
  const status: "loading" | "ready" | "empty" | "error" = previewEntry
    ? "ready"
    : isLoading
      ? "loading"
      : isError
        ? is404
          ? "empty"
          : "error"
        : entry
          ? "ready"
          : "empty";
  const pageStatus: "loading" | "ready" | "empty" | "error" =
    isPreviewLoading && !previewEntry ? "loading" : status;
  const errorMessage = isError
    ? is404
      ? detailMissingDescription
      : error instanceof Error
        ? error.message
        : errorTitle
    : !id
      ? t("diaryDetail.missingId")
      : "";
  const showArticleEnhancements = Boolean(entry) && featureFlags.toc;

  useEffect(() => {
    if (entry) {
      void ArticleMarkdownRenderer.preload();
      void CommentSection.preload();
    }
  }, [entry]);

  const WeatherIcon = entry?.weather ? weatherIcons[entry.weather] : null;
  const weatherLabel = entry?.weather ? t(weatherLabelKeys[entry.weather]) : "";
  const publicDiaryLabel = buildDiaryPublicLabel(entry, t("nav.diary"));
  const headerDateLabel = entry?.headerDate || "";

  return (
    <div className="min-h-screen bg-background text-foreground">
      <PageMeta
        title={entry ? publicDiaryLabel : (status === "error" ? errorTitle : detailMissingTitle)}
        description={
          entry?.body.slice(0, 150) ??
          (errorMessage || detailMissingDescription)
        }
      />
      {entry && (
        <JsonLd
          title={publicDiaryLabel}
          description={entry.body.slice(0, 200) || ""}
          slug={entry.slug}
          type="diary"
        />
      )}
      <FallingPetals />
      <Navbar />
      {previewEntry ? <PreviewModeBadge /> : null}

      <main className="mx-auto max-w-5xl px-6 pt-28 pb-20 lg:px-8">
        <motion.button
          type="button"
          onClick={() => navigate(-1)}
          className="mb-8 flex items-center gap-1.5 text-sm font-body text-foreground/30 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] active:scale-95"
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        >
          <ArrowLeft className="h-4 w-4" />
          {detailBackLabel}
        </motion.button>

        {pageStatus === "loading" ? (
          <>
            <motion.div
              className="mb-8 overflow-hidden rounded-[2rem] liquid-glass border border-[rgb(var(--shiro-border-rgb)/0.16)] px-6 py-6 sm:px-8 sm:py-8"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="relative flex min-h-[180px] flex-col justify-between gap-6">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="space-y-3">
                    <div className="h-8 w-48 rounded-full bg-foreground/[0.04]" />
                    <div className="h-3 w-28 rounded-full bg-foreground/[0.04]" />
                  </div>
                  <div className="flex items-center gap-3 self-start">
                    <div className="h-12 w-12 rounded-[1rem] bg-foreground/[0.04]" />
                    <div className="h-14 w-32 rounded-[1.2rem] bg-foreground/[0.04]" />
                  </div>
                </div>
                <div>
                  <div className="h-3 w-32 rounded-full bg-foreground/[0.04]" />
                  <div className="mt-4 h-24 w-44 rounded-[1.8rem] bg-foreground/[0.045]" />
                </div>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: 0.5,
                delay: 0.1,
                ease: [0.16, 1, 0.3, 1],
              }}
            >
              {Array.from({ length: 4 }, (_, index) => (
                <div key={`diary-line-${index}`} className="mb-6">
                  <div className="h-4 w-full rounded-full bg-foreground/[0.035]" />
                  <div className="mt-2 h-4 w-[82%] rounded-full bg-foreground/[0.03]" />
                </div>
              ))}
            </motion.div>
          </>
        ) : entry ? (
          <>
            <motion.div
              className="mx-auto mb-8 w-[92%] px-2 py-2 sm:w-[90%] sm:px-4 sm:py-3"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="grid min-h-[3.5rem] grid-cols-[minmax(0,1fr)_auto] items-center gap-3 sm:min-h-[3.75rem] sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
                <div className="col-start-1 min-w-0 sm:col-start-2">
                  <div className="flex flex-col items-start gap-2 sm:items-center">
                    <div className="flex flex-wrap items-center justify-start gap-2 text-left text-[13px] text-foreground/36 sm:justify-center sm:text-center">
                      {entry.isArchived ? <ArchiveBadge /> : null}
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
                  {entry.mood ? (
                    <span className="inline-flex h-7 min-w-7 items-center justify-center rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-[rgb(var(--shiro-panel-rgb)/0.2)] px-1.5 text-[0.98rem] leading-none text-foreground/78 sm:h-8 sm:min-w-8 sm:px-1.5 sm:text-[1.05rem]">
                      {entry.mood}
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
            </motion.div>

            <motion.div
              ref={articleRef}
              className="mx-auto w-full max-w-[46rem]"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: 0.5,
                delay: 0.1,
                ease: [0.16, 1, 0.3, 1],
              }}
            >
              <Suspense
                fallback={
                  <div className="space-y-4">
                    <div className="h-4 w-full rounded-full bg-foreground/[0.035]" />
                    <div className="h-4 w-[90%] rounded-full bg-foreground/[0.03]" />
                    <div className="h-4 w-[74%] rounded-full bg-foreground/[0.03]" />
                  </div>
                }
              >
                <ArticleMarkdownRenderer
                  content={entry.body}
                  className="detail-markdown"
                />
              </Suspense>
            </motion.div>

            {showArticleEnhancements ? (
              <ArticleEnhancements
                containerRef={articleRef}
                content={entry.body}
                enableToc={featureFlags.toc}
              />
            ) : null}

            {entry.poem && (
              <motion.div
                className="mt-10 border-b border-t border-[rgb(var(--shiro-divider-rgb)/0.26)] py-6 text-center"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.6, delay: 0.4 }}
              >
                <p className="text-sm font-heading italic tracking-wide text-[rgb(var(--shiro-accent-rgb)/0.5)]">
                  {entry.poem}
                </p>
              </motion.div>
            )}

            <div className="mt-10 text-center">
              <p className="text-xs font-body text-[rgb(var(--shiro-accent-rgb)/0.42)]">
                {detailEndLabel}
              </p>
            </div>

            <LazyOnVisible
              fallback={
                <div className="mt-12 h-24 rounded-[1.5rem] border border-[rgb(var(--shiro-border-rgb)/0.12)] bg-foreground/[0.02]" />
              }
            >
              <Suspense fallback={null}>
                <CommentSection contentType="diary" contentSlug={entry.slug} />
              </Suspense>
            </LazyOnVisible>
          </>
        ) : (
          <motion.div
            className="border-t border-[rgb(var(--shiro-divider-rgb)/0.26)] pt-8"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          >
            <p className="text-sm font-body text-foreground/40">
              {pageStatus === "error" ? errorTitle : detailMissingTitle}
            </p>
            <p className="mt-2 text-xs font-body text-foreground/25">
              {errorMessage || detailMissingDescription}
            </p>
            <button
              type="button"
              onClick={
                pageStatus === "error"
                  ? () => refetch()
                  : () => navigate("/diary")
              }
              className="mt-4 text-xs font-body text-foreground/30 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.8)]"
            >
              {pageStatus === "error" ? retryLabel : detailListLabel}
            </button>
          </motion.div>
        )}
      </main>

      <Footer />
    </div>
  );
};

export default DiaryDetail;
