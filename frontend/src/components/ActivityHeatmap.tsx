import { useMemo, useRef, useEffect, useLayoutEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useTheme } from "@serino/theme";
import {
  useReadActivityHeatmapApiV1SiteActivityHeatmapGet,
} from "@serino/api-client/site";
import type {
  ActivityHeatmapWeekRead,
} from "@serino/api-client/models";
import { CalendarDays } from "lucide-react";
import { useDeferredActivation } from "@/hooks/useDeferredActivation";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import { useFrontendI18n } from "@/i18n";
import { usePageConfig } from "@/contexts/runtime-config";
import { warmInternalHref } from "@/lib/route-preload";

interface WeeklyData {
  week: number;
  total: number;
  days: number[];
  month: string;
  label: string;
}

const normalizeHeatmapWeeks = (weeks: ActivityHeatmapWeekRead[]): WeeklyData[] =>
  weeks.map((week, index) => ({
    week: index,
    total: week.total,
    days: Array.from({ length: 7 }, (_, dayIndex) => Math.max(0, week.days[dayIndex] ?? 0)),
    month: week.month_label,
    label: week.label,
  }));

const WAVE_H = 180;
const COL_W = 22;
const COL_GAP = 2;
const DESKTOP_MOTION_QUERY = "(min-width: 768px) and (hover: hover) and (pointer: fine)";
const DESKTOP_FRAME_INTERVAL_MS = 1000 / 60;
const MOBILE_FRAME_INTERVAL_MS = 1000 / 30;
const DESKTOP_WAVE_AMPLITUDE = 10;
const MOBILE_WAVE_AMPLITUDE = 2;
const DESKTOP_WAVE_SPEED = 0.65;
const MOBILE_WAVE_SPEED = 0.48;
const ACCENT_FALLBACK = "60 100 200";
const PANEL_STRONG_FALLBACK = "255 255 255";
const BORDER_FALLBACK = "185 194 211";

const tokenRgb = (name: string, fallback: string, alpha: number) =>
  `rgb(var(${name}, ${fallback}) / ${alpha})`;

const buildMonthMarkers = (weeks: WeeklyData[]) => {
  const markers: Array<{ label: string; x: number }> = [];
  let lastMonth = "";
  weeks.forEach((week, index) => {
    if (week.month !== lastMonth) {
      markers.push({ label: week.month, x: index * (COL_W + COL_GAP) + COL_W / 2 + 20 });
      lastMonth = week.month;
    }
  });
  return markers;
};

interface WavePoint {
  x: number;
  y: number;
}

const buildCubicBezierPath = (points: readonly WavePoint[]) => {
  if (points.length < 2) return "";

  let path = `M ${points[0].x} ${points[0].y}`;
  for (let index = 0; index < points.length - 1; index++) {
    const p0 = points[Math.max(index - 1, 0)];
    const p1 = points[index];
    const p2 = points[index + 1];
    const p3 = points[Math.min(index + 2, points.length - 1)];
    const controlPoint1X = p1.x + (p2.x - p0.x) / 6;
    const controlPoint1Y = p1.y + (p2.y - p0.y) / 6;
    const controlPoint2X = p2.x - (p3.x - p1.x) / 6;
    const controlPoint2Y = p2.y - (p3.y - p1.y) / 6;

    path += ` C ${controlPoint1X} ${controlPoint1Y}, ${controlPoint2X} ${controlPoint2Y}, ${p2.x} ${p2.y}`;
  }

  return path;
};

const matchesDesktopMotion = () =>
  typeof window === "undefined"
  || typeof window.matchMedia !== "function"
  || window.matchMedia(DESKTOP_MOTION_QUERY).matches;

const useDesktopMotion = () => {
  const [isDesktopMotion, setIsDesktopMotion] = useState(matchesDesktopMotion);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;

    const media = window.matchMedia(DESKTOP_MOTION_QUERY);
    const update = () => setIsDesktopMotion(media.matches);

    update();
    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", update);
      return () => media.removeEventListener("change", update);
    }

    media.addListener(update);
    return () => media.removeListener(update);
  }, []);

  return isDesktopMotion;
};

