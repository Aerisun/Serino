import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import { ChevronDown, Cloud, CloudLightning, CloudRain, CloudSnow, Sun, Wind } from "lucide-react";
import PageShell from "@/components/PageShell";
import { staggerItem } from "@/config";
import { usePageConfig } from "@/contexts/RuntimeConfigContext";
import { fetchPublicContentCollection, formatPublishedDate, splitContentParagraphs, type PublicContentEntry } from "@/lib/api";
import type { BaseViewPageConfig } from "@/lib/page-config";

interface DiaryEntry {
  id: number;
  slug: string;
  date: string;
  day: string;
  weekday: string;
  weather?: string;
  weatherLabel: string;
  mood?: string;
  content: string;
}

type WeatherIconComponent = typeof Sun;

type DiaryPageConfig = BaseViewPageConfig;

const weatherIcons: Record<string, WeatherIconComponent> = {
  sunny: Sun,
  cloudy: Cloud,
  rainy: CloudRain,
  snowy: CloudSnow,
  stormy: CloudLightning,
  windy: Wind,
};

const weatherLabels: Record<string, string> = {
  sunny: "晴",
  cloudy: "多云",
  rainy: "雨",
  snowy: "雪",
  stormy: "雷阵雨",
  windy: "大风",
};

const formatDayOfMonth = (value: string | null) => {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return String(parsed.getDate()).padStart(2, "0");
};

const formatWeekday = (value: string | null) => {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return new Intl.DateTimeFormat("zh-CN", { weekday: "short" }).format(parsed);
};

const mapRemoteDiaryEntry = (entry: PublicContentEntry, index: number): DiaryEntry => {
  const paragraphs = splitContentParagraphs(entry.body);

  return {
    id: index + 1,
    slug: entry.slug,
    date: formatPublishedDate(entry.published_at) || "",
    day: formatDayOfMonth(entry.published_at),
    weekday: formatWeekday(entry.published_at),
    weather: entry.weather ?? undefined,
    weatherLabel: (entry.weather && weatherLabels[entry.weather]) || "",
    mood: entry.mood ?? undefined,
    content: entry.summary?.trim() || paragraphs[0] || entry.body || entry.title,
  };
};

const Diary = () => {
  const config = usePageConfig().diary as DiaryPageConfig;
  const navigate = useNavigate();
  const [items, setItems] = useState<DiaryEntry[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    const loadDiary = async () => {
      setStatus("loading");
      setErrorMessage("");

      try {
        const payload = await fetchPublicContentCollection("diary", 20, { signal: controller.signal });
        if (controller.signal.aborted) {
          return;
        }

        const nextItems = payload.items.map(mapRemoteDiaryEntry);
        setItems(nextItems);
        setStatus(nextItems.length > 0 ? "ready" : "empty");
      } catch (error) {
        if (!controller.signal.aborted) {
          setItems([]);
          setStatus("error");
          setErrorMessage(error instanceof Error ? error.message : "日记加载失败");
        }
      }
    };

    void loadDiary();

    return () => {
      controller.abort();
    };
  }, [reloadKey]);

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
    >
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
            <p className="text-sm font-body leading-relaxed text-foreground/45">日记加载失败</p>
            <p className="mt-2 text-sm font-body leading-relaxed text-foreground/30">{errorMessage}</p>
            <button
              type="button"
              onClick={() => setReloadKey((value) => value + 1)}
              className="mt-3 text-[11px] font-body text-foreground/30 transition-colors hover:text-foreground/60"
            >
              重试
            </button>
          </div>
        )}

        {status === "empty" && (
          <div className="liquid-glass rounded-2xl px-5 py-4">
            <p className="text-sm font-body leading-relaxed text-foreground/35">
              {config.emptyMessage ?? "今天还没有新的日记"}
            </p>
          </div>
        )}

        {status === "ready" &&
          items.map((entry, i) => {
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

                        <div className="flex items-center gap-2">
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
                            <span className="text-[10px] font-body uppercase tracking-wider text-foreground/15 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.48)]">
                              {[entry.date, entry.weatherLabel].filter(Boolean).join(" · ")}
                            </span>
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                navigate(`/diary/${entry.slug}`);
                              }}
                              className="text-[11px] font-body text-foreground/30 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.76)]"
                            >
                              查看详情 →
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
    </PageShell>
  );
};

export default Diary;
