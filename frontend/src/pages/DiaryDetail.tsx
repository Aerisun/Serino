import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowLeft, Sun, Cloud, CloudRain, CloudSnow, CloudLightning, Wind } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import FallingPetals from "@/components/FallingPetals";
import CommentSection from "@/components/CommentSection";
import PageMeta from "@/components/PageMeta";
import { fetchPublicContentEntry, formatPublishedDate, splitContentParagraphs, type PublicContentEntry } from "@/lib/api";

type Weather = "sunny" | "cloudy" | "rainy" | "snowy" | "stormy" | "windy";

const weatherIcons: Record<Weather, typeof Sun> = {
  sunny: Sun, cloudy: Cloud, rainy: CloudRain,
  snowy: CloudSnow, stormy: CloudLightning, windy: Wind,
};
const weatherLabels: Record<Weather, string> = {
  sunny: "晴", cloudy: "多云", rainy: "雨",
  snowy: "雪", stormy: "雷阵雨", windy: "大风",
};

interface DiaryData {
  slug: string;
  date: string;
  weekday: string;
  weather: Weather;
  mood: string;
  title: string;
  paragraphs: string[];
  poem?: string;
}

const diaryData: Record<string, DiaryData> = {
  "1": {
    slug: "spring-equinox-and-warm-light",
    date: "2026 年 3 月 21 日",
    weekday: "周六",
    weather: "sunny",
    mood: "☀️",
    title: "春分后的第一个晴天",
    paragraphs: [
      "春分刚过，阳光从窗帘缝隙里漏进来，暖暖的。今天把博客的首页重新设计了一遍，加了花瓣飘落的效果，看着心情特别好。",
      "下午去了趟咖啡店，点了杯拿铁，坐在角落里写了两个小时的代码。店里放着 Norah Jones 的歌，声音刚好，不吵也不安静。窗外有人遛狗，金毛摇着尾巴跑过去又跑回来。",
      "晚上散步的时候看到樱花已经开了几朵，粉白色的花瓣在路灯下透着光。拍了几张照片，但手机拍不出那种感觉。有些美好的瞬间，大概只能留在记忆里。",
      "回家后泡了杯茶，坐在阳台上发了一会儿呆。远处的楼群亮着零星的灯光，夜风里有隐约的花香。春天真的来了。",
    ],
    poem: "春风如贵客，一到便繁华。——袁枚",
  },
  "2": {
    slug: "motion-curve-notes",
    date: "2026 年 3 月 20 日",
    weekday: "周五",
    weather: "cloudy",
    mood: "💭",
    title: "关于缓动曲线的思考",
    paragraphs: [
      "今天在改一个动画的缓动曲线，反复调了大概二十多次，最后发现 cubic-bezier(0.16, 1, 0.3, 1) 最舒服。有些事情就是这样，差一点点感觉就完全不对。",
      "这让我想到做设计也是如此。好的设计和普通设计之间的差距，往往不是「有没有」，而是「好不好」。一个按钮的圆角是 8px 还是 12px，一段文字的行高是 1.5 还是 1.75，这些看似微小的差异，累积起来就决定了整体的品质。",
      "晚上读了几页《设计中的设计》，原研哉说的「白」让我想了很久。白不是空无一物，而是充满了可能性的状态。就像一张白纸，它不是没有内容，而是在等待内容。",
      "今天多云，天空是均匀的灰白色，像一张巨大的宣纸铺在城市上方。这种天气适合思考。",
    ],
  },
  "3": {
    slug: "rain-day-and-lofi",
    date: "2026 年 3 月 19 日",
    weekday: "周四",
    weather: "rainy",
    mood: "🌧️",
    title: "雨天，面条，和意外的高效",
    paragraphs: [
      "下了一整天的雨，窝在家里没出门。窗外是连绵不断的雨声，像白噪音一样笼罩着整个世界。",
      "把友链页面的朋友圈功能做完了，写了很多假数据，但看起来还挺真实的。做这种功能的时候会想，互联网最初的样子是不是就该这样——大家各自有一个小小的空间，然后通过链接彼此相连。",
      "中午煮了碗面，加了个蛋。面条在锅里翻滚的样子很治愈。吃完后靠在沙发上刷了会儿手机，看到一条推特说「The best code is the code you don't write」，深以为然。",
      "雨声配着 lo-fi 音乐，竟然效率出奇的高。也许是因为下雨天没有出门的念头，心反而安定了下来。",
    ],
    poem: "小楼一夜听春雨，深巷明朝卖杏花。——陆游",
  },
  "4": {
    slug: "burst-of-inspiration-day",
    date: "2026 年 3 月 18 日",
    weekday: "周三",
    weather: "sunny",
    mood: "✨",
    title: "灵感爆发的一天",
    paragraphs: [
      "今天灵感特别好，一口气写了三篇碎碎念。发现写东西和写代码很像，都需要找到节奏感。节奏对了，一切都会自然流动。",
      "晚上和朋友视频聊了一个小时，聊到了各自的近况，感觉时间过得好快。上次见面还是去年秋天，说好一起去爬山，结果一直没实现。",
      "睡前翻了翻之前写的日记，发现半年前的烦恼现在看来都不算什么。也许现在的烦恼，半年后回头看也会这样吧。",
    ],
  },
  "5": {
    slug: "windy-library-day",
    date: "2026 年 3 月 17 日",
    weekday: "周二",
    weather: "windy",
    mood: "🍃",
    title: "风很大的一天",
    paragraphs: [
      "风很大，出门的时候差点被吹走。去图书馆还了几本书，又借了两本。一本是关于字体设计的，另一本是村上春树的新书。",
      "回来的路上买了杯热可可，手指冻得有点僵。突然想到一个有趣的问题：为什么我们总是在寒冷的时候更容易想到温暖的事？",
      "晚上把书翻了几页，字体设计那本特别有意思。原来我们每天看到的文字背后，有那么多设计师的心血。每一个笔画的弧度、每一个字母的间距，都是精心计算过的。",
    ],
    poem: "解落三秋叶，能开二月花。——李峤",
  },
  "6": {
    slug: "new-week-balance",
    date: "2026 年 3 月 16 日",
    weekday: "周一",
    weather: "cloudy",
    mood: "📝",
    title: "新的一周",
    paragraphs: [
      "新的一周开始了。给自己列了个 todo list，然后心安理得地只完成了一半。",
      "液态玻璃效果的模糊值调了很久，从 blur(4px) 到 blur(50px) 来回试，最后找到了一个不错的平衡点。做设计这件事，很多时候就是在两个极端之间来回摇摆，直到找到那个「刚刚好」的位置。",
      "晚饭后在楼下走了一圈，空气有点湿润，像是要下雨的样子。路灯把树影拉得很长，有种说不出的安静。",
    ],
  },
  "7": {
    slug: "quiet-weekend",
    date: "2026 年 3 月 15 日",
    weekday: "周日",
    weather: "sunny",
    mood: "🌸",
    title: "安静的周末",
    paragraphs: [
      "周末的最后一天，去公园走了走。树上的花苞已经鼓鼓的了，再过几天应该就会开了。",
      "拍了几张照片，光线特别好。回来后把照片调了调色，想放到博客的相册里。一个人的周末，安静但不孤单。",
      "晚上煮了火锅，一个人吃了一整锅。看了两集纪录片，关于阿尔卑斯山的。那些雪山和湖泊，美得不真实。什么时候能亲眼去看看呢。",
    ],
    poem: "人间有味是清欢。——苏轼",
  },
};

