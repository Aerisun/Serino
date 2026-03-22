import { useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import { ChevronLeft, ChevronRight, FileText, BookOpen, Feather } from "lucide-react";
import { useNavigate } from "react-router-dom";
import PageShell from "@/components/PageShell";
import { staggerItem, transition } from "@/config";
import { usePageConfig } from "@/contexts/RuntimeConfigContext";
import { fetchPublicCalendar, type PublicCalendarEvent } from "@/lib/api";
import type { BaseViewPageConfig } from "@/lib/page-config";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";

interface CalendarEvent {
  date: string;
  type: "post" | "diary" | "excerpt";
  title: string;
  href?: string;
}

interface CalendarPageConfig extends BaseViewPageConfig {
  weekdayLabels?: unknown;
  monthLabels?: unknown;
  todayLabel?: string;
}

const typeConfig = {
  post: {
    icon: FileText,
    label: "帖子",
    chipClass: "bg-[rgb(var(--shiro-accent-rgb)/0.12)] text-[rgb(var(--shiro-accent-rgb)/0.88)]",
    dotClass: "bg-[rgb(var(--shiro-accent-rgb)/0.72)]",
  },
  diary: {
    icon: BookOpen,
    label: "日记",
    chipClass: "bg-[rgb(var(--shiro-accent-rgb)/0.1)] text-[rgb(var(--shiro-accent-rgb)/0.78)]",
    dotClass: "bg-[rgb(var(--shiro-accent-rgb)/0.5)]",
  },
  excerpt: {
    icon: Feather,
    label: "文摘",
    chipClass: "bg-[rgb(var(--shiro-accent-rgb)/0.08)] text-[rgb(var(--shiro-accent-rgb)/0.7)]",
    dotClass: "bg-[rgb(var(--shiro-accent-rgb)/0.38)]",
  },
} as const;

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number) {
  const day = new Date(year, month, 1).getDay();
  return day === 0 ? 6 : day - 1;
}

const formatDateKey = (value: Date) => {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const normalizeDateKey = (value: string) => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }

  return formatDateKey(parsed);
};

const normalizeType = (value: string): CalendarEvent["type"] | null => {
  const raw = value.toLowerCase();
  if (raw === "post" || raw === "posts" || raw === "article") return "post";
  if (raw === "diary" || raw === "diaries" || raw === "journal") return "diary";
  if (raw === "excerpt" || raw === "excerpts" || raw === "quote") return "excerpt";
  return null;
};

const normalizeCalendarEvent = (item: PublicCalendarEvent): CalendarEvent | null => {
  const date = normalizeDateKey(item.date);
  const type = normalizeType(item.type);

  if (!date || !type || !item.title) {
    return null;
  }

  return {
    date,
    type,
    title: item.title,
    href: item.href,
  };
};

const getWeekdayLabels = (value: unknown) => {
  if (Array.isArray(value) && value.length === 7) {
    return value.map(String);
  }

  return ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
};

const getMonthLabels = (value: unknown) => {
  if (Array.isArray(value) && value.length === 12) {
    return value.map(String);
  }

  return Array.from({ length: 12 }, (_, index) => `${index + 1}月`);
};

