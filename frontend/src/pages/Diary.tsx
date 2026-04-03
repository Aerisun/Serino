import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import {
  ChevronDown,
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
  Search,
  Sun,
  Wind,
} from "lucide-react";
import ArchiveBadge from "@/components/ArchiveBadge";
import PageShell from "@/components/PageShell";
import { staggerItem } from "@/config";
import { usePageConfig } from "@/contexts/runtime-config";
import { useFrontendI18n, type FrontendLang } from "@/i18n";
import { useInfiniteList } from "@/hooks/use-infinite-list";
import { formatPublishedDate, splitContentParagraphs } from "@/lib/api/utils";
import { clampPageSize } from "@/lib/page-size";
import { formatDateInBeijing, getBeijingDateParts } from "@/lib/time";
import { readDiaryApiV1SiteDiaryGet } from "@serino/api-client/site";
import type { ContentEntryRead } from "@serino/api-client/models";
import type { BaseViewPageConfig } from "@/lib/page-config";

interface DiaryEntry {
  id: number;
  slug: string;
  date: string;
  day: string;
  weekday: string;
  isArchived: boolean;
  weather?: string;
  weatherLabel: string;
  mood?: string;
  content: string;
  poem?: string;
}

type WeatherIconComponent = typeof Sun;

interface DiaryPageConfig extends BaseViewPageConfig {
  detailCtaLabel?: string;
}

const weatherIcons: Record<string, WeatherIconComponent> = {
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

const formatDayOfMonth = (value: string | null) => {
  const parts = value ? getBeijingDateParts(value) : null;
  return parts ? String(parts.day).padStart(2, "0") : "";
};

const formatWeekday = (value: string | null, lang: FrontendLang) => {
  return value
    ? formatDateInBeijing(value, lang === "zh" ? "zh-CN" : "en-US", { weekday: "short" })
    : "";
};

const mapRemoteDiaryEntry = (
  entry: ContentEntryRead,
  index: number,
  t: (key: string, values?: Record<string, string | number>, fallback?: string) => string,
  lang: FrontendLang,
): DiaryEntry => {
  const paragraphs = splitContentParagraphs(entry.body);

  return {
    id: index + 1,
    slug: entry.slug,
    date: formatPublishedDate(entry.published_at) || "",
    day: formatDayOfMonth(entry.published_at),
    weekday: formatWeekday(entry.published_at, lang),
    isArchived: entry.status === "archived",
    weather: entry.weather ?? undefined,
    weatherLabel:
      entry.weather && weatherLabelKeys[entry.weather]
        ? t(weatherLabelKeys[entry.weather])
        : "",
    mood: entry.mood ?? undefined,
    content: entry.summary?.trim() || paragraphs[0] || entry.body || entry.title,
    poem: entry.poem?.trim() || undefined,
  };
};

const matchesSearchText = (fields: Array<string | null | undefined>, query: string) => {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return true;
  }

  return fields.some((field) => (field ?? "").toLowerCase().includes(normalizedQuery));
};

