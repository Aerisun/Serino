import { useMemo, useRef, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTheme } from "@serino/theme";
import {
  useReadActivityHeatmapApiV1SiteActivityHeatmapGet,
} from "@serino/api-client/site";
import type {
  ActivityHeatmapWeekRead,
} from "@serino/api-client/models";
import { CalendarDays } from "lucide-react";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import { useFrontendI18n } from "@/i18n";
import { usePageConfig } from "@/contexts/runtime-config";

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
const PARTICLE_COUNT = 40;
const ACCENT_FALLBACK = "60 100 200";
const PANEL_STRONG_FALLBACK = "255 255 255";
const BORDER_FALLBACK = "185 194 211";

const tokenRgb = (name: string, fallback: string, alpha: number) =>
  `rgb(var(${name}, ${fallback}) / ${alpha})`;

const blobPath = (cx: number, cy: number, r: number, seed: number) => {
  const pts = 6;
  const coords: string[] = [];
  for (let i = 0; i <= pts; i++) {
    const angle = (i / pts) * Math.PI * 2;
    const wobble = 1 + Math.sin(seed * 7 + i * 2.3) * 0.25 + Math.cos(seed * 3 + i * 1.7) * 0.15;
    const x = cx + Math.cos(angle) * r * wobble;
    const y = cy + Math.sin(angle) * r * wobble;
    coords.push(`${x},${y}`);
  }
  let d = `M ${coords[0]}`;
  for (let i = 1; i < coords.length; i++) {
    const prev = coords[i - 1].split(",").map(Number);
    const curr = coords[i].split(",").map(Number);
    const cpx = (prev[0] + curr[0]) / 2;
    const cpy = (prev[1] + curr[1]) / 2;
    d += ` Q ${prev[0]},${prev[1]} ${cpx},${cpy}`;
  }
  d += " Z";
  return d;
};

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

