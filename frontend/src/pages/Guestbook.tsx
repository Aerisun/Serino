import { useState } from "react";
import { motion } from "motion/react";
import { Send } from "lucide-react";
import PageShell from "@/components/PageShell";
import { pageConfig, staggerItem } from "@/config";

interface Message {
  id: number;
  name: string;
  avatar: string;
  content: string;
  date: string;
}

const messages: Message[] = [
  {
    id: 1,
    name: "Elena Torres",
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Elena",
    content: "你的博客设计真的太好看了！液态玻璃的效果特别有质感，请问是怎么实现的？",
    date: "2026-03-20",
  },
  {
    id: 2,
    name: "Kai Nakamura",
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Kai",
    content: "Felix, your work on motion design is inspiring. The easing curves article changed how I think about animation.",
    date: "2026-03-18",
  },
  {
    id: 3,
    name: "David Okoro",
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=David",
    content: "偶然发现你的网站，被花瓣飘落的效果吸引了。整体氛围很棒，很有个人风格。加油！",
    date: "2026-03-15",
  },
  {
    id: 4,
    name: "Sofia Lindgren",
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Sofia",
    content: "Reading your diary entries feels like a warm conversation. Keep writing, Felix!",
    date: "2026-03-12",
  },
  {
    id: 5,
    name: "Priya Sharma",
    avatar: "https://api.dicebear.com/9.x/notionists/svg?seed=Priya",
    content: "你的文摘栏目收录的都是好文章，原研哉那段关于白的摘录我也很喜欢。",
    date: "2026-03-08",
  },
];
const config = pageConfig.guestbook;

const Guestbook = () => {
  const [name, setName] = useState("");
  const [content, setContent] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (name.trim() && content.trim()) {
      setName("");
      setContent("");
    }
  };

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
    >

        {/* Form */}
        <motion.form
          onSubmit={handleSubmit}
          className="mt-10 liquid-glass rounded-2xl p-6"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: config.motion.duration, delay: config.motion.delay, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="flex flex-col sm:flex-row gap-3 mb-3">
            <input
              type="text"
              placeholder={config.namePlaceholder}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="flex-1 rounded-xl border border-foreground/[0.08] bg-foreground/[0.03] px-4 py-2.5 text-sm font-body text-foreground placeholder:text-foreground/20 outline-none transition-colors focus:border-foreground/15 focus:bg-foreground/[0.05]"
            />
          </div>
          <textarea
            placeholder={config.contentPlaceholder}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={3}
            className="w-full rounded-xl border border-foreground/[0.08] bg-foreground/[0.03] px-4 py-3 text-sm font-body text-foreground placeholder:text-foreground/20 outline-none transition-colors focus:border-foreground/15 focus:bg-foreground/[0.05] resize-none"
          />
          <div className="mt-3 flex justify-end">
            <button
              type="submit"
              className="flex items-center gap-2 rounded-full liquid-glass px-5 py-2.5 text-sm font-body font-medium text-foreground/60 hover:text-foreground transition-colors active:scale-[0.97]"
            >
              <Send className="h-3.5 w-3.5" />
              {config.submitLabel}
            </button>
          </div>
        </motion.form>

        {/* Messages */}
        <div className="mt-10 flex flex-col gap-0">
          {messages.map((msg, i) => (
            <motion.div
              key={msg.id}
              className="flex items-start gap-3.5 py-5 border-t border-foreground/[0.05]"
              {...staggerItem(i, {
                baseDelay: config.motion.delay + 0.04,
                step: config.motion.stagger,
                duration: config.motion.duration,
              })}
            >
              {/* Avatar */}
              <div className="h-9 w-9 shrink-0 overflow-hidden rounded-full bg-foreground/[0.06] mt-0.5">
                <img
                  src={msg.avatar}
                  alt={msg.name}
                  className="h-full w-full object-cover"
                  loading="lazy"
                />
              </div>

              {/* Content */}
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-sm font-body font-medium text-foreground/70">
                    {msg.name}
                  </span>
                  <span className="text-[10px] font-body text-foreground/20 tabular-nums">
                    {msg.date}
                  </span>
                </div>
                <p className="mt-1.5 text-sm font-body text-foreground/45 leading-relaxed">
                  {msg.content}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
    </PageShell>
  );
};

export default Guestbook;
