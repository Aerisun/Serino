import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Heart, MessageCircle, Repeat2 } from "lucide-react";
import PageShell from "@/components/PageShell";
import { pageConfig, staggerItem } from "@/config";
import { fetchPublicContentCollection, formatPublishedDate, splitContentParagraphs, type PublicContentEntry } from "@/lib/api";

interface Thought {
  id: number | string;
  slug?: string;
  content: string;
  date: string;
  likes: number;
  comments: number;
  reposts: number;
  mood?: string;
}

const fallbackThoughts: Thought[] = [
  {
    id: 1,
    content: "今天把博客的排版重新调了一遍，字间距从 -0.02em 改到 -0.03em，整个页面的气质都不一样了。设计就是这种细微到像素级的偏执。",
    date: "3 小时前",
    likes: 24,
    comments: 5,
    reposts: 2,
    mood: "🎨",
  },
  {
    id: 2,
    content: "读完了 Dieter Rams 的《Less but Better》，越来越觉得好的设计不是加法而是减法。把不必要的东西去掉，剩下的自然就有力量。",
    date: "昨天",
    likes: 47,
    comments: 8,
    reposts: 6,
  },
  {
    id: 3,
    content: "下午在咖啡店写代码，窗外下雨，耳机里放着 Nujabes。这种时刻效率特别高，可能是因为没有任何打扰。",
    date: "2 天前",
    likes: 62,
    comments: 12,
    reposts: 3,
    mood: "☕",
  },
  {
    id: 4,
    content: "发现一个规律：越是简单的页面越难做。因为没有多余元素可以藏拙，每一个间距、每一个颜色都暴露在外面。",
    date: "3 天前",
    likes: 35,
    comments: 4,
    reposts: 7,
  },
  {
    id: 5,
    content: "把所有项目的配色都统一成了同一套灰度体系，突然觉得作品集看起来像一个人做的了（之前真的不像）。",
    date: "5 天前",
    likes: 28,
    comments: 6,
    reposts: 1,
    mood: "✨",
  },
  {
    id: 6,
    content: "有时候觉得写前端和做手工很像，都是把一堆零散的东西拼成一个完整的、能用的、最好还好看的东西。",
    date: "1 周前",
    likes: 53,
    comments: 9,
    reposts: 4,
  },
  {
    id: 7,
    content: "终于把暗黑模式的对比度问题解决了。关键不是把白色换成黑色，而是重新定义每一层的灰度关系。",
    date: "1 周前",
    likes: 41,
    comments: 7,
    reposts: 5,
    mood: "🌙",
  },
  {
    id: 8,
    content: "今天面试了一个实习生，作品集很粗糙但是思路特别清晰。比起精美的 Dribbble shot，我更看重解决问题的过程。",
    date: "2 周前",
    likes: 89,
    comments: 15,
    reposts: 11,
  },
];
const config = pageConfig.thoughts;

const mapRemoteThought = (entry: PublicContentEntry, index: number): Thought => {
  const fallback = fallbackThoughts[index];

  return {
    id: fallback?.id ?? entry.slug,
    slug: entry.slug,
    content: entry.summary?.trim() || splitContentParagraphs(entry.body)[0] || entry.title,
    date: formatPublishedDate(entry.published_at) || fallback?.date || "",
    likes: fallback?.likes ?? 0,
    comments: fallback?.comments ?? 0,
    reposts: fallback?.reposts ?? 0,
    mood: fallback?.mood,
  };
};

const Thoughts = () => {
  const [items, setItems] = useState<Thought[]>(fallbackThoughts);

  useEffect(() => {
    let cancelled = false;

    const loadThoughts = async () => {
      try {
        const payload = await fetchPublicContentCollection("thoughts", 40);
        if (cancelled || payload.items.length === 0) {
          return;
        }

        setItems(payload.items.map(mapRemoteThought));
      } catch {
        if (!cancelled) {
          setItems(fallbackThoughts);
        }
      }
    };

    void loadThoughts();

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

        {/* Timeline */}
        <div className="relative mt-10">
          {/* Vertical line */}
          <div className="absolute left-5 top-0 bottom-0 w-px bg-foreground/6" />

          {items.map((thought, i) => (
            <motion.div
              key={thought.id}
              className="relative pl-14 pb-10 last:pb-0"
              {...staggerItem(i, {
                baseDelay: config.motion.delay,
                step: config.motion.stagger,
                duration: config.motion.duration,
              })}
            >
              {/* Dot */}
              <div className="absolute left-[14px] top-1.5 h-3 w-3 rounded-full border-2 border-foreground/15 bg-background" />

              {/* Date + mood */}
              <div className="flex items-center gap-2 text-xs text-foreground/25">
                <span>{thought.date}</span>
                {thought.mood && <span>{thought.mood}</span>}
              </div>

              {/* Content */}
              <p className="mt-2 text-[0.935rem] leading-7 text-foreground/65">
                {thought.content}
              </p>

              {/* Actions */}
              <div className="mt-3 flex items-center gap-5 text-xs text-foreground/20">
                <button className="flex items-center gap-1.5 transition-colors hover:text-foreground/45 active:scale-[0.95]">
                  <Heart className="h-3.5 w-3.5" />
                  {thought.likes}
                </button>
                <button className="flex items-center gap-1.5 transition-colors hover:text-foreground/45 active:scale-[0.95]">
                  <MessageCircle className="h-3.5 w-3.5" />
                  {thought.comments}
                </button>
                <button className="flex items-center gap-1.5 transition-colors hover:text-foreground/45 active:scale-[0.95]">
                  <Repeat2 className="h-3.5 w-3.5" />
                  {thought.reposts}
                </button>
              </div>
            </motion.div>
          ))}
        </div>
    </PageShell>
  );
};

export default Thoughts;
