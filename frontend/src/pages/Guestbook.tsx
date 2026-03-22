import { motion } from "motion/react";
import CommentSection from "@/components/CommentSection";
import PageShell from "@/components/PageShell";
import { usePageConfig } from "@/contexts/RuntimeConfigContext";
import type { BaseViewPageConfig } from "@/lib/page-config";

interface GuestbookPageConfig extends BaseViewPageConfig {
  namePlaceholder?: string;
  contentPlaceholder?: string;
  submitLabel?: string;
}

const Guestbook = () => {
  const config = usePageConfig().guestbook as GuestbookPageConfig;

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
    >
      <motion.div
        className="mt-10"
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: config.motion.duration,
          delay: config.motion.delay,
          ease: [0.16, 1, 0.3, 1],
        }}
      >
        <CommentSection contentType="guestbook" />
      </motion.div>
    </PageShell>
  );
};

export default Guestbook;