const Diary = () => {
  const { t, lang } = useFrontendI18n();
  const config = usePageConfig().diary as unknown as DiaryPageConfig;
  const errorTitle = config.errorTitle ?? t("diary.errorTitle");
  const retryLabel = config.retryLabel ?? t("common.retry");
  const loadMoreLabel = config.loadMoreLabel ?? t("diary.loadingMore");
  const detailCtaLabel = config.detailCtaLabel ?? t("diary.detailCta");
  const searchPlaceholder = config.searchPlaceholder ?? t("diary.searchPlaceholder");
  const navigate = useNavigate();
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const pageSize = clampPageSize(config.pageSize, 15);
  const [search, setSearch] = useState("");
  const [rawSearch, setRawSearch] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { items, status, errorMessage, hasMore, isLoadingMore, sentinelRef, reload } = useInfiniteList({
    queryKey: ["site", "diary"],
    queryFn: async (p) => {
      const data = (await readDiaryApiV1SiteDiaryGet(p)).data;

      if (data && "items" in data && Array.isArray(data.items)) {
        return {
          items: data.items,
          has_more: Boolean(data.has_more),
        };
      }

      throw new Error(t("diary.invalidResponse"));
    },
    pageSize,
    mapItem: (entry, index) => mapRemoteDiaryEntry(entry, index, t, lang),
  });

  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  const filtered = useMemo(() => {
    return items.filter((entry) =>
      matchesSearchText(
        [entry.date, entry.day, entry.weekday, entry.weatherLabel, entry.mood, entry.content, entry.poem],
        search,
      ),
    );
  }, [items, search]);

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width === "narrow" ? "content" : (config.width ?? "content")}
    >
      <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="group relative max-w-xs flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground/25 transition-colors group-focus-within:text-[rgb(var(--shiro-accent-rgb)/0.72)]" />
          <input
            type="text"
            placeholder={searchPlaceholder}
            value={rawSearch}
            onChange={(event) => {
              const value = event.target.value;
              setRawSearch(value);
              if (debounceRef.current) {
                clearTimeout(debounceRef.current);
              }
              debounceRef.current = setTimeout(() => setSearch(value), 300);
            }}
            maxLength={100}
            aria-label={searchPlaceholder}
            className="w-full rounded-xl border border-foreground/8 bg-foreground/[0.03] py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-foreground/25 outline-none transition-colors focus:border-[rgb(var(--shiro-border-rgb)/0.32)] focus:bg-[rgb(var(--shiro-panel-rgb)/0.35)]"
          />
        </div>
      </div>

      <div className="mt-10 flex flex-col gap-3">
        {status === "loading" &&
          Array.from({ length: 5 }, (_, index) => (
            <div key={`diary-skeleton-${index}`} className="liquid-glass rounded-2xl px-5 py-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex min-w-[42px] flex-col items-center">
                    <div className="h-5 w-6 rounded-full bg-foreground/[0.05]" />
                    <div className="mt-1 h-2.5 w-8 rounded-full bg-foreground/[0.035]" />
                  </div>
                  <div className="h-8 w-px bg-foreground/[0.08]" />
                  <div className="flex items-center gap-2">
                    <div className="h-4 w-4 rounded-full bg-foreground/[0.04]" />
                    <div className="h-3 w-12 rounded-full bg-foreground/[0.04]" />
                  </div>
                </div>
                <div className="h-4 w-4 rounded-full bg-foreground/[0.03]" />
              </div>
              <div className="mt-3 h-4 w-[80%] rounded-full bg-foreground/[0.04]" />
            </div>
          ))}

        {status === "error" && (
          <div className="liquid-glass rounded-2xl px-5 py-4">
            <p className="text-sm font-body leading-relaxed text-foreground/45">{errorTitle}</p>
            <p className="mt-2 text-sm font-body leading-relaxed text-foreground/30">{errorMessage}</p>
            <button
              type="button"
              onClick={() => reload()}
              className="mt-3 text-[11px] font-body text-foreground/30 transition-colors hover:text-foreground/60"
            >
              {retryLabel}
            </button>
          </div>
        )}

        {(status === "empty" || (status === "ready" && filtered.length === 0)) && (
          <div className="liquid-glass rounded-2xl px-5 py-4">
            <p className="text-sm font-body leading-relaxed text-foreground/35">
              {config.emptyMessage ?? t("diary.emptyMessage")}
            </p>
          </div>
        )}

        {status === "ready" &&
          filtered.map((entry, i) => {
            const isExpanded = expandedId === entry.id;
            const WeatherIcon = entry.weather ? weatherIcons[entry.weather] : null;

            return (
              <motion.div
                key={entry.id}
                {...staggerItem(i, {
                  baseDelay: config.motion.delay,
                  step: config.motion.stagger,
                  duration: config.motion.duration,
                })}
              >
                <button
                  type="button"
                  onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                  className="w-full text-left"
                >
                  <div
                    className={`group liquid-glass rounded-2xl px-5 py-4 cursor-pointer transition-[background-color,border-color,box-shadow] ${
                      isExpanded
                        ? "border border-[rgb(var(--shiro-border-rgb)/0.14)] bg-[rgb(var(--shiro-panel-rgb)/0.22)]"
                        : "hover:border hover:border-[rgb(var(--shiro-border-rgb)/0.12)] hover:bg-[rgb(var(--shiro-panel-rgb)/0.16)]"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="flex min-w-[42px] flex-col items-center">
                          <span className="text-lg font-body font-medium leading-none text-foreground/80 tabular-nums transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.92)]">
                            {entry.day || "--"}
                          </span>
                          <span className="mt-0.5 text-[10px] font-body text-foreground/25 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.68)]">
                            {entry.weekday}
                          </span>
                        </div>

                        <div className="h-8 w-px bg-foreground/[0.08] transition-colors group-hover:bg-[rgb(var(--shiro-divider-rgb)/0.34)]" />

                        <div className="flex flex-wrap items-center gap-2">
                          {entry.isArchived ? <ArchiveBadge /> : null}
                          {WeatherIcon ? <WeatherIcon className="h-4 w-4 text-foreground/30 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.5)]" /> : null}
                          {entry.weatherLabel ? (
                            <span className="text-xs font-body text-foreground/30 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.7)]">{entry.weatherLabel}</span>
                          ) : null}
                          {entry.mood && <span className="text-sm transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]">{entry.mood}</span>}
                        </div>
                      </div>

                      <ChevronDown
                        className={`h-4 w-4 text-foreground/20 transition-transform duration-300 group-hover:text-[rgb(var(--shiro-accent-rgb)/0.36)] ${
                          isExpanded ? "rotate-180" : ""
                        }`}
                      />
                    </div>

                    {!isExpanded && (
                      <p className="mt-3 line-clamp-1 text-sm font-body leading-relaxed text-foreground/35 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.68)]">
                        {entry.content}
                      </p>
                    )}

                    <AnimatePresence>
                      {isExpanded && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: config.motion.duration - 0.1, ease: [0.16, 1, 0.3, 1] }}
                          className="overflow-hidden"
                        >
                          <p className="mt-4 text-[0.935rem] font-body leading-7 text-foreground/60 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.8)]">
                            {entry.content}
                          </p>
                          <div className="mt-4 flex items-center justify-between border-t border-foreground/[0.05] pt-3 transition-colors group-hover:border-[rgb(var(--shiro-divider-rgb)/0.28)]">
                            {entry.poem ? (
                              <span className="text-[11px] font-heading italic tracking-wide text-[rgb(var(--shiro-accent-rgb)/0.5)] transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.76)]">
                                {entry.poem}
                              </span>
                            ) : null}
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                navigate(`/diary/${entry.slug}`);
                              }}
                              className="ml-auto text-[11px] font-body text-foreground/30 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.76)]"
                            >
                              {detailCtaLabel} →
                            </button>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </button>
              </motion.div>
            );
          })}
      </div>

      {status === "ready" && hasMore && (
        <div ref={sentinelRef} className="py-8 text-center">
          {isLoadingMore && <span className="text-xs text-foreground/25">{loadMoreLabel}</span>}
        </div>
      )}
    </PageShell>
  );
};

export default Diary;
