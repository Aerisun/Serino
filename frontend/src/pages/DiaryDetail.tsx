import { useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowLeft, Cloud, CloudLightning, CloudRain, CloudSnow, Sun, Wind } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import FallingPetals from "@/components/FallingPetals";
import CommentSection from "@/components/CommentSection";

import PageMeta from "@/components/PageMeta";
import CodeHighlighter from "@/components/CodeHighlighter";
import JsonLd from "@/components/JsonLd";
import TableOfContents from "@/components/TableOfContents";
import { useFeatureFlags } from "@/contexts/runtime-config";
import { formatPublishedDate } from "@/lib/api/utils";
import { useReadDiaryEntryApiV1PublicDiarySlugGet } from "@serino/api-client/public";
import type { ContentEntryRead } from "@serino/api-client/models";
import MarkdownRenderer from "@/components/MarkdownRenderer";

type Weather = "sunny" | "cloudy" | "rainy" | "snowy" | "stormy" | "windy";

const weatherIcons: Record<Weather, typeof Sun> = {
  sunny: Sun,
  cloudy: Cloud,
  rainy: CloudRain,
  snowy: CloudSnow,
  stormy: CloudLightning,
  windy: Wind,
};

const weatherLabels: Record<Weather, string> = {
  sunny: "晴",
  cloudy: "多云",
  rainy: "雨",
  snowy: "雪",
  stormy: "雷阵雨",
  windy: "大风",
};

interface DiaryData {
  slug: string;
  date: string;
  weekday: string;
  weather?: Weather;
  mood?: string;
  title: string;
  body: string;
  poem?: string;
  likes: number | null;
  comments: number | null;
}

const formatWeekday = (value: string | null) => {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return new Intl.DateTimeFormat("zh-CN", { weekday: "short" }).format(parsed);
};

const buildRemoteDiaryEntry = (entry: ContentEntryRead): DiaryData => ({
  slug: entry.slug,
  date: formatPublishedDate(entry.published_at) || "",
  weekday: formatWeekday(entry.published_at),
  weather: entry.weather as Weather | undefined,
  mood: entry.mood ?? undefined,
  title: entry.title,
  body: entry.body,
  poem: entry.poem ?? undefined,
  likes: entry.like_count ?? null,
  comments: entry.comment_count ?? null,
});

const DiaryDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const featureFlags = useFeatureFlags();
  const articleRef = useRef<HTMLDivElement>(null);

  const slug = id ? decodeURIComponent(id) : "";
  const { data: response, isLoading, isError, error, refetch } = useReadDiaryEntryApiV1PublicDiarySlugGet(slug, { query: { enabled: !!id } });

  const entry = response?.data ? buildRemoteDiaryEntry(response.data) : null;
  const is404 = isError && error != null && typeof error === "object" && "response" in error && (error as { response?: { status?: number } }).response?.status === 404;
  const status: "loading" | "ready" | "empty" | "error" = isLoading
    ? "loading"
    : isError
      ? is404 ? "empty" : "error"
      : entry ? "ready" : "empty";
  const errorMessage = isError
    ? is404
      ? "日记不存在或已被移除"
      : error instanceof Error ? error.message : "日记加载失败"
    : !id ? "缺少日记标识" : "";

  const WeatherIcon = entry?.weather ? weatherIcons[entry.weather] : null;
  const weatherLabel = entry?.weather ? weatherLabels[entry.weather] : "";

  return (
    <div className="min-h-screen bg-background text-foreground">
      <PageMeta
        title={entry?.title ?? (status === "error" ? "日记加载失败" : "日记不存在")}
        description={entry?.body.slice(0, 150) ?? (errorMessage || "你访问的日记暂时不存在。")}
      />
      {entry && (
        <JsonLd
          title={entry.title}
          description={entry.body.slice(0, 200) || ""}
          slug={entry.slug}
          type="diary"
        />
      )}
      <FallingPetals />
      <Navbar />

      <main className="mx-auto max-w-2xl px-6 pt-28 pb-20 lg:px-8">
        <motion.button
          type="button"
          onClick={() => navigate(-1)}
          className="mb-8 flex items-center gap-1.5 text-sm font-body text-foreground/30 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] active:scale-95"
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        >
          <ArrowLeft className="h-4 w-4" />
          返回
        </motion.button>

        {status === "loading" ? (
          <>
            <motion.div
              className="mb-10 rounded-2xl liquid-glass border border-[rgb(var(--shiro-border-rgb)/0.16)] p-6 sm:p-8"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="mb-4 flex items-start justify-between">
                <div className="w-full">
                  <div className="h-3 w-36 rounded-full bg-foreground/[0.04]" />
                  <div className="mt-3 h-8 w-[58%] rounded-full bg-foreground/[0.045]" />
                </div>
                <div className="ml-4 flex shrink-0 items-center gap-2">
                  <div className="h-8 w-8 rounded-full bg-foreground/[0.04]" />
                  <div className="h-7 w-14 rounded-lg bg-foreground/[0.04]" />
                </div>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
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
              className="liquid-glass mb-10 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] p-6 sm:p-8"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="mb-4 flex items-start justify-between">
                <div>
                  <p className="text-xs font-body uppercase tracking-wider text-[rgb(var(--shiro-accent-rgb)/0.54)]">
                    {entry.weekday ? `${entry.weekday} · ` : ""}
                    {entry.date}
                  </p>
                  <h1 className="mt-2 text-xl sm:text-2xl font-heading italic tracking-tight text-foreground/90">
                    {entry.title}
                  </h1>
                </div>
                <div className="ml-4 flex shrink-0 items-center gap-2">
                  {entry.mood ? <span className="text-2xl">{entry.mood}</span> : null}
                  {WeatherIcon ? (
                    <div className="flex items-center gap-1 rounded-lg border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-[rgb(var(--shiro-panel-rgb)/0.24)] px-2.5 py-1">
                      <WeatherIcon className="h-3.5 w-3.5 text-[rgb(var(--shiro-accent-rgb)/0.7)]" />
                      <span className="text-[11px] font-body text-[rgb(var(--shiro-accent-rgb)/0.68)]">{weatherLabel}</span>
                    </div>
                  ) : null}
                </div>
              </div>
            </motion.div>

            <motion.div
              ref={articleRef}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            >
              <MarkdownRenderer content={entry.body} />
            </motion.div>

            <CodeHighlighter containerRef={articleRef} content={[entry.body]} />
            {featureFlags.toc && <TableOfContents containerRef={articleRef} content={[entry.body]} />}

            {entry.poem && (
              <motion.div
                className="mt-10 border-b border-t border-[rgb(var(--shiro-divider-rgb)/0.26)] py-6 text-center"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.6, delay: 0.4 }}
              >
                <p className="text-sm font-heading italic tracking-wide text-[rgb(var(--shiro-accent-rgb)/0.5)]">{entry.poem}</p>
              </motion.div>
            )}

            <div className="mt-10 text-center">
              <p className="text-xs font-body text-[rgb(var(--shiro-accent-rgb)/0.42)]">— 今日份记录 —</p>
            </div>

            <CommentSection
              contentType="diary"
              contentSlug={entry.slug}
            />
          </>
        ) : (
          <motion.div
            className="border-t border-[rgb(var(--shiro-divider-rgb)/0.26)] pt-8"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          >
            <p className="text-sm font-body text-foreground/40">
              {status === "error" ? "日记加载失败" : "日记不存在"}
            </p>
            <p className="mt-2 text-xs font-body text-foreground/25">
              {errorMessage || "你访问的日记暂时不存在。"}
            </p>
            <button
              type="button"
              onClick={status === "error" ? () => refetch() : () => navigate("/diary")}
              className="mt-4 text-xs font-body text-foreground/30 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.8)]"
            >
              {status === "error" ? "重试" : "返回列表"}
            </button>
          </motion.div>
        )}
      </main>

      <Footer />
    </div>
  );
};

export default DiaryDetail;