const usePageVisibility = () => {
  const [isPageVisible, setIsPageVisible] = useState(
    () => typeof document === "undefined" || !document.hidden,
  );

  useEffect(() => {
    const update = () => setIsPageVisible(!document.hidden);

    update();
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);

  return isPageVisible;
};

const useElementVisibility = <T extends Element>() => {
  const ref = useRef<T>(null);
  const [isVisible, setIsVisible] = useState(() => typeof IntersectionObserver === "undefined");

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (typeof IntersectionObserver === "undefined") {
      setIsVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => setIsVisible(entry?.isIntersecting ?? false),
      { threshold: 0 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return [ref, isVisible] as const;
};

const useAnimationTime = (active: boolean, frameIntervalMs: number) => {
  const [time, setTime] = useState(0);

  useEffect(() => {
    if (!active) return;

    let animationFrame = 0;
    let lastUpdate = performance.now();
    const tick = (now: number) => {
      if (now - lastUpdate >= frameIntervalMs) {
        setTime((current) => current + Math.min((now - lastUpdate) / 1000, 0.1));
        lastUpdate = now;
      }
      animationFrame = requestAnimationFrame(tick);
    };

    animationFrame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animationFrame);
  }, [active, frameIntervalMs]);

  return time;
};

interface ActivityHeatmapProps {
  enabled?: boolean;
}

const ActivityHeatmap = ({ enabled = true }: ActivityHeatmapProps) => {
  const { t } = useFrontendI18n();
  const queryClient = useQueryClient();
  const pages = usePageConfig();
  const queryEnabled = useDeferredActivation(enabled, [enabled]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [chartViewportRef, isChartVisible] = useElementVisibility<HTMLDivElement>();
  const [hoveredWeek, setHoveredWeek] = useState<number | null>(null);
  const prefersReducedMotion = useReducedMotionPreference();
  const isDesktopMotion = useDesktopMotion();
  const isPageVisible = usePageVisibility();
  const { resolvedTheme } = useTheme();
  const config = (pages.activity as Record<string, unknown> | undefined) ?? {};
  const title = String(config.heatmapTitle ?? t("heatmap.title"));
  const stats = [
    { key: "thisWeek", label: String(config.heatmapThisWeekLabel ?? t("heatmap.thisWeek")) },
    { key: "peakWeek", label: String(config.heatmapPeakWeekLabel ?? t("heatmap.peakWeek")) },
    { key: "averageWeek", label: String(config.heatmapAverageWeekLabel ?? t("heatmap.avgPerWeek")) },
  ] as const;
  const isDark = resolvedTheme === "dark";

  const { data: response, isLoading, isError, refetch } =
    useReadActivityHeatmapApiV1SiteActivityHeatmapGet(
      {
        weeks: 52,
        tz: "Asia/Shanghai",
      },
      {
        query: {
          enabled: queryEnabled,
          staleTime: 5 * 60_000,
          gcTime: 20 * 60_000,
        },
      },
    );
  const remoteWeeks = response?.data?.weeks;
  const data = useMemo(() => (remoteWeeks ? normalizeHeatmapWeeks(remoteWeeks) : []), [remoteWeeks]);
  const remoteStats = response?.data?.stats ?? null;
  const status: "loading" | "ready" | "empty" | "error" = isLoading
    || (enabled && !queryEnabled && !response?.data)
    ? "loading"
    : isError
      ? "error"
      : data.length > 0
        ? "ready"
        : "empty";

  const totalWidth = Math.max(data.length * (COL_W + COL_GAP) + 40, 160);
  const maxVal = Math.max(...data.map((d) => d.total), 1);
  const hasData = status === "ready" && data.length > 0;
  const shouldAnimate = hasData && isChartVisible && isPageVisible && !prefersReducedMotion;
  const frameIntervalMs = isDesktopMotion ? DESKTOP_FRAME_INTERVAL_MS : MOBILE_FRAME_INTERVAL_MS;
  const time = useAnimationTime(shouldAnimate, frameIntervalMs);

  const accentSoft = tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.16);
  const accentGhost = tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.06);
  const lineColor = tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.88);
  const tooltipBg = tokenRgb("--shiro-panel-strong-rgb", PANEL_STRONG_FALLBACK, isDark ? 0.82 : 0.9);
  const tooltipStroke = tokenRgb("--shiro-border-rgb", BORDER_FALLBACK, isDark ? 0.44 : 0.58);
  const statValueColor = tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.86);
  const statLabelColor = tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.34);

  useLayoutEffect(() => {
    if (!hasData) {
      setHoveredWeek(null);
      return;
    }

    const viewport = scrollRef.current;
    if (!viewport) return;

    const alignToNewestWeek = () => {
      viewport.scrollLeft = viewport.scrollWidth - viewport.clientWidth;
    };

    alignToNewestWeek();
    const frameId = requestAnimationFrame(alignToNewestWeek);
    return () => cancelAnimationFrame(frameId);
  }, [hasData, data.length]);

  const displayTime = prefersReducedMotion ? 0 : time;
  const waveAmplitude = isDesktopMotion ? DESKTOP_WAVE_AMPLITUDE : MOBILE_WAVE_AMPLITUDE;
  const waveSpeed = isDesktopMotion ? DESKTOP_WAVE_SPEED : MOBILE_WAVE_SPEED;
  const points = data.map((d, i) => {
    const baseY = WAVE_H - (d.total / maxVal) * (WAVE_H - 40);
    const animatedY = baseY + Math.sin(displayTime * waveSpeed + i * 0.3) * waveAmplitude;
    return {
      x: i * (COL_W + COL_GAP) + COL_W / 2 + 20,
      y: animatedY,
    };
  });
  const wavePath = buildCubicBezierPath(points);
  const fillPath =
    wavePath
      ? `${wavePath} L ${points[points.length - 1].x} ${WAVE_H + 10} L ${points[0].x} ${WAVE_H + 10} Z`
      : "";

  const monthMarkers = useMemo(() => buildMonthMarkers(data), [data]);
  const thisWeek = data[data.length - 1]?.total ?? 0;
  const peakWeek = remoteStats?.peak_week ?? 0;
  const averagePerWeek = remoteStats?.average_per_week ?? 0;
  const averagePerWeekLabel = averagePerWeek.toLocaleString(undefined, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });

  return (
    <div className="relative flex flex-col gap-4">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-32"
        style={{
          background:
            "radial-gradient(ellipse 60% 80% at 50% 0%, rgb(var(--shiro-glow-rgb, 180 198 255) / 0.16) 0%, transparent 72%)",
        }}
      />

      <div className="relative flex items-baseline justify-between gap-4">
        <h3 className="text-sm font-body font-medium uppercase tracking-[0.28em] text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.68)]">
          {title}
        </h3>
        <Link
          to="/calendar"
          onMouseEnter={() => {
            void warmInternalHref({ href: "/calendar", queryClient, pages });
          }}
          onFocus={() => {
            void warmInternalHref({ href: "/calendar", queryClient, pages });
          }}
          onTouchStart={() => {
            void warmInternalHref({ href: "/calendar", queryClient, pages });
          }}
          className="inline-flex items-center gap-1.5 px-1 py-1.5 text-xs font-body font-medium text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.72)] transition hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.9)]"
          aria-label={t("heatmap.calendarAria")}
        >
          <CalendarDays className="h-3.5 w-3.5" />
          {t("heatmap.calendar")}
        </Link>
      </div>

      <div className="relative grid grid-flow-col auto-cols-max justify-start items-end gap-x-6 sm:gap-x-10 md:gap-x-14 lg:gap-x-20">
        {[
          { label: stats[0].label, value: hasData ? thisWeek : "—" },
          { label: stats[1].label, value: hasData ? peakWeek : "—" },
          { label: stats[2].label, value: hasData ? averagePerWeekLabel : "—" },
        ].map((stat) => (
          <div key={stat.label} className="min-w-0 whitespace-nowrap">
            <span className="block text-xl font-body font-medium tabular-nums" style={{ color: statValueColor }}>
              {stat.value}
            </span>
            <span
              className="block text-[10px] font-body uppercase tracking-wider"
              style={{ color: statLabelColor }}
            >
              {stat.label}
            </span>
          </div>
        ))}
      </div>

      <div ref={chartViewportRef} className="relative pt-1">
        <div
          ref={scrollRef}
          className="scrollbar-hide -mx-2 overflow-x-auto px-2"
          style={{ WebkitOverflowScrolling: "touch" }}
        >
          <svg width={totalWidth + 20} height={WAVE_H + 40} className="block">
            <defs>
              <linearGradient id="waveFillGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={accentSoft} />
                <stop offset="50%" stopColor={accentGhost} />
                <stop offset="100%" stopColor="transparent" />
              </linearGradient>
              <filter id="waveGlow">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <filter id="dotGlow" x="-150%" y="-150%" width="400%" height="400%">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {hasData && (
              <>
                <path d={fillPath} fill="url(#waveFillGrad)" />

                <path
                  d={wavePath}
                  fill="none"
                  stroke={tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.14)}
                  strokeWidth={4}
                  strokeLinecap="round"
                />
                <path
                  d={wavePath}
                  fill="none"
                  stroke={lineColor}
                  strokeWidth={1.5}
                  strokeLinecap="round"
                  filter="url(#waveGlow)"
                />

                {data.map((d, i) => {
                  const x = i * (COL_W + COL_GAP) + 20;
                  const isHovered = hoveredWeek === i;
                  return (
                    <g key={i}>
                      <rect
                        x={x}
                        y={0}
                        width={COL_W}
                        height={WAVE_H}
                        fill="transparent"
                        onMouseEnter={() => setHoveredWeek(i)}
                        onMouseLeave={() => setHoveredWeek(null)}
                        style={{ cursor: "crosshair" }}
                      />
                      {isHovered && (
                        <g pointerEvents="none">
                          <line
                            x1={points[i].x}
                            y1={points[i].y}
                            x2={points[i].x}
                            y2={WAVE_H}
                            stroke={tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.18)}
                            strokeWidth={1}
                            strokeDasharray="2 4"
                          />
                          {d.days && (
                            <g>
                              {d.days.map((dayVal, di) => {
                                const barH = (dayVal / Math.max(...d.days, 1)) * 24;
                                const bx = points[i].x - 10.5 + di * 3.5;
                                const by = WAVE_H - 2 - barH;
                                return (
                                  <rect
                                    key={di}
                                    x={bx}
                                    y={by}
                                    width={2.5}
                                    height={barH}
                                    rx={1.25}
                                    fill={tokenRgb(
                                      "--shiro-accent-rgb",
                                      ACCENT_FALLBACK,
                                      0.2 + (dayVal / Math.max(...d.days, 1)) * 0.42,
                                    )}
                                  />
                                );
                              })}
                            </g>
                          )}
                        </g>
                      )}
                      <circle
                        pointerEvents="none"
                        cx={points[i].x}
                        cy={points[i].y}
                        r={isHovered ? 5 : d.total > maxVal * 0.5 ? 2 : 0}
                        fill={isHovered ? lineColor : tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.6)}
                        filter={isHovered ? "url(#dotGlow)" : undefined}
                        className="transition-all duration-200"
                      />
                    </g>
                  );
                })}

                {hoveredWeek !== null && points[hoveredWeek] && (
                  <g pointerEvents="none">
                    <rect
                      x={points[hoveredWeek].x - 44}
                      y={points[hoveredWeek].y - 38}
                      width={88}
                      height={26}
                      rx={13}
                      fill={tooltipBg}
                      stroke={tooltipStroke}
                      strokeWidth={0.5}
                    />
                    <text
                      x={points[hoveredWeek].x}
                      y={points[hoveredWeek].y - 21}
                      textAnchor="middle"
                      className="font-body"
                      fill={tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.78)}
                      fontSize={10}
                      fontWeight={500}
                    >
                      {data[hoveredWeek].total} · {data[hoveredWeek].label}
                    </text>
                  </g>
                )}

                {monthMarkers.map((m, i) => (
                  <text
                    key={i}
                    x={m.x}
                    y={WAVE_H + 22}
                    textAnchor="middle"
                    className="font-body"
                    fill={tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.2)}
                    fontSize={9}
                  >
                    {m.label}
                  </text>
                ))}
              </>
            )}
          </svg>
        </div>

        {status === "error" && (
          <div className="pointer-events-none absolute right-2 top-2">
            <button
              type="button"
              onClick={() => void refetch()}
              className="pointer-events-auto rounded-full border px-3 py-1 text-[10px] transition-colors"
              style={{
                borderColor: tokenRgb("--shiro-border-rgb", BORDER_FALLBACK, isDark ? 0.42 : 0.56),
                color: tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.66),
              }}
            >
              {t("heatmap.retry")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ActivityHeatmap;
