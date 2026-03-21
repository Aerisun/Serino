import { useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import { ChevronLeft, ChevronRight, FileText, BookOpen, Feather } from "lucide-react";
import { useNavigate } from "react-router-dom";
import PageShell from "@/components/PageShell";
import { staggerItem, transition } from "@/config";
import { usePageConfig } from "@/contexts/RuntimeConfigContext";
import { fetchPublicCalendar, type PublicCalendarEvent } from "@/lib/api";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";

interface CalendarEvent {
  date: string; // YYYY-MM-DD
  type: "post" | "diary" | "excerpt";
  title: string;
  href?: string;
}

const LOCAL_EVENTS: CalendarEvent[] = [
  { date: "2026-03-21", type: "post", title: "从零搭建个人设计系统的完整思路" },
  { date: "2026-03-20", type: "diary", title: "春分，天气转暖" },
  { date: "2026-03-18", type: "post", title: "液态玻璃效果的 CSS 实现与优化" },
  { date: "2026-03-17", type: "excerpt", title: "「人间词话」摘录" },
  { date: "2026-03-15", type: "diary", title: "读完了一本好书" },
  { date: "2026-03-14", type: "post", title: "为什么我选择做独立设计师" },
  { date: "2026-03-12", type: "diary", title: "和朋友聊了很久" },
  { date: "2026-03-10", type: "excerpt", title: "木心《文学回忆录》" },
  { date: "2026-03-08", type: "post", title: "React 19 中值得关注的设计模式变化" },
  { date: "2026-03-05", type: "diary", title: "惊蛰，听到了第一声春雷" },
  { date: "2026-03-03", type: "excerpt", title: "加缪《局外人》节选" },
  { date: "2026-03-01", type: "post", title: "网页排版中的节奏感：间距与留白" },
  { date: "2026-02-28", type: "diary", title: "二月的最后一天" },
  { date: "2026-02-25", type: "post", title: "用 Framer Motion 做有质感的页面过渡" },
  { date: "2026-02-22", type: "excerpt", title: "博尔赫斯《沙之书》" },
  { date: "2026-02-20", type: "diary", title: "雨水，细雨绵绵" },
  { date: "2026-02-15", type: "post", title: "深色模式设计的七个容易忽略的细节" },
];

const typeConfig = {
  post: { icon: FileText, label: "帖子", color: "bg-blue-500/20 text-blue-300" },
  diary: { icon: BookOpen, label: "日记", color: "bg-emerald-500/20 text-emerald-300" },
  excerpt: { icon: Feather, label: "文摘", color: "bg-amber-500/20 text-amber-300" },
};
function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number) {
  const day = new Date(year, month, 1).getDay();
  return day === 0 ? 6 : day - 1; // Monday = 0
}

