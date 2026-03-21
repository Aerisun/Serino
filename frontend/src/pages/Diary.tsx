import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import { Sun, Cloud, CloudRain, CloudSnow, CloudLightning, Wind, ChevronDown } from "lucide-react";
import PageShell from "@/components/PageShell";
import { staggerItem } from "@/config";
import { usePageConfig } from "@/contexts/RuntimeConfigContext";
import { fetchPublicContentCollection, splitContentParagraphs, type PublicContentEntry } from "@/lib/api";

type Weather = "sunny" | "cloudy" | "rainy" | "snowy" | "stormy" | "windy";

interface DiaryEntry {
  id: number;
  slug: string;
  title: string;
  date: string;
  weekday: string;
  weather: Weather;
  mood: string;
  content: string;
}

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

const fallbackDiaryEntries: DiaryEntry[] = [
  {
    id: 1,
    slug: "spring-equinox-and-warm-light",
    title: "春分后的第一个晴天",
    date: "2026-03-21",
    weekday: "周六",
    weather: "sunny",
    mood: "☀️",
    content: "春分刚过，阳光从窗帘缝隙里漏进来，暖暖的。今天把博客的首页重新设计了一遍，加了花瓣飘落的效果，看着心情特别好。下午去了趟咖啡店，点了杯拿铁，坐在角落里写了两个小时的代码。晚上散步的时候看到樱花已经开了几朵，春天真的来了。",
  },
  {
    id: 2,
    slug: "motion-curve-notes",
    title: "关于缓动曲线的思考",
    date: "2026-03-20",
    weekday: "周五",
    weather: "cloudy",
    mood: "💭",
    content: "今天在改一个动画的缓动曲线，反复调了大概二十多次，最后发现 cubic-bezier(0.16, 1, 0.3, 1) 最舒服。有些事情就是这样，差一点点感觉就完全不对。晚上读了几页《设计中的设计》，原研哉说的\u201C白\u201D让我想了很久。",
  },
  {
    id: 3,
    slug: "rain-day-and-lofi",
    title: "雨天，面条，和意外的高效",
    date: "2026-03-19",
    weekday: "周四",
    weather: "rainy",
    mood: "🌧️",
    content: "下了一整天的雨，窝在家里没出门。把友链页面的朋友圈功能做完了，写了很多假数据，但看起来还挺真实的。中午煮了碗面，加了个蛋。雨声配着 lo-fi 音乐，竟然效率出奇的高。",
  },
  {
    id: 4,
    slug: "burst-of-inspiration-day",
    title: "灵感爆发的一天",
    date: "2026-03-18",
    weekday: "周三",
    weather: "sunny",
    mood: "✨",
    content: "今天灵感特别好，一口气写了三篇碎碎念。发现写东西和写代码很像，都需要找到节奏感。节奏对了，一切都会自然流动。晚上和朋友视频聊了一个小时，聊到了各自的近况，感觉时间过得好快。",
  },
  {
    id: 5,
    slug: "windy-library-day",
    title: "风很大的一天",
    date: "2026-03-17",
    weekday: "周二",
    weather: "windy",
    mood: "🍃",
    content: "风很大，出门的时候差点被吹走。去图书馆还了几本书，又借了两本。一本是关于字体设计的，另一本是村上春树的新书。回来的路上买了杯热可可，手指冻得有点僵。",
  },
  {
    id: 6,
    slug: "new-week-balance",
    title: "新的一周",
    date: "2026-03-16",
    weekday: "周一",
    weather: "cloudy",
    mood: "📝",
    content: "新的一周开始了。给自己列了个 todo list，然后心安理得地只完成了一半。液态玻璃效果的模糊值调了很久，从 blur(4px) 到 blur(50px) 来回试，最后找到了一个不错的平衡点。",
  },
  {
    id: 7,
    slug: "quiet-weekend",
    title: "安静的周末",
    date: "2026-03-15",
    weekday: "周日",
    weather: "sunny",
    mood: "🌸",
    content: "周末的最后一天，去公园走了走。树上的花苞已经鼓鼓的了，再过几天应该就会开了。拍了几张照片，光线特别好。回来后把照片调了调色，想放到博客的相册里。一个人的周末，安静但不孤单。",
  },
];
const fallbackBySlug = Object.fromEntries(fallbackDiaryEntries.map((item) => [item.slug, item]));

