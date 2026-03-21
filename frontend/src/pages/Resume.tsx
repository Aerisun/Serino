import { motion } from "motion/react";
import { Briefcase, GraduationCap, Code, Palette, Printer } from "lucide-react";
import PageShell from "@/components/PageShell";
import { staggerItem } from "@/config";
import { usePageConfig } from "@/contexts/RuntimeConfigContext";
import type { ResumeExperienceConfig, PageMotionConfig } from "@/config";
import type { BaseViewPageConfig } from "@/lib/page-config";

interface ResumePageConfig extends BaseViewPageConfig {
  downloadLabel?: string;
  bio?: string;
  skills?: string[];
  experience?: ResumeExperienceConfig[];
}

const Resume = () => {
  const config = usePageConfig().resume as ResumePageConfig;
  const skills = config.skills ?? [];
  const experience = config.experience ?? [];
  const motionConfig: PageMotionConfig = config.motion;

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaTitle={config.metaTitle}
      metaDescription={config.metaDescription}
      width={config.width}
      headerAside={
        <button
          type="button"
          onClick={() => window.print()}
          className="flex items-center gap-2 text-xs text-foreground/42 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.82)]"
        >
          {config.downloadLabel} <Printer className="h-3 w-3" />
        </button>
      }
    >
      <motion.p
        className="mt-8 max-w-2xl text-[0.935rem] font-body leading-7 text-foreground/50"
        {...staggerItem(0, {
          baseDelay: 0.06,
          step: 0,
          duration: motionConfig.duration,
        })}
      >
        {config.bio}
      </motion.p>

      <motion.div
        className="mt-12"
        {...staggerItem(1, {
          baseDelay: 0.1,
          step: 0,
          duration: motionConfig.duration,
        })}
      >
        <h2 className="mb-4 text-xs font-body font-medium uppercase tracking-[0.2em] text-foreground/25">
          技能
        </h2>
        <div className="flex flex-wrap gap-2">
          {skills.map((skill) => (
            <span
              key={skill}
              className="rounded-full liquid-glass px-3 py-1.5 text-xs font-body text-foreground/45 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.78)]"
            >
              {skill}
            </span>
          ))}
        </div>
      </motion.div>

      <motion.div
        className="mt-14"
        {...staggerItem(2, {
          baseDelay: 0.14,
          step: 0,
          duration: motionConfig.duration,
        })}
      >
        <h2 className="mb-6 text-xs font-body font-medium uppercase tracking-[0.2em] text-foreground/25">
          经历
        </h2>

        <div className="flex flex-col gap-0">
          {experience.map((item, i) => {
            const Icon = [Palette, Code, Briefcase, GraduationCap][i] ?? Briefcase;

            return (
              <div
                key={i}
                className="group flex gap-4 border-t border-foreground/[0.05] py-6 transition-colors hover:border-[rgb(var(--shiro-divider-rgb)/0.22)] first:border-t-0"
              >
                <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl liquid-glass transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.58)]">
                  <Icon className="h-4 w-4 text-foreground/35 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.58)]" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
                    <h3 className="text-sm font-body font-medium text-foreground/80 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.9)]">
                      {item.role}
                    </h3>
                    <span className="shrink-0 text-[11px] font-body tabular-nums text-foreground/20 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.52)]">
                      {item.period}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs font-body text-foreground/30 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.66)]">
                    {item.org}
                  </p>
                  <p className="mt-2 text-sm font-body leading-relaxed text-foreground/40 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.62)]">
                    {item.desc}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </motion.div>
    </PageShell>
  );
};

export default Resume;