const normalizeDateKey = (value: unknown) => {
  if (typeof value !== "string" || !value) {
    return "";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }

  const year = parsed.getFullYear();
  const month = String(parsed.getMonth() + 1).padStart(2, "0");
  const day = String(parsed.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const normalizeType = (value: unknown): CalendarEvent["type"] | null => {
  if (typeof value !== "string") {
    return null;
  }

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

const CalendarPage = () => {
  const config = usePageConfig().calendar as Record<string, any>;
  const WEEKDAYS = (config.weekdayLabels ?? []) as string[];
  const MONTHS = (config.monthLabels ?? []) as string[];
  const today = new Date();
  const navigate = useNavigate();
  const prefersReducedMotion = useReducedMotionPreference();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [calendarEvents, setCalendarEvents] = useState<CalendarEvent[]>(LOCAL_EVENTS);

  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfMonth(year, month);

  useEffect(() => {
    let cancelled = false;

    const loadCalendarEvents = async () => {
      try {
        const payload = await fetchPublicCalendar(undefined, undefined);
        const remoteEvents = payload.events
          .map((item) => normalizeCalendarEvent(item))
          .filter((item): item is CalendarEvent => item !== null);
        if (!cancelled && remoteEvents.length > 0) {
          setCalendarEvents(remoteEvents);
        }
      } catch {
        // Keep the local mock fallback.
      }
    };

    void loadCalendarEvents();

    return () => {
      cancelled = true;
    };
  }, []);

  const eventMap = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {};
    calendarEvents.forEach((e) => {
      if (!map[e.date]) map[e.date] = [];
      map[e.date].push(e);
    });
    return map;
  }, [calendarEvents]);

  const selectedEvents = selectedDate ? eventMap[selectedDate] || [] : [];

  const prevMonth = () => {
    if (month === 0) { setMonth(11); setYear(y => y - 1); }
    else setMonth(m => m - 1);
  };

  const nextMonth = () => {
    if (month === 11) { setMonth(0); setYear(y => y + 1); }
    else setMonth(m => m + 1);
  };

  const formatDateKey = (day: number) =>
    `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

  const todayKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  const activeEvents = selectedDate ? selectedEvents : eventMap[todayKey] || [];

  const cells: (number | null)[] = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
    >

        <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_280px]">
          {/* Calendar grid */}
          <motion.div
            className="liquid-glass rounded-2xl p-6"
            initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={transition({
              duration: config.motion.duration,
              delay: config.motion.delay,
              reducedMotion: prefersReducedMotion,
            })}
          >
            {/* Month navigation */}
            <div className="flex items-center justify-between mb-6">
              <button
                onClick={prevMonth}
                className="p-2 rounded-xl text-foreground/40 hover:text-foreground/70 hover:bg-foreground/5 transition-colors active:scale-95"
              >
                <ChevronLeft className="h-5 w-5" />
              </button>
              <h2 className="text-lg font-body font-medium text-foreground/80">
                {year} 年 {MONTHS[month]}
              </h2>
              <button
                onClick={nextMonth}
                className="p-2 rounded-xl text-foreground/40 hover:text-foreground/70 hover:bg-foreground/5 transition-colors active:scale-95"
              >
                <ChevronRight className="h-5 w-5" />
              </button>
            </div>

            {/* Weekday headers */}
            <div className="grid grid-cols-7 mb-2">
              {WEEKDAYS.map((d) => (
                <div key={d} className="text-center text-xs font-body text-foreground/25 py-2">
                  {d}
                </div>
              ))}
            </div>

            {/* Day cells */}
            <div className="grid grid-cols-7 gap-1">
              {cells.map((day, i) => {
                if (day === null) return <div key={`empty-${i}`} />;
                const dateKey = formatDateKey(day);
                const dayEvents = eventMap[dateKey] || [];
                const isToday = dateKey === todayKey;
                const isSelected = dateKey === selectedDate;

                return (
                  <button
                    key={dateKey}
                    onClick={() => setSelectedDate(isSelected ? null : dateKey)}
                    className={`relative aspect-square rounded-xl flex flex-col items-center justify-center gap-0.5 transition-all active:scale-95 ${
                      isSelected
                        ? "bg-foreground/15 ring-1 ring-foreground/20"
                        : isToday
                        ? "bg-foreground/8"
                        : "hover:bg-foreground/5"
                    }`}
                  >
                    <span
                      className={`text-sm font-body tabular-nums ${
                        isToday
                          ? "text-foreground font-medium"
                          : dayEvents.length > 0
                          ? "text-foreground/70"
                          : "text-foreground/30"
                      }`}
                    >
                      {day}
                    </span>
                    {dayEvents.length > 0 && (
                      <div className="flex gap-0.5">
                        {dayEvents.map((e, j) => (
                          <span
                            key={j}
                            className={`w-1 h-1 rounded-full ${
                              e.type === "post"
                                ? "bg-blue-400/70"
                                : e.type === "diary"
                                ? "bg-emerald-400/70"
                                : "bg-amber-400/70"
                            }`}
                          />
                        ))}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Legend */}
            <div className="flex items-center gap-4 mt-6 pt-4 border-t border-foreground/5">
              {Object.entries(typeConfig).map(([key, cfg]) => (
                <div key={key} className="flex items-center gap-1.5">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      key === "post" ? "bg-blue-400/70" : key === "diary" ? "bg-emerald-400/70" : "bg-amber-400/70"
                    }`}
                  />
                  <span className="text-[11px] font-body text-foreground/30">{cfg.label}</span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Side panel — selected date events */}
          <motion.div
            className="liquid-glass rounded-2xl p-5 h-fit lg:sticky lg:top-24"
            initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={transition({
              duration: config.motion.duration,
              delay: 0.16,
              reducedMotion: prefersReducedMotion,
            })}
          >
            <h3 className="text-xs font-body uppercase tracking-widest text-foreground/30 mb-4">
              {selectedDate
                ? `${parseInt(selectedDate.split("-")[2])} 日`
                : "今日"}
            </h3>

            {activeEvents.length > 0 ? (
              <div className="flex flex-col gap-3">
                {activeEvents.map((e, i) => {
                  const cfg = typeConfig[e.type];
                  const Icon = cfg.icon;
                  return (
                    <motion.button
                      type="button"
                      key={i}
                      className="group cursor-pointer rounded-xl p-3 hover:bg-foreground/5 transition-colors"
                      onClick={() => {
                        if (e.href) {
                          navigate(e.href);
                        }
                      }}
                      {...staggerItem(i, {
                        baseDelay: 0,
                        step: 0.05,
                        duration: 0.3,
                        reducedMotion: prefersReducedMotion,
                      })}
                    >
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-body ${cfg.color}`}>
                          <Icon className="h-3 w-3" />
                          {cfg.label}
                        </span>
                      </div>
                      <p className="text-sm font-body text-foreground/70 group-hover:text-foreground/90 transition-colors leading-snug">
                        {e.title}
                      </p>
                    </motion.button>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm font-body text-foreground/20 py-8 text-center">
                {selectedDate ? "这一天没有记录" : "今天还没有记录"}
              </p>
            )}
          </motion.div>
        </div>
    </PageShell>
  );
};

export default CalendarPage;
