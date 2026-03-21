import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Heart, MessageCircle, Repeat2 } from "lucide-react";
import PageShell from "@/components/PageShell";
import { staggerItem } from "@/config";
import { usePageConfig } from "@/contexts/RuntimeConfigContext";
import {
  fetchPublicContentCollection,
  formatPublishedDate,
  splitContentParagraphs,
  type PublicContentEntry,
} from "@/lib/api";

interface Thought {
  id: string;
  content: string;
  date: string;
  likes: number;
  comments: number;
  reposts: number;
  mood?: string;
}

const mapRemoteThought = (entry: PublicContentEntry): Thought => {
  const paragraphs = splitContentParagraphs(entry.body);

  return {
    id: entry.slug,
    content: entry.summary?.trim() || paragraphs[0] || entry.body || entry.title,
    date: entry.relative_date ?? (formatPublishedDate(entry.published_at) || ""),
    likes: entry.like_count ?? 0,
    comments: entry.comment_count ?? 0,
    reposts: entry.repost_count ?? 0,
    mood: entry.mood ?? undefined,
  };
};

const Thoughts = () => {
  const config = usePageConfig().thoughts as Record<string, any>;
  const [items, setItems] = useState<Thought[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    const loadThoughts = async () => {
      setStatus("loading");
      setErrorMessage("");

      try {
        const payload = await fetchPublicContentCollection("thoughts", 30, { signal: controller.signal });
        if (controller.signal.aborted) {
          return;
        }

        const nextItems = payload.items.map(mapRemoteThought);
        setItems(nextItems);
        setStatus(nextItems.length > 0 ? "ready" : "empty");
      } catch (error) {
        if (!controller.signal.aborted) {
          setItems([]);
          setStatus("error");
          setErrorMessage(error instanceof Error ? error.message : "碎碎念加载失败");
        }
      }
    };

    void loadThoughts();

    return () => {
      controller.abort();
    };
  }, [reloadKey]);

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
    >
      <div className="relative mt-10">
        <div className="absolute bottom-0 left-5 top-0 w-px bg-foreground/6" />

        {status === "loading" &&
          Array.from({ length: 6 }, (_, index) => (
            <div key={`thought-skeleton-${index}`} className="relative pb-10 pl-14 last:pb-0">
              <div className="absolute left-[14px] top-1.5 h-3 w-3 rounded-full border-2 border-foreground/12 bg-background" />
              <div className="h-3 w-28 rounded-full bg-foreground/[0.05]" />
              <div className="mt-3 h-4 w-[88%] rounded-full bg-foreground/[0.04]" />
              <div className="mt-2 h-4 w-[72%] rounded-full bg-foreground/[0.035]" />
              <div className="mt-4 flex items-center gap-5">
                <div className="h-3.5 w-10 rounded-full bg-foreground/[0.035]" />
                <div className="h-3.5 w-10 rounded-full bg-foreground/[0.035]" />
                <div className="h-3.5 w-10 rounded-full bg-foreground/[0.03]" />
              </div>
            </div>
          ))}

        {status === "error" && (
          <div className="relative pb-10 pl-14">
            <div className="absolute left-[14px] top-1.5 h-3 w-3 rounded-full border-2 border-foreground/12 bg-background" />
            <div className="flex items-center gap-2 text-xs text-foreground/25">
              <span>刚刚</span>
            </div>
            <p className="mt-2 text-[0.935rem] leading-7 text-foreground/45">碎碎念加载失败</p>
            <p className="mt-2 text-sm leading-7 text-foreground/30">{errorMessage}</p>
            <div className="mt-3">
              <button
                type="button"
                onClick={() => setReloadKey((value) => value + 1)}
                className="text-xs text-foreground/25 transition-colors hover:text-foreground/45"
              >
                重试
              </button>
            </div>
          </div>
        )}

        {status === "empty" && (
          <div className="relative pb-10 pl-14">
            <div className="absolute left-[14px] top-1.5 h-3 w-3 rounded-full border-2 border-foreground/12 bg-background" />
            <div className="flex items-center gap-2 text-xs text-foreground/25">
              <span>今天</span>
            </div>
            <p className="mt-2 text-[0.935rem] leading-7 text-foreground/45">
              {config.emptyMessage ?? "最近没有新的碎碎念"}
            </p>
          </div>
        )}

        {status === "ready" &&
          items.map((thought, index) => (
            <motion.div
              key={thought.id}
              className="relative pb-10 pl-14 last:pb-0"
              {...staggerItem(index, {
                baseDelay: config.motion.delay,
                step: config.motion.stagger,
                duration: config.motion.duration,
              })}
            >
              <div className="absolute left-[14px] top-1.5 h-3 w-3 rounded-full border-2 border-foreground/15 bg-background" />

              <div className="flex items-center gap-2 text-xs text-foreground/25">
                {thought.date && <span>{thought.date}</span>}
                {thought.mood && <span>{thought.mood}</span>}
              </div>

              <p className="mt-2 text-[0.935rem] leading-7 text-foreground/65">
                {thought.content}
              </p>

              <div className="mt-3 flex items-center gap-5 text-xs text-foreground/20">
                <button type="button" className="flex items-center gap-1.5 transition-colors hover:text-foreground/45 active:scale-[0.95]">
                  <Heart className="h-3.5 w-3.5" />
                  {thought.likes}
                </button>
                <button type="button" className="flex items-center gap-1.5 transition-colors hover:text-foreground/45 active:scale-[0.95]">
                  <MessageCircle className="h-3.5 w-3.5" />
                  {thought.comments}
                </button>
                <button type="button" className="flex items-center gap-1.5 transition-colors hover:text-foreground/45 active:scale-[0.95]">
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
