import { useMemo, useRef, useEffect, useState } from "react";
import { useTheme } from "@/contexts/useTheme";
import { fetchActivityHeatmap, type PublicActivityHeatmapStats } from "@/lib/api";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";

interface WeeklyData {
  week: number;
  total: number;
  days: number[];
  month: string;
  label: string;
}

const generateWeeklyData = (): WeeklyData[] => {
  const weeks: WeeklyData[] = [];
  const now = new Date();
  for (let w = 51; w >= 0; w--) {
    const date = new Date(now);
    date.setDate(date.getDate() - w * 7);
    const month = date.toLocaleDateString("en-US", { month: "short" });
    const label = `${month} ${date.getDate()}`;
    const phase = Math.sin((52 - w) / 4.5) * 0.4 + 0.5;
    const noise = Math.random() * 0.6 + 0.2;
    const total = Math.max(0, Math.floor(phase * noise * 60));
    const days: number[] = [];
    let remaining = total;
    for (let d = 0; d < 7; d++) {
      if (d === 6) {
        days.push(remaining);
        break;
      }
      const dayVal = Math.floor(Math.random() * (remaining / (7 - d) * 2));
      days.push(Math.min(dayVal, remaining));
      remaining -= days[d];
    }
    weeks.push({ week: 51 - w, total, days, month, label });
  }
  return weeks;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const toNumber = (value: unknown, fallback = 0) => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }

  return fallback;
};

const toNumberArray = (value: unknown) =>
  Array.isArray(value) ? value.map((item) => toNumber(item, 0)) : [];

const extractArrayPayload = (payload: unknown) => {
  if (Array.isArray(payload)) {
    return payload;
  }

  if (!isRecord(payload)) {
    return [];
  }

  for (const key of ["weeks", "items", "data", "list", "results"]) {
    const value = payload[key];
    if (Array.isArray(value)) {
      return value;
    }
  }

  return [];
};

const normalizeWeek = (value: unknown, index: number): WeeklyData | null => {
  if (!isRecord(value)) {
    return null;
  }

  const weekStartValue =
    typeof value.week_start === "string"
      ? value.week_start
      : typeof value.weekStart === "string"
        ? value.weekStart
        : "";
  const weekStart = weekStartValue ? new Date(weekStartValue) : null;
  const isValidWeekStart = weekStart !== null && !Number.isNaN(weekStart.getTime());
  const month =
    typeof value.month_label === "string"
      ? value.month_label
      : typeof value.monthLabel === "string"
        ? value.monthLabel
        : isValidWeekStart
          ? weekStart.toLocaleDateString("en-US", { month: "short" })
          : "";
  const label =
    typeof value.label === "string"
      ? value.label
      : isValidWeekStart
        ? `${weekStart.toLocaleDateString("en-US", { month: "short" })} ${weekStart.getDate()}`
        : month
          ? `${month} ${index + 1}`
          : `Week ${index + 1}`;
  const total = toNumber(value.total ?? value.count ?? value.value, 0);
  const rawDays = toNumberArray(value.days ?? value.day_counts ?? value.dayCounts);
  const days = rawDays.length > 0 ? rawDays.slice(0, 7) : [];

  while (days.length < 7) {
    days.push(0);
  }

  return {
    week: toNumber(value.week ?? value.index ?? index, index),
    total,
    days,
    month,
    label,
  };
};

const normalizeHeatmapWeeks = (payload: unknown) =>
  extractArrayPayload(payload)
    .map((item, index) => normalizeWeek(item, index))
    .filter((item): item is WeeklyData => item !== null);

const WAVE_H = 180;
const COL_W = 22;
const COL_GAP = 2;
const PARTICLE_COUNT = 40;

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

