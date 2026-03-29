import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "motion/react";
import { Clock, Eye, MessageCircle, Tag } from "lucide-react";
import { PREVIEW_REQUEST_MESSAGE, isPreviewDataMessage } from "@serino/utils";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import FallingPetals from "@/components/FallingPetals";
import BackToTop from "@/components/BackToTop";
import CodeHighlighter from "@/components/CodeHighlighter";
import PageShell from "@/components/PageShell";
import TableOfContents from "@/components/TableOfContents";
import { useFeatureFlags, usePageConfig } from "@/contexts/runtime-config";
import MarkdownRenderer from "@/components/MarkdownRenderer";
import EmbeddedResume from "@/components/EmbeddedResume";

const _STORAGE_KEY_PREFIX = "aerisun-preview-";

const estimateReadTime = (value: string) =>
  `${Math.max(1, Math.ceil(value.length / 180))} 分钟`;

const weatherIcons: Record<string, string> = {
  sunny: "☀️",
  cloudy: "☁️",
  fog: "🌫️",
  haze: "🌫️",
  light_rain: "🌦️",
  shower: "🌧️🌨️",
  rainy: "🌧️",
  heavy_rain: "🌧️🌧️",
  light_snow: "🌨️",
  snowy: "❄️",
  heavy_snow: "❄️❄️",
  sleet: "🌧️❄️",
  stormy: "⛈️",
  windy: "💨",
};

interface PreviewData {
  type: "posts" | "diary" | "resume";
  slug?: string;
  title: string;
  summary?: string;
  body?: string;
  tags?: string[];
  status?: string;
  category?: string;
  mood?: string;
  weather?: string;
  poem?: string;
  published_at?: string | null;
  created_at?: string;
  location?: string;
  email?: string;
  profile_image_url?: string;
}

function PostPreview({ data }: { data: PreviewData }) {
  const featureFlags = useFeatureFlags();
  const pages = usePageConfig();
  const postsConfig = (pages.posts ?? {}) as {
    categories?: { fallback?: string };
  };
  const fallbackCategoryLabel = postsConfig.categories?.fallback ?? "未分类";
  const articleRef = useRef<HTMLElement>(null);

  const category = data.category || fallbackCategoryLabel;
  const readTime = estimateReadTime(data.body || "");

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="mb-4 flex flex-wrap items-center gap-3 text-xs font-body text-foreground/25">
          <span>
            {data.published_at
              ? new Date(data.published_at).toLocaleDateString("zh-CN")
              : "草稿"}
          </span>
          <span className="rounded-md border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-[rgb(var(--shiro-panel-rgb)/0.28)] px-2 py-0.5 text-[rgb(var(--shiro-accent-rgb)/0.72)]">
            {category}
          </span>
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {readTime}
          </span>
          <span className="flex items-center gap-1">
            <Eye className="h-3 w-3" />0
          </span>
          <span className="flex items-center gap-1">
            <MessageCircle className="h-3 w-3" />0
          </span>
        </div>

        <h1 className="text-2xl sm:text-3xl font-heading italic tracking-tight text-foreground leading-tight">
          {data.title || "无标题"}
        </h1>

        {data.tags && data.tags.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {data.tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 rounded-lg border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-foreground/5 px-2.5 py-1 text-[11px] font-body text-foreground/30 transition-colors hover:border-[rgb(var(--shiro-accent-rgb)/0.28)] hover:text-[rgb(var(--shiro-accent-rgb)/0.78)]"
              >
                <Tag className="h-3 w-3" />
                {tag}
              </span>
            ))}
          </div>
        )}
      </motion.div>

      <motion.article
        ref={articleRef}
        className="mt-10"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
      >
        <MarkdownRenderer content={data.body || ""} />
      </motion.article>

      <CodeHighlighter containerRef={articleRef} content={[data.body || ""]} />
      {featureFlags.toc && (
        <TableOfContents
          containerRef={articleRef}
          content={[data.body || ""]}
        />
      )}

      <div className="mt-12 border-t border-[rgb(var(--shiro-divider-rgb)/0.26)] pt-8">
        <p className="text-center text-xs font-body text-foreground/20">
          — END —
        </p>
      </div>
    </>
  );
}

function DiaryPreview({ data }: { data: PreviewData }) {
  const featureFlags = useFeatureFlags();
  const articleRef = useRef<HTMLElement>(null);
  const dateStr = data.published_at
    ? new Date(data.published_at).toLocaleDateString("zh-CN")
    : "草稿";
  const weekday = data.published_at
    ? new Date(data.published_at).toLocaleDateString("zh-CN", {
        weekday: "long",
      })
    : "";

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="liquid-glass rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.14)] p-6 mb-8">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-body text-foreground/25">
                {dateStr} {weekday}
              </p>
              <h1 className="mt-2 text-2xl sm:text-3xl font-heading italic tracking-tight text-foreground leading-tight">
                {data.title || "无标题"}
              </h1>
            </div>
            <div className="flex items-center gap-3 text-lg">
              {data.mood && <span title="心情">{data.mood}</span>}
              {data.weather && (
                <span title="天气">
                  {weatherIcons[data.weather] || data.weather}
                </span>
              )}
            </div>
          </div>
        </div>
      </motion.div>

      <motion.article
        ref={articleRef}
        className="mt-6"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
      >
        <MarkdownRenderer content={data.body || ""} />
      </motion.article>

      <CodeHighlighter containerRef={articleRef} content={[data.body || ""]} />
      {featureFlags.toc && (
        <TableOfContents
          containerRef={articleRef}
          content={[data.body || ""]}
        />
      )}

      {data.poem && (
        <motion.div
          className="mt-12 border-t border-[rgb(var(--shiro-divider-rgb)/0.26)] pt-8 text-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
        >
          <p className="whitespace-pre-line text-sm font-body text-foreground/30 italic">
            {data.poem}
          </p>
        </motion.div>
      )}
    </>
  );
}