const CalendarPage = () => {
  const config = usePageConfig().calendar as unknown as CalendarPageConfig;
  const weekdayLabels = getWeekdayLabels(config.weekdayLabels);
  const monthLabels = getMonthLabels(config.monthLabels);
  const today = new Date();
  const navigate = useNavigate();
  const prefersReducedMotion = useReducedMotionPreference();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [calendarEvents, setCalendarEvents] = useState<CalendarEvent[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfMonth(year, month);
  const rangeStart = formatDateKey(new Date(year, month, 1));
  const rangeEnd = formatDateKey(new Date(year, month + 1, 0));

  useEffect(() => {
    const controller = new AbortController();

    const loadCalendarEvents = async () => {
      setStatus("loading");
      setErrorMessage("");
      setCalendarEvents([]);

      try {
        const payload = await fetchPublicCalendar(rangeStart, rangeEnd, { signal: controller.signal });
        if (controller.signal.aborted) {
          return;
        }

        const nextEvents = payload.events
          .map((item) => normalizeCalendarEvent(item))
          .filter((item): item is CalendarEvent => item !== null);

        setCalendarEvents(nextEvents);
        setStatus(nextEvents.length > 0 ? "ready" : "empty");
      } catch (error) {
        if (!controller.signal.aborted) {
          setCalendarEvents([]);
          setStatus("error");
          setErrorMessage(error instanceof Error ? error.message : "日历加载失败");
        }
      }
    };

    void loadCalendarEvents();

    return () => {
      controller.abort();
    };
  }, [month, rangeEnd, rangeStart, reloadKey, year]);

  const eventMap = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {};
    calendarEvents.forEach((event) => {
      if (!map[event.date]) {
        map[event.date] = [];
      }
      map[event.date].push(event);
    });
    return map;
  }, [calendarEvents]);

  const todayKey = formatDateKey(today);
  const activeDate = selectedDate;
  const activeEvents = activeDate ? eventMap[activeDate] || [] : eventMap[todayKey] || [];

  const cells: (number | null)[] = [];
  for (let index = 0; index < firstDay; index += 1) {
    cells.push(null);
  }
  for (let day = 1; day <= daysInMonth; day += 1) {
    cells.push(day);
  }

  const hasMonthData = calendarEvents.length > 0;

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
    >
      <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_280px]">
        <motion.div
          className="rounded-2xl p-6 liquid-glass transition-[background-color,border-color,box-shadow]"
          initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={transition({
            duration: config.motion.duration,
            delay: config.motion.delay,
            reducedMotion: prefersReducedMotion,
          })}
        >
          <div className="mb-6 flex items-center justify-between">
            <button
              type="button"
              onClick={() => {
                if (month === 0) {
                  setMonth(11);
                  setYear((value) => value - 1);
                  return;
                }

                setMonth((value) => value - 1);
              }}
              className="rounded-xl p-2 text-foreground/40 transition-colors hover:bg-[rgb(var(--shiro-panel-rgb)/0.2)] hover:text-[rgb(var(--shiro-accent-rgb)/0.84)] active:scale-95"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
            <h2 className="text-lg font-body font-medium text-foreground/80">
              {year} 年 {monthLabels[month]}
            </h2>
            <button
              type="button"
              onClick={() => {
                if (month === 11) {
                  setMonth(0);
                  setYear((value) => value + 1);
                  return;
                }

                setMonth((value) => value + 1);
              }}
              className="rounded-xl p-2 text-foreground/40 transition-colors hover:bg-[rgb(var(--shiro-panel-rgb)/0.2)] hover:text-[rgb(var(--shiro-accent-rgb)/0.84)] active:scale-95"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
          </div>

          <div className="mb-2 grid grid-cols-7">
            {weekdayLabels.map((label) => (
              <div key={label} className="py-2 text-center text-xs font-body text-foreground/25">
                {label}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-1">
            {cells.map((day, index) => {
              if (day === null) {
                return <div key={`empty-${index}`} />;
              }

              const dateKey = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
              const dayEvents = eventMap[dateKey] || [];
              const isToday = dateKey === todayKey;
              const isSelected = dateKey === activeDate;

              return (
                <button
                  type="button"
                  key={dateKey}
                  onClick={() => setSelectedDate(isSelected ? null : dateKey)}
                  className={`relative flex aspect-square flex-col items-center justify-center gap-0.5 rounded-xl transition-all active:scale-95 ${
                    isSelected
                      ? "bg-[rgb(var(--shiro-accent-rgb)/0.14)] ring-1 ring-[rgb(var(--shiro-accent-rgb)/0.22)]"
                      : isToday
                        ? "bg-[rgb(var(--shiro-panel-rgb)/0.16)]"
                        : "hover:bg-[rgb(var(--shiro-panel-rgb)/0.12)]"
                  }`}
                >
                  <span
                    className={`text-sm font-body tabular-nums ${
                      isToday
                        ? "font-medium text-[rgb(var(--shiro-accent-rgb)/0.9)]"
                        : dayEvents.length > 0
                          ? "text-foreground/70"
                          : "text-foreground/30"
                    }`}
                  >
                    {day}
                  </span>
                  {dayEvents.length > 0 && (
                    <div className="flex gap-0.5">
                      {dayEvents.map((event, markerIndex) => (
                        <span
                          key={`${dateKey}-${markerIndex}`}
                          className={`h-1 w-1 rounded-full ${
                            event.type === "post"
                              ? typeConfig.post.dotClass
                              : event.type === "diary"
                                ? typeConfig.diary.dotClass
                                : typeConfig.excerpt.dotClass
                          }`}
                        />
                      ))}
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          <div className="mt-6 flex items-center gap-4 border-t border-foreground/5 pt-4">
            {Object.entries(typeConfig).map(([key, item]) => (
              <div key={key} className="flex items-center gap-1.5">
                <span
                  className={`h-2 w-2 rounded-full ${item.dotClass}`}
                />
                <span className="text-[11px] font-body text-foreground/30">{item.label}</span>
              </div>
            ))}
          </div>
        </motion.div>

        <motion.div
          className="h-fit rounded-2xl p-5 liquid-glass transition-[background-color,border-color,box-shadow] lg:sticky lg:top-24"
          initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={transition({
            duration: config.motion.duration,
            delay: 0.16,
            reducedMotion: prefersReducedMotion,
          })}
        >
          <h3 className="mb-4 text-xs font-body uppercase tracking-widest text-foreground/30">
            {activeDate ? `${parseInt(activeDate.split("-")[2], 10)} 日` : String(config.todayLabel ?? "")}
          </h3>

          {status === "loading" ? (
            <div className="flex flex-col gap-3">
              <div className="h-14 animate-pulse rounded-xl bg-foreground/[0.03]" />
              <div className="h-14 animate-pulse rounded-xl bg-foreground/[0.03]" />
              <div className="h-14 animate-pulse rounded-xl bg-foreground/[0.03]" />
              <p className="pt-1 text-center text-xs font-body text-foreground/20">
                {String(config.loadingLabel ?? "")}
              </p>
            </div>
          ) : status === "error" ? (
            <div className="py-8 text-center">
              <p className="text-sm font-body text-foreground/20">{errorMessage || String(config.emptyMessage ?? "")}</p>
              <button
                type="button"
                onClick={() => setReloadKey((value) => value + 1)}
                className="mt-4 rounded-full liquid-glass px-4 py-2 text-xs font-medium text-foreground/70"
              >
                {String(config.retryLabel ?? "")}
              </button>
            </div>
          ) : !hasMonthData ? (
            <p className="py-8 text-center text-sm font-body text-foreground/20">
              {String(config.emptyMessage ?? "")}
            </p>
          ) : activeEvents.length > 0 ? (
            <div className="flex flex-col gap-3">
              {activeEvents.map((event, index) => {
                const item = typeConfig[event.type];
                const Icon = item.icon;

                return (
                  <motion.button
                    type="button"
                    key={`${event.href}-${index}`}
                    className={`group rounded-xl p-3 text-left transition-[background-color,border-color,box-shadow] ${event.href ? "hover:bg-[rgb(var(--shiro-panel-rgb)/0.16)] hover:shadow-[inset_0_1px_0_rgb(var(--shiro-accent-rgb)/0.04)]" : ""}`}
                    onClick={() => {
                      if (event.href) {
                        navigate(event.href);
                      }
                    }}
                    {...staggerItem(index, {
                      baseDelay: 0,
                      step: 0.05,
                      duration: 0.3,
                      reducedMotion: prefersReducedMotion,
                    })}
                  >
                    <div className="mb-1.5 flex items-center gap-2">
                      <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-body ${item.chipClass}`}>
                        <Icon className="h-3 w-3" />
                        {item.label}
                      </span>
                    </div>
                    <p className="text-sm font-body leading-snug text-foreground/70 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.88)]">
                      {event.title}
                    </p>
                  </motion.button>
                );
              })}
            </div>
          ) : (
            <p className="py-8 text-center text-sm font-body text-foreground/20">
              {selectedDate ? "这一天没有记录" : String(config.emptyMessage ?? "")}
            </p>
          )}
        </motion.div>
      </div>
    </PageShell>
  );
};

export default CalendarPage;
