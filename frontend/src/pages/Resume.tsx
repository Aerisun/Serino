import { motion } from "motion/react";
import { Briefcase, GraduationCap, Code, Palette, Printer } from "lucide-react";
import PageShell from "@/components/PageShell";
import { pageConfig, staggerItem } from "@/config";

const Resume = () => {
  const config = pageConfig.resume;

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
          className="flex items-center gap-2 text-xs text-foreground/42 transition-colors hover:text-foreground/68"
        >
          {config.downloadLabel} <Printer className="h-3 w-3" />
        </button>
      }
    >

        {/* Bio */}
        <motion.p
          className="mt-8 text-[0.935rem] font-body text-foreground/50 leading-7 max-w-2xl"
          {...staggerItem(0, {
            baseDelay: 0.06,
            step: 0,
            duration: config.motion.duration,
          })}
        >
          {config.bio}
        </motion.p>

        {/* Skills */}
        <motion.div
          className="mt-12"
          {...staggerItem(1, {
            baseDelay: 0.1,
            step: 0,
            duration: config.motion.duration,
          })}
        >
          <h2 className="text-xs font-body font-medium text-foreground/25 uppercase tracking-[0.2em] mb-4">
            技能
          </h2>
          <div className="flex flex-wrap gap-2">
            {config.skills.map((skill) => (
              <span
                key={skill}
                className="text-xs font-body text-foreground/45 px-3 py-1.5 rounded-full liquid-glass"
              >
                {skill}
              </span>
            ))}
          </div>
        </motion.div>

        {/* Experience */}
        <motion.div
          className="mt-14"
          {...staggerItem(2, {
            baseDelay: 0.14,
            step: 0,
            duration: config.motion.duration,
          })}
        >
          <h2 className="text-xs font-body font-medium text-foreground/25 uppercase tracking-[0.2em] mb-6">
            经历
          </h2>

          <div className="flex flex-col gap-0">
            {config.experience.map((item, i) => {
              const Icon = [Palette, Code, Briefcase, GraduationCap][i] ?? Briefcase;

              return (
              <div
                key={i}
                className="group flex gap-4 py-6 border-t border-foreground/[0.05] first:border-t-0"
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl liquid-glass mt-0.5">
                  <Icon className="h-4 w-4 text-foreground/35" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex flex-col sm:flex-row sm:items-baseline sm:justify-between gap-1">
                    <h3 className="text-sm font-body font-medium text-foreground/80">
                      {item.role}
                    </h3>
                    <span className="text-[11px] font-body text-foreground/20 tabular-nums shrink-0">
                      {item.period}
                    </span>
                  </div>
                  <p className="text-xs font-body text-foreground/30 mt-0.5">{item.org}</p>
                  <p className="text-sm font-body text-foreground/40 leading-relaxed mt-2">
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
