import { useMemo, useRef, useEffect, useState } from "react";
import { useTheme } from "@/contexts/useTheme";
import {
  fetchActivityHeatmap,
  type PublicActivityHeatmapStats,
  type PublicActivityHeatmapWeek,
} from "@/lib/api";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";

interface WeeklyData {
  week: number;
  total: number;
  days: number[];
  month: string;
  label: string;
}

const normalizeHeatmapWeeks = (weeks: PublicActivityHeatmapWeek[]): WeeklyData[] =>
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
  const scrollRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<WeeklyData[]>([]);
  const [remoteStats, setRemoteStats] = useState<PublicActivityHeatmapStats | null>(null);
  const [hoveredWeek, setHoveredWeek] = useState<number | null>(null);
  const [time, setTime] = useState(0);
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const prefersReducedMotion = useReducedMotionPreference();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const totalWidth = Math.max(data.length * (COL_W + COL_GAP) + 40, 160);
  const maxVal = Math.max(...data.map((d) => d.total), 1);
  const hasData = status === "ready" && data.length > 0;

  const accentColor = isDark ? "140,170,255" : "60,100,200";
  const lineColor = isDark ? "200,220,255" : "40,80,180";
  const particleColor = isDark ? "white" : "hsl(222, 47%, 11%)";
  const gridLineColor = isDark ? "rgba(255,255,255,0.025)" : "rgba(0,0,0,0.04)";
  const tooltipBg = isDark ? "rgba(20,24,40,0.7)" : "rgba(255,255,255,0.85)";
  const tooltipStroke = isDark ? `rgba(${accentColor},0.15)` : `rgba(${accentColor},0.25)`;

  useEffect(() => {
    const controller = new AbortController();

    const loadHeatmap = async () => {
      setStatus("loading");
      setErrorMessage("");

      try {
        const payload = await fetchActivityHeatmap(52, { signal: controller.signal });
        if (controller.signal.aborted) {
          return;
        }

        const remoteWeeks = normalizeHeatmapWeeks(payload.weeks);
        setData(remoteWeeks);
        setRemoteStats(payload.stats);
        setStatus(remoteWeeks.length > 0 ? "ready" : "empty");
      } catch (error) {
        if (!controller.signal.aborted) {
          setData([]);
          setRemoteStats(null);
          setStatus("error");
          setErrorMessage(error instanceof Error ? error.message : "热力图加载失败");
        }
      }
    };

    void loadHeatmap();

    return () => {
      controller.abort();
    };
  }, [reloadKey]);

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
  }, [data.length, totalWidth]);

  const monthMarkers = useMemo(() => buildMonthMarkers(data), [data]);
  const dayLabels = ["一", "三", "五"];
  const totalContributions = remoteStats?.total_contributions ?? 0;
  const thisWeek = data[data.length - 1]?.total ?? 0;
  const peakWeek = remoteStats?.peak_week ?? 0;
  const averagePerWeek = remoteStats?.average_per_week ?? 0;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-body font-medium text-foreground/50 uppercase tracking-widest">
          Activity
        </h3>
        <span className="text-xs font-body text-foreground/30 tabular-nums">
          {status === "loading"
            ? "加载中"
            : status === "error"
              ? "加载失败"
              : `${totalContributions.toLocaleString()} contributions`}
        </span>
      </div>

      <div className="flex items-center gap-6">
        {[
          { label: "This week", value: hasData ? thisWeek : "—" },
          { label: "Peak week", value: hasData ? peakWeek : "—" },
          { label: "Avg / week", value: hasData ? averagePerWeek : "—" },
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

      <div className="relative">
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
                      fill={`rgba(${accentColor},${isHovered ? 0.15 : 0.04 + intensity * 0.04})`}
                      className="transition-opacity duration-300"
                    />
                  );
                })}

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
                      className="fill-foreground/80 font-body"
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
                    className="fill-foreground/20 font-body"
                    fontSize={9}
                  >
                    {m.label}
                  </text>
                ))}

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
              </>
            )}
          </svg>
        </div>

        {status === "error" && (
          <div className="pointer-events-none absolute right-2 top-2">
            <button
              type="button"
              onClick={() => setReloadKey((value) => value + 1)}
              className="pointer-events-auto rounded-full border border-foreground/10 px-3 py-1 text-[10px] text-foreground/55 transition-colors hover:text-foreground/75"
            >
              重试
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ActivityHeatmap;