function ResumePreview({ data }: { data: PreviewData }) {
  return (
    <PageShell
      eyebrow=""
      title=""
      description=""
      width="wide"
      contentClassName="mt-0"
      compactHeader
    >
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.06, ease: [0.16, 1, 0.3, 1] }}
      >
        <EmbeddedResume
          name={data.title || "Your Name"}
          content={data.summary || ""}
          profileImageUrl={data.profile_image_url}
          contacts={{
            location: data.location,
            email: data.email,
          }}
        />
      </motion.div>
    </PageShell>
  );
}

export default function Preview() {
  const [params] = useSearchParams();
  const [data, setData] = useState<PreviewData | null>(null);

  const storageKey = params.get("storageKey") || "";

  // Read initial data and listen for updates
  useEffect(() => {
    if (!storageKey) return;

    const read = () => {
      try {
        const raw = localStorage.getItem(storageKey);
        if (raw) setData(JSON.parse(raw));
      } catch {
        /* ignore */
      }
    };

    read();

    // Listen for localStorage updates from admin window
    const onStorage = (e: StorageEvent) => {
      if (e.key === storageKey && e.newValue) {
        try {
          setData(JSON.parse(e.newValue));
        } catch {
          /* ignore */
        }
      }
    };

    const onMessage = (event: MessageEvent) => {
      if (window.opener && event.source !== window.opener) {
        return;
      }
      if (!isPreviewDataMessage<PreviewData>(event.data)) return;
      if (event.data.storageKey !== storageKey) return;
      setData(event.data.payload);
    };

    window.addEventListener("storage", onStorage);
    window.addEventListener("message", onMessage);

    if (window.opener) {
      window.opener.postMessage(
        {
          type: PREVIEW_REQUEST_MESSAGE,
          storageKey,
        },
        "*",
      );
    }

    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("message", onMessage);
    };
  }, [storageKey]);

  if (!data) {
    return (
      <div className="min-h-screen bg-background text-foreground">
        <FallingPetals />
        <Navbar />
        <main className="mx-auto max-w-2xl px-6 pt-28 pb-20 lg:px-8">
          <p className="text-sm font-body text-foreground/40">
            {storageKey ? "正在加载预览数据..." : "缺少预览参数"}
          </p>
        </main>
        <Footer />
      </div>
    );
  }

  if (data.type === "resume") {
    return (
      <>
        <div className="pointer-events-none fixed left-4 top-4 z-[9999] sm:left-6 sm:top-6">
          <div
            className="inline-flex items-center gap-2.5 rounded-full border border-amber-400/30 bg-[rgba(36,28,12,0.78)] px-4 py-2 text-xs font-medium text-amber-100 shadow-[0_12px_40px_rgba(0,0,0,0.22)] backdrop-blur-md sm:text-sm"
            aria-label="预览模式，此内容尚未发布"
            title="预览模式，此内容尚未发布"
          >
            <span className="h-2 w-2 rounded-full bg-amber-300 shadow-[0_0_10px_rgba(252,211,77,0.9)]" />
            <span>预览模式</span>
          </div>
        </div>

        <ResumePreview data={data} />
      </>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <FallingPetals />
      <Navbar />

      {/* Preview badge */}
      <div className="pointer-events-none fixed left-4 top-4 z-[9999] sm:left-6 sm:top-6">
        <div
          className="inline-flex items-center gap-2.5 rounded-full border border-amber-400/30 bg-[rgba(36,28,12,0.78)] px-4 py-2 text-xs font-medium text-amber-100 shadow-[0_12px_40px_rgba(0,0,0,0.22)] backdrop-blur-md sm:text-sm"
          aria-label="预览模式，此内容尚未发布"
          title="预览模式，此内容尚未发布"
        >
          <span className="h-2 w-2 rounded-full bg-amber-300 shadow-[0_0_10px_rgba(252,211,77,0.9)]" />
          <span>预览模式</span>
        </div>
      </div>

      <main className="mx-auto max-w-2xl px-6 pt-28 pb-20 lg:px-8">
        {data.type === "diary" ? (
          <DiaryPreview data={data} />
        ) : (
          <PostPreview data={data} />
        )}
      </main>

      <BackToTop />
      <Footer />
    </div>
  );
}
