import { motion } from "motion/react";
import { Briefcase, GraduationCap, Code, Palette, ArrowUpRight } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import FallingPetals from "@/components/FallingPetals";

const Resume = () => {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <FallingPetals />
      <Navbar />

      <main className="mx-auto max-w-3xl px-6 pt-28 pb-20 lg:px-8">
        {/* Header */}
        <motion.div
          className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
        >
          <div>
            <h1 className="text-3xl font-heading italic tracking-tight text-foreground sm:text-4xl">
              Felix
            </h1>
            <p className="mt-2 text-sm text-foreground/40">
              UI/UX Designer · Frontend Developer
            </p>
          </div>
          <a
            href="#"
            className="flex items-center gap-2 rounded-full liquid-glass px-4 py-2 text-xs font-body text-foreground/50 hover:text-foreground/70 transition-colors active:scale-[0.97] self-start sm:self-auto"
          >
            下载 PDF <ArrowUpRight className="h-3 w-3" />
          </a>
        </motion.div>

        {/* Bio */}
        <motion.p
          className="mt-8 text-[0.935rem] font-body text-foreground/50 leading-7 max-w-2xl"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.06, ease: [0.16, 1, 0.3, 1] }}
        >
          我做网页设计，也写前端，专注于将视觉美学与交互体验融合为一体。
          擅长设计系统搭建、动效设计和响应式开发，追求每一个像素的精确与每一帧动画的流畅。
        </motion.p>

        {/* Skills */}
        <motion.div
          className="mt-12"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
        >
          <h2 className="text-xs font-body font-medium text-foreground/25 uppercase tracking-[0.2em] mb-4">
            技能
          </h2>
          <div className="flex flex-wrap gap-2">
            {["React", "TypeScript", "Tailwind CSS", "Figma", "Framer Motion", "Next.js", "Vue", "Design Systems", "Responsive Design", "SVG/Canvas", "Git", "Node.js"].map((skill) => (
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
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.14, ease: [0.16, 1, 0.3, 1] }}
        >
          <h2 className="text-xs font-body font-medium text-foreground/25 uppercase tracking-[0.2em] mb-6">
            经历
          </h2>

          <div className="flex flex-col gap-0">
            {[
              {
                icon: Palette,
                role: "独立设计师 & 前端开发",
                org: "Freelance",
                period: "2024 — 至今",
                desc: "为多个品牌和创业团队提供从视觉设计到前端落地的全流程服务，专注个人品牌网站和产品界面设计。",
              },
              {
                icon: Code,
                role: "前端开发工程师",
                org: "某科技公司",
                period: "2022 — 2024",
                desc: "负责核心产品的前端架构和设计系统搭建，主导了暗色模式适配和动效体系的建立。",
              },
              {
                icon: Briefcase,
                role: "UI/UX 设计实习",
                org: "某设计工作室",
                period: "2021 — 2022",
                desc: "参与多个 B 端产品的界面设计，学习了从用户调研到交付的完整设计流程。",
              },
              {
                icon: GraduationCap,
                role: "数字媒体艺术",
                org: "某大学",
                period: "2018 — 2022",
                desc: "系统学习了视觉传达、交互设计和前端开发，毕业设计获院级优秀作品。",
              },
            ].map((item, i) => (
              <div
                key={i}
                className="group flex gap-4 py-6 border-t border-foreground/[0.05] first:border-t-0"
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl liquid-glass mt-0.5">
                  <item.icon className="h-4 w-4 text-foreground/35" />
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
            ))}
          </div>
        </motion.div>
      </main>
      <Footer />
    </div>
  );
};

export default Resume;