const fallbackBySlug = Object.fromEntries(
  Object.values(diaryData).map((item) => [item.slug, item]),
);

const formatWeekday = (value: string | null) => {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return new Intl.DateTimeFormat("zh-CN", { weekday: "short" }).format(parsed);
};

const buildRemoteDiaryEntry = (entry: PublicContentEntry, fallback?: DiaryData): DiaryData => ({
  slug: entry.slug,
  date: formatPublishedDate(entry.published_at) || fallback?.date || "",
  weekday: formatWeekday(entry.published_at) || fallback?.weekday || "",
  weather: fallback?.weather ?? "cloudy",
  mood: fallback?.mood ?? "📝",
  title: entry.title,
  paragraphs: splitContentParagraphs(entry.body),
  poem: fallback?.poem,
});

const DiaryDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const initialFallback = (id ? diaryData[id] : undefined) ?? (id ? fallbackBySlug[id] : undefined) ?? null;
  const [entry, setEntry] = useState<DiaryData | null>(initialFallback);

  useEffect(() => {
    let cancelled = false;

    const fallback = (id ? diaryData[id] : undefined) ?? (id ? fallbackBySlug[id] : undefined) ?? null;
    const targetSlug = fallback?.slug ?? id;

    setEntry(fallback);

    if (!targetSlug) {
      return () => {
        cancelled = true;
      };
    }

    const loadEntry = async () => {
      try {
        const payload = await fetchPublicContentEntry("diary", targetSlug);
        if (cancelled) {
          return;
        }

        setEntry(buildRemoteDiaryEntry(payload, fallback ?? undefined));
      } catch {
        if (!cancelled) {
          setEntry(fallback);
        }
      }
    };

    void loadEntry();

    return () => {
      cancelled = true;
    };
  }, [id]);

  if (!entry) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
        <PageMeta title="日记不存在" description="你访问的日记暂时不存在。" />
        <p className="text-foreground/30">日记不存在</p>
      </div>
    );
  }

  const WeatherIcon = weatherIcons[entry.weather];

  return (
    <div className="min-h-screen bg-background text-foreground">
      <PageMeta title={entry.title} description={entry.paragraphs[0]} />
      <FallingPetals />
      <Navbar />

      <main className="mx-auto max-w-2xl px-6 pt-28 pb-20 lg:px-8">
        <motion.button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm font-body text-foreground/30 hover:text-foreground/60 transition-colors mb-8 active:scale-95"
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        >
          <ArrowLeft className="h-4 w-4" />
          返回
        </motion.button>

        <motion.div
          className="liquid-glass rounded-2xl p-6 sm:p-8 mb-10"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="flex items-start justify-between mb-4">
            <div>
              <p className="text-xs font-body text-foreground/25 uppercase tracking-wider">
                {entry.weekday} · {entry.date}
              </p>
              <h1 className="mt-2 text-xl sm:text-2xl font-heading italic tracking-tight text-foreground/90">
                {entry.title}
              </h1>
            </div>
            <div className="flex items-center gap-2 shrink-0 ml-4">
              <span className="text-2xl">{entry.mood}</span>
              <div className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-foreground/5">
                <WeatherIcon className="h-3.5 w-3.5 text-foreground/35" />
                <span className="text-[11px] font-body text-foreground/30">
                  {weatherLabels[entry.weather]}
                </span>
              </div>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
        >
          {entry.paragraphs.map((p, i) => (
            <motion.p
              key={i}
              className="text-sm font-body text-foreground/50 leading-[1.9] mb-6 first-letter:text-foreground/70 first-letter:text-base"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.15 + i * 0.06, ease: [0.16, 1, 0.3, 1] }}
            >
              {p}
            </motion.p>
          ))}
        </motion.div>

        {entry.poem && (
          <motion.div
            className="mt-10 py-6 border-t border-b border-foreground/5 text-center"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.4 }}
          >
            <p className="text-sm font-heading italic text-foreground/25 tracking-wide">
              {entry.poem}
            </p>
          </motion.div>
        )}

        <div className="mt-10 text-center">
          <p className="text-xs font-body text-foreground/15">— 今日份记录 —</p>
        </div>

        <CommentSection contentType="diary" contentSlug={entry.slug} />
      </main>
      <Footer />
    </div>
  );
};

export default DiaryDetail;
