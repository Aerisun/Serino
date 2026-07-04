import { motion } from "motion/react";
import EmbeddedResume from "@/components/EmbeddedResume";
import PageShell from "@/components/PageShell";
import { staggerItem } from "@/config";
import { usePageConfig } from "@/contexts/runtime-config";
import type { PageMotionConfig } from "@/lib/runtime-config";
import type { BaseViewPageConfig } from "@/lib/page-config";

interface ResumePageConfig extends BaseViewPageConfig {
  bio?: string;
  profileImageUrl?: string;
  contacts?: {
    location?: string;
    email?: string;
  };
}

const Resume = () => {
  const config = usePageConfig().resume as unknown as ResumePageConfig;
  const motionConfig: PageMotionConfig = config.motion;

  return (
    <PageShell
      eyebrow=""
      title=""
      description=""
      metaTitle={config.metaTitle}
      metaDescription={config.metaDescription}
      metaAuthor={config.title}
      width="wide"
      contentClassName="mt-0"
      mainClassName="max-sm:!px-4 max-sm:!pb-8"
      footerClassName="max-sm:!mt-6"
      compactHeader
    >
      <motion.div
        {...staggerItem(0, {
          baseDelay: 0.04,
          step: 0,
          duration: motionConfig.duration,
        })}
      >
        <EmbeddedResume
          name={config.title}
          content={config.bio ?? ""}
          profileImageUrl={config.profileImageUrl}
          contacts={config.contacts}
        />
      </motion.div>
    </PageShell>
  );
};

export default Resume;