const formatDateKey = (value: string | null) => {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toISOString().slice(0, 10);
};

const formatWeekday = (value: string | null) => {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return new Intl.DateTimeFormat("zh-CN", { weekday: "short" }).format(parsed);
};

const mapRemoteDiaryEntry = (entry: PublicContentEntry, index: number): DiaryEntry => {
  const fallback = fallbackBySlug[entry.slug];
  const preview = entry.summary?.trim() || splitContentParagraphs(entry.body)[0] || fallback?.content || "";

  return {
    id: fallback?.id ?? index + 1,
    slug: entry.slug,
    title: entry.title,
    date: formatDateKey(entry.published_at) || fallback?.date || "",
    weekday: formatWeekday(entry.published_at) || fallback?.weekday || "",
    weather: fallback?.weather ?? "cloudy",
    mood: fallback?.mood ?? "📝",
    content: preview,
  };
};

const Diary = () => {
  const config = usePageConfig().diary as Record<string, any>;
  const [items, setItems] = useState<DiaryEntry[]>(fallbackDiaryEntries);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;

    const loadDiary = async () => {
      try {
        const payload = await fetchPublicContentCollection("diary", 20);
        if (cancelled || payload.items.length === 0) {
          return;
        }

        setItems(payload.items.map(mapRemoteDiaryEntry));
      } catch {
        if (!cancelled) {
          setItems(fallbackDiaryEntries);
        }
      }
    };

    void loadDiary();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
    >

        {/* Diary entries */}
        <div className="mt-10 flex flex-col gap-3">
          {items.map((entry, i) => {
            const isExpanded = expandedId === entry.id;
            const WeatherIcon = weatherIcons[entry.weather];

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
                  onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                  className="w-full text-left"
                >
                  <div
                    className={`liquid-glass rounded-2xl px-5 py-4 transition-colors ${
                      isExpanded ? "bg-foreground/[0.03]" : "hover:bg-foreground/[0.02]"
                    }`}
                  >
                    {/* Header row */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {/* Date block */}
                        <div className="flex flex-col items-center min-w-[42px]">
                          <span className="text-lg font-body font-medium text-foreground/80 tabular-nums leading-none">
                            {entry.date.split("-")[2]}
                          </span>
                          <span className="text-[10px] font-body text-foreground/25 mt-0.5">
                            {entry.weekday}
                          </span>
                        </div>

                        {/* Divider */}
                        <div className="h-8 w-px bg-foreground/[0.08]" />

                        {/* Weather + mood */}
                        <div className="flex items-center gap-2">
                          <WeatherIcon className="h-4 w-4 text-foreground/30" />
                          <span className="text-xs font-body text-foreground/30">
                            {weatherLabels[entry.weather]}
                          </span>
                          <span className="text-sm">{entry.mood}</span>
                        </div>
                      </div>

                      {/* Expand indicator */}
                      <ChevronDown
                        className={`h-4 w-4 text-foreground/20 transition-transform duration-300 ${
                          isExpanded ? "rotate-180" : ""
                        }`}
                      />
                    </div>

                    {/* Preview (collapsed) */}
                    {!isExpanded && (
                      <p className="mt-3 text-sm font-body text-foreground/35 line-clamp-1 leading-relaxed">
                        {entry.content}
                      </p>
                    )}

                    {/* Full content (expanded) */}
                    <AnimatePresence>
                      {isExpanded && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: config.motion.duration - 0.1, ease: [0.16, 1, 0.3, 1] }}
                          className="overflow-hidden"
                        >
                          <p className="mt-4 text-[0.935rem] font-body text-foreground/60 leading-7">
                            {entry.content}
                          </p>
                          <div className="mt-4 pt-3 border-t border-foreground/[0.05] flex items-center justify-between">
                            <span className="text-[10px] font-body text-foreground/15 uppercase tracking-wider">
                              {entry.date} · {weatherLabels[entry.weather]}
                            </span>
                            <button
                              onClick={(e) => { e.stopPropagation(); navigate(`/diary/${entry.slug}`); }}
                              className="text-[11px] font-body text-foreground/30 hover:text-foreground/60 transition-colors"
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
