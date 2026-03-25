import { motion } from "motion/react";
import CommentSection from "@/components/CommentSection";
import PageShell from "@/components/PageShell";
import { usePageConfig } from "@/contexts/runtime-config";
import type { BaseViewPageConfig } from "@/lib/page-config";

interface GuestbookPageConfig extends BaseViewPageConfig {
  namePlaceholder?: string;
  contentPlaceholder?: string;
  submitLabel?: string;
}

const Guestbook = () => {
  const config = usePageConfig().guestbook as unknown as GuestbookPageConfig;
  const guestbookPromptCopy = {
    name: config.namePlaceholder ?? "输入你想留下的名字",
    content: config.contentPlaceholder ?? "写下想问候、讨论或分享的内容",
    submit: config.submitLabel ?? "发表留言",
  };

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
    >
      <motion.div
        className="mt-10 space-y-4"
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: config.motion.duration,
          delay: config.motion.delay,
          ease: [0.16, 1, 0.3, 1],
        }}
      >
        <div className="liquid-glass rounded-[1.75rem] border border-[rgb(var(--shiro-border-rgb)/0.16)] p-5 text-sm font-body text-foreground/70">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-foreground/45">留言提示</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="rounded-full border border-[rgb(var(--shiro-border-rgb)/0.18)] px-3 py-1.5">
              昵称：{guestbookPromptCopy.name}
            </span>
            <span className="rounded-full border border-[rgb(var(--shiro-border-rgb)/0.18)] px-3 py-1.5">
              正文：{guestbookPromptCopy.content}
            </span>
            <span className="rounded-full border border-[rgb(var(--shiro-border-rgb)/0.18)] px-3 py-1.5">
              按钮：{guestbookPromptCopy.submit}
            </span>
          </div>
        </div>

        <CommentSection contentType="guestbook" />
      </motion.div>
    </PageShell>
  );
};

export default Guestbook;
