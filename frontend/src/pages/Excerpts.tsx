import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { BookOpen, ExternalLink, X } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import FallingPetals from "@/components/FallingPetals";

interface Excerpt {
  id: number;
  title: string;
  author: string;
  source: string;
  content: string;
  tags: string[];
  date: string;
}

const excerpts: Excerpt[] = [
  {
    id: 1,
    title: "关于白",
    author: "原研哉",
    source: "《白》",
    content: "白不是一种颜色，而是一种感受力。它是在所有颜色消失之后，仍然存在的那种纯净。当我们说某个东西是白的，我们真正在说的是，它让我们看到了空间本身。白是容纳一切可能性的状态，是尚未被填满的画布，是沉默中蕴含的所有声音。",
    tags: ["设计", "美学"],
    date: "2026-03-20",
  },
  {
    id: 2,
    title: "少即是多",
    author: "Dieter Rams",
    source: "Less but Better",
    content: "Good design is as little design as possible. Less, but better \u2013 because it concentrates on the essential aspects, and the products are not burdened with non-essentials. Back to purity, back to simplicity.",
    tags: ["设计", "极简"],
    date: "2026-03-18",
  },
  {
    id: 3,
    title: "创造的秘密",
    author: "村上春树",
    source: "《我的职业是小说家》",
    content: "写长篇小说时，我每天早上四点起床，写五到六个小时。下午跑步或游泳，然后读书、听音乐，晚上九点就寝。这种生活我坚持了三十多年。重复本身就是一件了不起的事，重复之中隐藏着某种力量，这种力量会慢慢地、确实地改变我们。",
    tags: ["写作", "生活"],
    date: "2026-03-15",
  },
  {
    id: 4,
    title: "观看之道",
    author: "John Berger",
    source: "Ways of Seeing",
    content: "Seeing comes before words. The child looks and recognizes before it can speak. But there is also another sense in which seeing comes before words. It is seeing which establishes our place in the surrounding world.",
    tags: ["艺术", "视觉"],
    date: "2026-03-12",
  },
  {
    id: 5,
    title: "留白的意义",
    author: "李欧梵",
    source: "《中国现代文学与现代性十讲》",
    content: "中国画讲究留白，不是因为画家偷懒，而是因为空白本身就是意义的一部分。空白给了观者想象的空间，让画面从有限延伸到无限。最好的设计也是如此，不是填满每一个角落，而是知道在哪里停下来。",
    tags: ["美学", "东方"],
    date: "2026-03-08",
  },
  {
    id: 6,
    title: "工具与手",
    author: "Richard Sennett",
    source: "The Craftsman",
    content: "The craftsman represents the special human condition of being engaged. Every good craftsman conducts a dialogue between concrete practices and thinking; this dialogue evolves into sustaining habits, and these habits establish a rhythm between problem solving and problem finding.",
    tags: ["工艺", "思考"],
    date: "2026-03-05",
  },
  {
    id: 7,
    title: "时间的形状",
    author: "松浦弥太郎",
    source: "《100 个基本》",
    content: "每天做一件让自己开心的小事。不是什么了不起的大事，只是一件很小的事就好。泡一杯好茶，读几页喜欢的书，在笔记本上画一朵花。这些小事堆积起来，就构成了我们生活的质感。",
    tags: ["生活", "日常"],
    date: "2026-03-01",
  },
];

const Excerpts = () => {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = excerpts.find((e) => e.id === selectedId);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <FallingPetals />
      <Navbar />

      <main className="mx-auto max-w-3xl px-6 pt-28 pb-20 lg:px-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
        >
          <h1 className="text-3xl font-heading italic tracking-tight text-foreground sm:text-4xl">
            文摘
          </h1>
          <p className="mt-3 text-sm text-foreground/35">
            摘录那些让我停下来想一想的文字。
          </p>
        </motion.div>

        {/* Excerpt cards */}
        <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {excerpts.map((excerpt, i) => (
            <motion.button
              key={excerpt.id}
              onClick={() => setSelectedId(excerpt.id)}
              className="group text-left liquid-glass rounded-2xl p-5 transition-colors hover:bg-foreground/[0.03] active:scale-[0.98]"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: 0.4,
                delay: 0.06 + i * 0.04,
                ease: [0.16, 1, 0.3, 1],
              }}
            >
              {/* Source info */}
              <div className="flex items-center gap-2 mb-3">
                <BookOpen className="h-3.5 w-3.5 text-foreground/20" />
                <span className="text-[10px] font-body text-foreground/25 uppercase tracking-wider truncate">
                  {excerpt.source} · {excerpt.author}
                </span>
              </div>

              {/* Title */}
              <h3 className="text-base font-body font-medium text-foreground/80 group-hover:text-foreground transition-colors leading-snug">
                {excerpt.title}
              </h3>

              {/* Preview */}
              <p className="mt-2 text-[12px] font-body text-foreground/30 leading-relaxed line-clamp-3">
                {excerpt.content}
              </p>

              {/* Tags */}
              <div className="mt-3 flex flex-wrap gap-1.5">
                {excerpt.tags.map((tag) => (
                  <span
                    key={tag}
                    className="text-[10px] font-body text-foreground/20 px-2 py-0.5 rounded-full border border-foreground/[0.06]"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </motion.button>
          ))}
        </div>
      </main>

      {/* Detail modal */}
      <AnimatePresence>
        {selected && (
          <motion.div
            className="fixed inset-0 z-[90] flex items-center justify-center px-6"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            {/* Backdrop */}
            <div
              className="absolute inset-0 bg-background/80 backdrop-blur-sm"
              onClick={() => setSelectedId(null)}
            />

            {/* Content */}
            <motion.div
              className="relative liquid-glass rounded-3xl p-8 max-w-lg w-full max-h-[80vh] overflow-y-auto scrollbar-hide"
              initial={{ scale: 0.95, opacity: 0, y: 16 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 16 }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            >
              {/* Close */}
              <button
                onClick={() => setSelectedId(null)}
                className="absolute top-4 right-4 h-8 w-8 flex items-center justify-center rounded-full text-foreground/30 hover:text-foreground/60 hover:bg-foreground/[0.05] transition-colors"
              >
                <X className="h-4 w-4" />
              </button>

              {/* Source */}
              <div className="flex items-center gap-2 mb-4">
                <BookOpen className="h-4 w-4 text-foreground/25" />
                <span className="text-xs font-body text-foreground/30">
                  {selected.source}
                </span>
              </div>

              {/* Title */}
              <h2 className="text-xl font-heading italic text-foreground leading-snug">
                {selected.title}
              </h2>
              <p className="mt-1 text-xs font-body text-foreground/25">
                {selected.author} · {selected.date}
              </p>

              {/* Divider */}
              <div className="my-5 border-t border-foreground/[0.06]" />

              {/* Content */}
              <p
                className="text-[0.935rem] font-body text-foreground/60 leading-8"
                style={{ fontFamily: "'Instrument Serif', serif" }}
              >
                {selected.content}
              </p>

              {/* Tags */}
              <div className="mt-6 flex flex-wrap gap-2">
                {selected.tags.map((tag) => (
                  <span
                    key={tag}
                    className="text-[11px] font-body text-foreground/25 px-3 py-1 rounded-full border border-foreground/[0.08]"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <Footer />
    </div>
  );
};

export default Excerpts;
