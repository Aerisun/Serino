import { useMemo, useState } from "react";
import { motion } from "motion/react";
import { ChevronLeft, ChevronRight, FileText, BookOpen, Feather } from "lucide-react";
import { useNavigate } from "react-router-dom";
import PageShell from "@/components/PageShell";
import { staggerItem, transition } from "@/config";
import { usePageConfig } from "@/contexts/runtime-config";
import { useFrontendI18n, type FrontendLang } from "@/i18n";
import { useReadCalendarApiV1SiteCalendarGet } from "@serino/api-client/site";
import type { CalendarEventRead } from "@serino/api-client/models";
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
  selectedEmptyMessage?: string;
  postTypeLabel?: string;
  diaryTypeLabel?: string;
  excerptTypeLabel?: string;
}

const typeConfigBase = {
  post: {
    icon: FileText,
    chipClass: "bg-[rgb(var(--shiro-accent-rgb)/0.12)] text-[rgb(var(--shiro-accent-rgb)/0.88)]",
    dotClass: "bg-[rgb(var(--shiro-accent-rgb)/0.72)]",
  },
  diary: {
    icon: BookOpen,
    chipClass: "bg-[rgb(var(--shiro-accent-rgb)/0.1)] text-[rgb(var(--shiro-accent-rgb)/0.78)]",
    dotClass: "bg-[rgb(var(--shiro-accent-rgb)/0.5)]",
  },
  excerpt: {
    icon: Feather,
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

const normalizeCalendarEvent = (item: CalendarEventRead): CalendarEvent | null => {
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

const getWeekdayLabels = (
  value: unknown,
  t: (key: string, values?: Record<string, string | number>, fallback?: string) => string,
) => {
  if (Array.isArray(value) && value.length === 7) {
    return value.map(String);
  }

  return [
    t("calendar.weekdayMon"),
    t("calendar.weekdayTue"),
    t("calendar.weekdayWed"),
    t("calendar.weekdayThu"),
    t("calendar.weekdayFri"),
    t("calendar.weekdaySat"),
    t("calendar.weekdaySun"),
  ];
};

const getMonthLabels = (value: unknown, lang: FrontendLang) => {
  if (Array.isArray(value) && value.length === 12) {
    return value.map(String);
  }

  return Array.from({ length: 12 }, (_, index) =>
    new Intl.DateTimeFormat(lang === "zh" ? "zh-CN" : "en-US", { month: "short" }).format(
      new Date(2024, index, 1),
    ),
  );
};

const CalendarPage = () => {
  const { t, lang } = useFrontendI18n();
  const config = usePageConfig().calendar as unknown as CalendarPageConfig;
  const weekdayLabels = getWeekdayLabels(config.weekdayLabels, t);
  const monthLabels = getMonthLabels(config.monthLabels, lang);
  const loadingLabel = config.loadingLabel ?? t("calendar.loadingLabel");
  const retryLabel = config.retryLabel ?? t("calendar.retryLabel");
  const errorTitle = config.errorTitle ?? t("calendar.errorTitle");
  const selectedEmptyMessage = config.selectedEmptyMessage ?? t("calendar.selectedEmptyMessage");
  const typeConfig = {
    post: {
      ...typeConfigBase.post,
      label: config.postTypeLabel ?? t("calendar.postTypeLabel"),
    },
    diary: {
      ...typeConfigBase.diary,
      label: config.diaryTypeLabel ?? t("calendar.diaryTypeLabel"),
    },
    excerpt: {
      ...typeConfigBase.excerpt,
      label: config.excerptTypeLabel ?? t("calendar.excerptTypeLabel"),
    },
  } as const;
  const today = new Date();
  const navigate = useNavigate();
  const prefersReducedMotion = useReducedMotionPreference();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const MIN_YEAR = 2024;
  const MIN_MONTH = 0;
  const isAtMinMonth = year === MIN_YEAR && month <= MIN_MONTH;
  const isAtMaxMonth = year === today.getFullYear() && month >= today.getMonth();

  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfMonth(year, month);
  const rangeStart = formatDateKey(new Date(year, month, 1));
  const rangeEnd = formatDateKey(new Date(year, month + 1, 0));

  const { data: response, isLoading, isError, error, refetch } = useReadCalendarApiV1SiteCalendarGet({ from: rangeStart, to: rangeEnd });
  const calendarEvents = useMemo(
    () =>
      (response?.data?.events ?? [])
        .map((item) => normalizeCalendarEvent(item))
        .filter((item): item is CalendarEvent => item !== null),
    [response],
  );
  const status: "loading" | "ready" | "empty" | "error" = isLoading
    ? "loading"
    : isError
      ? "error"
      : calendarEvents.length > 0
        ? "ready"
        : "empty";
  const errorMessage = isError ? (error instanceof Error ? error.message : errorTitle) : "";

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
  const activeDayLabel = activeDate
    ? t("calendar.dayOfMonth", { day: parseInt(activeDate.split("-")[2], 10) })
    : String(config.todayLabel ?? t("calendar.today"));

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
              disabled={isAtMinMonth}
              onClick={() => {
                if (isAtMinMonth) return;
                if (month === 0) {
                  setMonth(11);
                  setYear((value) => value - 1);
                  return;
                }
                setMonth((value) => value - 1);
              }}
              className={`rounded-xl p-2 text-foreground/40 transition-colors hover:bg-[rgb(var(--shiro-panel-rgb)/0.2)] hover:text-[rgb(var(--shiro-accent-rgb)/0.84)] active:scale-95 ${isAtMinMonth ? "opacity-30 cursor-not-allowed" : ""}`}
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
            <h2 className="text-lg font-body font-medium text-foreground/80">
              {t("calendar.yearMonth", { year, month: monthLabels[month] })}
            </h2>
            <button
              type="button"
              disabled={isAtMaxMonth}
              onClick={() => {
                if (isAtMaxMonth) return;
                if (month === 11) {
                  setMonth(0);
                  setYear((value) => value + 1);
                  return;
                }
                setMonth((value) => value + 1);
              }}
              className={`rounded-xl p-2 text-foreground/40 transition-colors hover:bg-[rgb(var(--shiro-panel-rgb)/0.2)] hover:text-[rgb(var(--shiro-accent-rgb)/0.84)] active:scale-95 ${isAtMaxMonth ? "opacity-30 cursor-not-allowed" : ""}`}
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
            {activeDayLabel}
          </h3>

          {status === "loading" ? (
            <div className="flex flex-col gap-3">
              <div className="h-14 animate-pulse rounded-xl bg-foreground/[0.03]" />
              <div className="h-14 animate-pulse rounded-xl bg-foreground/[0.03]" />
              <div className="h-14 animate-pulse rounded-xl bg-foreground/[0.03]" />
              <p className="pt-1 text-center text-xs font-body text-foreground/20">
                {loadingLabel}
              </p>
            </div>
          ) : status === "error" ? (
            <div className="py-8 text-center">
              <p className="text-sm font-body text-foreground/20">
                {errorTitle}
              </p>
              <p className="mt-2 text-xs font-body text-foreground/20">
                {errorMessage || String(config.emptyMessage ?? "")}
              </p>
              <button
                type="button"
                onClick={() => void refetch()}
                className="mt-4 rounded-full liquid-glass px-4 py-2 text-xs font-medium text-foreground/70"
              >
                {retryLabel}
              </button>
            </div>
          ) : !hasMonthData ? (
            <p className="py-8 text-center text-sm font-body text-foreground/20">
              {String(config.emptyMessage ?? t("calendar.emptyMessage"))}
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
              {selectedDate ? selectedEmptyMessage : String(config.emptyMessage ?? t("calendar.emptyMessage"))}
            </p>
          )}
        </motion.div>
      </div>
    </PageShell>
  );
};

export default CalendarPage;