const ActivityHeatmap = () => {
  const { t } = useFrontendI18n();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [hoveredWeek, setHoveredWeek] = useState<number | null>(null);
  const [time, setTime] = useState(0);
  const prefersReducedMotion = useReducedMotionPreference();
  const { resolvedTheme } = useTheme();
  const config = (usePageConfig().activity as Record<string, unknown> | undefined) ?? {};
  const title = String(config.heatmapTitle ?? t("heatmap.title"));
  const stats = [
    { key: "thisWeek", label: String(config.heatmapThisWeekLabel ?? t("heatmap.thisWeek")) },
    { key: "peakWeek", label: String(config.heatmapPeakWeekLabel ?? t("heatmap.peakWeek")) },
    { key: "averageWeek", label: String(config.heatmapAverageWeekLabel ?? t("heatmap.avgPerWeek")) },
  ] as const;
  const isDark = resolvedTheme === "dark";

  const { data: response, isLoading, isError, refetch } = useReadActivityHeatmapApiV1SiteActivityHeatmapGet({
    weeks: 52,
    tz: "Asia/Shanghai",
  });
  const remoteWeeks = response?.data?.weeks;
  const data = useMemo(() => (remoteWeeks ? normalizeHeatmapWeeks(remoteWeeks) : []), [remoteWeeks]);
  const remoteStats = response?.data?.stats ?? null;
  const status: "loading" | "ready" | "empty" | "error" = isLoading
    ? "loading"
    : isError
      ? "error"
      : data.length > 0
        ? "ready"
        : "empty";

  const totalWidth = Math.max(data.length * (COL_W + COL_GAP) + 40, 160);
  const maxVal = Math.max(...data.map((d) => d.total), 1);
  const hasData = status === "ready" && data.length > 0;

  const accentSoft = tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.16);
  const accentGhost = tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.06);
  const lineColor = tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.88);
  const particleColor = isDark ? "rgba(255,255,255,0.42)" : "rgba(20,24,40,0.18)";
  const tooltipBg = tokenRgb("--shiro-panel-strong-rgb", PANEL_STRONG_FALLBACK, isDark ? 0.82 : 0.9);
  const tooltipStroke = tokenRgb("--shiro-border-rgb", BORDER_FALLBACK, isDark ? 0.44 : 0.58);
  const statValueColor = tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.86);
  const statLabelColor = tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.34);

  useEffect(() => {
    if (!hasData) {
      setHoveredWeek(null);
      return;
    }

    if (scrollRef.current) {
      scrollRef.current.scrollLeft = scrollRef.current.scrollWidth;
    }
  }, [hasData, data.length]);

  useEffect(() => {
    if (prefersReducedMotion) return;

    let raf: number;
    const tick = () => {
      setTime((t) => t + 0.008);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [prefersReducedMotion]);

  const displayTime = prefersReducedMotion ? 0 : time;
  const points = data.map((d, i) => ({
    x: i * (COL_W + COL_GAP) + COL_W / 2 + 20,
    y: WAVE_H - (d.total / maxVal) * (WAVE_H - 40) + Math.sin(displayTime + i * 0.3) * 2,
  }));

  const buildPath = (pts: { x: number; y: number }[]) => {
    if (pts.length < 2) return "";
    let p = `M ${pts[0].x} ${pts[0].y}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[Math.max(i - 1, 0)];
      const p1 = pts[i];
      const p2 = pts[i + 1];
      const p3 = pts[Math.min(i + 2, pts.length - 1)];
      const cp1x = p1.x + (p2.x - p0.x) / 6;
      const cp1y = p1.y + (p2.y - p0.y) / 6;
      const cp2x = p2.x - (p3.x - p1.x) / 6;
      const cp2y = p2.y - (p3.y - p1.y) / 6;
      p += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
    }
    return p;
  };

  const wavePath = buildPath(points);
  const fillPath =
    points.length > 0
      ? `${wavePath} L ${points[points.length - 1].x} ${WAVE_H + 10} L ${points[0].x} ${WAVE_H + 10} Z`
      : "";

  const particles = useMemo(() => {
    return Array.from({ length: PARTICLE_COUNT }, (_, i) => ({
      id: i,
      baseX: Math.random() * totalWidth,
      baseY: Math.random() * WAVE_H,
      r: Math.random() * 1.5 + 0.5,
      speed: Math.random() * 0.5 + 0.3,
      phase: Math.random() * Math.PI * 2,
      opacity: Math.random() * 0.3 + 0.05,
    }));
  }, [totalWidth]);

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
          className="inline-flex items-center gap-1.5 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.76] px-3 py-1.5 text-xs font-body font-medium text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.72)] transition hover:border-[rgb(var(--shiro-accent-rgb)/0.22)] hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.9)] dark:bg-card/[0.82]"
          aria-label={t("heatmap.calendarAria")}
        >
          <CalendarDays className="h-3.5 w-3.5" />
          {t("heatmap.calendar")}
        </Link>
      </div>

      <div className="relative flex flex-wrap items-end gap-x-8 gap-y-3 sm:gap-x-12">
        {[
          { label: stats[0].label, value: hasData ? thisWeek : "—" },
          { label: stats[1].label, value: hasData ? peakWeek : "—" },
          { label: stats[2].label, value: hasData ? averagePerWeekLabel : "—" },
        ].map((stat) => (
          <div key={stat.label} className="min-w-[6.5rem]">
            <span className="block text-xl font-body font-medium tabular-nums" style={{ color: statValueColor }}>
              {stat.value}
            </span>
            <span
              className="text-[10px] font-body uppercase tracking-wider"
              style={{ color: statLabelColor }}
            >
              {stat.label}
            </span>
          </div>
        ))}
      </div>

      <div className="relative pt-1">
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
              <filter id="dotGlow">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <clipPath id="waveClip">
                <path d={fillPath} />
              </clipPath>
            </defs>

            {hasData && (
              <>
                <path d={fillPath} fill="url(#waveFillGrad)" />

                <g clipPath="url(#waveClip)">
                  {particles.map((p) => {
                    const px = p.baseX + Math.sin(displayTime * p.speed + p.phase) * 8;
                    const py = p.baseY + Math.cos(displayTime * p.speed * 0.7 + p.phase) * 12;
                    return (
                      <circle
                        key={p.id}
                        cx={px}
                        cy={py}
                        r={p.r}
                        fill={particleColor}
                        opacity={p.opacity + Math.sin(displayTime * 2 + p.phase) * 0.05}
                      />
                    );
                  })}
                </g>

                {data.map((d, i) => {
                  if (d.total < maxVal * 0.3) return null;
                  const intensity = d.total / maxVal;
                  const r = 4 + intensity * 8;
                  const isHovered = hoveredWeek === i;
                  return (
                    <path
                      key={`blob-${i}`}
                      d={blobPath(points[i].x, points[i].y, isHovered ? r * 1.4 : r, i + displayTime * 0.5)}
                      fill={tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, isHovered ? 0.15 : 0.04 + intensity * 0.05)}
                      className="transition-opacity duration-300"
                    />
                  );
                })}

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
                        <line
                          x1={points[i].x}
                          y1={points[i].y}
                          x2={points[i].x}
                          y2={WAVE_H}
                          stroke={tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.18)}
                          strokeWidth={1}
                          strokeDasharray="2 4"
                        />
                      )}
                      <circle
                        cx={points[i].x}
                        cy={points[i].y}
                        r={isHovered ? 5 : d.total > maxVal * 0.5 ? 2 : 0}
                        fill={isHovered ? lineColor : tokenRgb("--shiro-accent-rgb", ACCENT_FALLBACK, 0.6)}
                        filter={isHovered ? "url(#dotGlow)" : undefined}
                        className="transition-all duration-200"
                      />
                      {isHovered && d.days && (
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
                  );
                })}

                {hoveredWeek !== null && points[hoveredWeek] && (
                  <g>
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