const ActivityHeatmap = () => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<WeeklyData[]>(() => generateWeeklyData());
  const [remoteStats, setRemoteStats] = useState<PublicActivityHeatmapStats | null>(null);
  const [hoveredWeek, setHoveredWeek] = useState<number | null>(null);
  const [time, setTime] = useState(0);
  const prefersReducedMotion = useReducedMotionPreference();
  const totalWidth = data.length * (COL_W + COL_GAP) + 40;
  const maxVal = Math.max(...data.map((d) => d.total), 1);
  const totalContributions = remoteStats?.total_contributions ?? data.reduce((sum, d) => sum + d.total, 0);
  const peakWeek = remoteStats?.peak_week ?? maxVal;
  const averagePerWeek =
    remoteStats?.average_per_week ?? Math.round(totalContributions / Math.max(data.length, 1));
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  // Theme-aware colors
  const accentColor = isDark ? "140,170,255" : "60,100,200";
  const lineColor = isDark ? "200,220,255" : "40,80,180";
  const particleColor = isDark ? "white" : "hsl(222, 47%, 11%)";
  const gridLineColor = isDark ? "rgba(255,255,255,0.025)" : "rgba(0,0,0,0.04)";
  const tooltipBg = isDark ? "rgba(20,24,40,0.7)" : "rgba(255,255,255,0.85)";
  const tooltipStroke = isDark ? `rgba(${accentColor},0.15)` : `rgba(${accentColor},0.25)`;

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollLeft = scrollRef.current.scrollWidth;
    }
  }, [data.length]);

  useEffect(() => {
    let cancelled = false;

    const loadHeatmap = async () => {
      try {
        const payload = await fetchActivityHeatmap(52);
        const remoteWeeks = normalizeHeatmapWeeks(payload.weeks);
        if (!cancelled && remoteWeeks.length > 0) {
          setData(remoteWeeks);
          setRemoteStats(payload.stats);
        }
      } catch {
        // Keep the local generated fallback.
      }
    };

    void loadHeatmap();

    return () => {
      cancelled = true;
    };
  }, []);

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
  const fillPath = `${wavePath} L ${points[points.length - 1].x} ${WAVE_H + 10} L ${points[0].x} ${WAVE_H + 10} Z`;

  const particles = useMemo(() => {
    return Array.from({ length: PARTICLE_COUNT }, (_, i) => ({
      id: i,
      baseX: Math.random() * 52 * (COL_W + COL_GAP) + 20,
      baseY: Math.random() * WAVE_H,
      r: Math.random() * 1.5 + 0.5,
      speed: Math.random() * 0.5 + 0.3,
      phase: Math.random() * Math.PI * 2,
      opacity: Math.random() * 0.3 + 0.05,
    }));
  }, []);

  const monthMarkers: { label: string; x: number }[] = [];
  let lastMonth = "";
  data.forEach((d, i) => {
    if (d.month !== lastMonth) {
      monthMarkers.push({ label: d.month, x: i * (COL_W + COL_GAP) + COL_W / 2 + 20 });
      lastMonth = d.month;
    }
  });

  const dayLabels = ["一", "三", "五"];

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-body font-medium text-foreground/50 uppercase tracking-widest">
          Activity
        </h3>
        <span className="text-xs font-body text-foreground/30 tabular-nums">
          {totalContributions.toLocaleString()} contributions
        </span>
      </div>

      {/* Stats row */}
      <div className="flex items-center gap-6">
        {[
          { label: "This week", value: data[data.length - 1]?.total ?? 0 },
          { label: "Peak week", value: peakWeek },
          { label: "Avg / week", value: averagePerWeek },
        ].map((stat) => (
          <div key={stat.label} className="flex flex-col">
            <span className="text-xl font-body font-medium text-foreground tabular-nums">
              {stat.value}
            </span>
            <span className="text-[10px] font-body text-foreground/25 uppercase tracking-wider">
              {stat.label}
            </span>
          </div>
        ))}
      </div>

      {/* Wave chart */}
      <div
        ref={scrollRef}
        className="overflow-x-auto scrollbar-hide -mx-2 px-2"
        style={{ WebkitOverflowScrolling: "touch" }}
      >
        <svg width={totalWidth + 20} height={WAVE_H + 36} className="block">
          <defs>
            <linearGradient id="waveFillGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={`rgba(${accentColor},0.15)`} />
              <stop offset="50%" stopColor={`rgba(${accentColor},0.04)`} />
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

          {/* Grid lines */}
          {[0.25, 0.5, 0.75].map((r) => (
            <line
              key={r}
              x1={20}
              y1={WAVE_H - r * (WAVE_H - 40)}
              x2={totalWidth}
              y2={WAVE_H - r * (WAVE_H - 40)}
              stroke={gridLineColor}
              strokeDasharray="2 10"
            />
          ))}

          {/* Fill area */}
          <path d={fillPath} fill="url(#waveFillGrad)" />

          {/* Floating particles */}
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

          {/* Organic blobs */}
          {data.map((d, i) => {
            if (d.total < maxVal * 0.3) return null;
            const intensity = d.total / maxVal;
            const r = 4 + intensity * 8;
            const isHovered = hoveredWeek === i;
            return (
              <path
                key={`blob-${i}`}
                d={blobPath(points[i].x, points[i].y, isHovered ? r * 1.4 : r, i + displayTime * 0.5)}
                fill={`rgba(${accentColor},${isHovered ? 0.15 : 0.04 + intensity * 0.04})`}
                className="transition-opacity duration-300"
              />
            );
          })}

          {/* Wave line */}
          <path
            d={wavePath}
            fill="none"
            stroke={`rgba(${accentColor},0.12)`}
            strokeWidth={4}
            strokeLinecap="round"
          />
          <path
            d={wavePath}
            fill="none"
            stroke={`rgba(${lineColor},0.5)`}
            strokeWidth={1.5}
            strokeLinecap="round"
            filter="url(#waveGlow)"
          />

          {/* Interactive columns */}
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
                    stroke={`rgba(${accentColor},0.15)`}
                    strokeWidth={1}
                    strokeDasharray="2 4"
                  />
                )}
                <circle
                  cx={points[i].x}
                  cy={points[i].y}
                  r={isHovered ? 5 : d.total > maxVal * 0.5 ? 2 : 0}
                  fill={isHovered ? `rgba(${lineColor},0.9)` : `rgba(${lineColor},0.5)`}
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
                          fill={`rgba(${accentColor},${0.2 + (dayVal / Math.max(...d.days, 1)) * 0.4})`}
                        />
                      );
                    })}
                  </g>
                )}
              </g>
            );
          })}

          {/* Tooltip */}
          {hoveredWeek !== null && (
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
                className="fill-foreground/80 font-body"
                fontSize={10}
                fontWeight={500}
              >
                {data[hoveredWeek].total} · {data[hoveredWeek].label}
              </text>
            </g>
          )}

          {/* Month labels */}
          {monthMarkers.map((m, i) => (
            <text
              key={i}
              x={m.x}
              y={WAVE_H + 22}
              textAnchor="middle"
              className="fill-foreground/20 font-body"
              fontSize={9}
            >
              {m.label}
            </text>
          ))}

          {/* Day labels */}
          {dayLabels.map((label, i) => (
            <text
              key={label}
              x={12}
              y={WAVE_H - (i + 1) * (WAVE_H / 5) + 4}
              textAnchor="middle"
              className="fill-foreground/10 font-body"
              fontSize={8}
            >
              {label}
            </text>
          ))}
        </svg>
      </div>
    </div>
  );
};

export default ActivityHeatmap;
