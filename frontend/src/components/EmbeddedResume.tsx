import { Mail, MapPin } from "lucide-react";
import MarkdownRenderer from "@/components/MarkdownRenderer";

interface EmbeddedResumeProps {
  name: string;
  content: string;
  profileImageUrl?: string;
  contacts?: {
    location?: string;
    email?: string;
  };
}

export default function EmbeddedResume({
  name,
  content,
  profileImageUrl,
  contacts,
}: EmbeddedResumeProps) {
  return (
    <section className="relative mx-auto max-w-[980px] px-2 py-4 md:py-6">
      <div className="pointer-events-none absolute inset-x-8 top-5 h-56 rounded-[3rem] bg-[radial-gradient(circle_at_top,rgb(var(--shiro-glow-rgb)/0.18),transparent_68%)] blur-3xl" />
      <div className="pointer-events-none absolute -right-10 top-10 h-28 w-28 rounded-full bg-[rgb(var(--shiro-accent-rgb)/0.14)] blur-3xl" />
      <div className="pointer-events-none absolute -left-8 bottom-8 h-24 w-24 rounded-full bg-[rgb(var(--shiro-panel-strong-rgb)/0.42)] blur-3xl" />

      <div className="relative overflow-hidden rounded-[2rem] border border-[rgb(var(--shiro-border-rgb)/0.14)] bg-background/[0.72] shadow-[0_18px_52px_rgba(10,14,24,0.12)] backdrop-blur-xl dark:bg-card/[0.82] dark:shadow-[0_24px_72px_rgba(0,0,0,0.26)]">
        <div className="pointer-events-none absolute inset-x-12 top-0 h-px bg-gradient-to-r from-transparent via-[rgb(var(--shiro-sheen-rgb)/0.96)] to-transparent" />
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgb(var(--shiro-glow-rgb)/0.12),transparent_38%),radial-gradient(circle_at_bottom_right,rgb(var(--shiro-accent-rgb)/0.08),transparent_36%)]" />

        <div className="relative px-6 py-7 md:px-8 md:py-8 lg:px-10 lg:py-10">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
            <div className="min-w-0 flex-1">
              <h2
                className="pl-2 text-[4.2rem] leading-[0.82] tracking-[-0.02em] text-foreground md:pl-3 md:text-[5.8rem]"
                style={{ fontFamily: '"Pinyon Script", cursive' }}
              >
                {name || "Your Name"}
              </h2>

              {contacts?.location || contacts?.email ? (
                <div className="mt-5 flex flex-wrap items-center gap-x-8 gap-y-2 pl-1 text-[0.98rem] tracking-[0.01em] text-foreground/58 md:pl-2">
                  {contacts?.location ? (
                    <span className="inline-flex whitespace-nowrap items-center gap-2">
                      <MapPin className="h-3.5 w-3.5 text-[rgb(var(--shiro-accent-rgb)/0.74)]" />
                      {contacts.location}
                    </span>
                  ) : null}
                  {contacts?.email ? (
                    <span className="inline-flex items-center gap-2 break-all">
                      <Mail className="h-3.5 w-3.5 text-[rgb(var(--shiro-accent-rgb)/0.74)]" />
                      {contacts.email}
                    </span>
                  ) : null}
                </div>
              ) : null}
            </div>

            <aside className="flex shrink-0 justify-start sm:justify-end sm:pr-4 lg:pr-10">
              {profileImageUrl ? (
                <div className="relative h-32 w-32 overflow-hidden rounded-[1.7rem] border border-[rgb(var(--shiro-border-rgb)/0.2)] bg-[rgb(var(--shiro-panel-rgb)/0.22)] p-1.5 shadow-[0_14px_32px_rgba(15,23,42,0.1)] dark:shadow-[0_16px_36px_rgba(0,0,0,0.18)]">
                  <div className="pointer-events-none absolute inset-0 rounded-[1.7rem] bg-[linear-gradient(145deg,transparent,rgb(var(--shiro-sheen-rgb)/0.2))]" />
                  <div className="absolute inset-1 rounded-[1.38rem] bg-[radial-gradient(circle_at_28%_28%,rgb(var(--shiro-glow-rgb)/0.28),transparent_58%)]" />
                  <img
                    src={profileImageUrl}
                    alt=""
                    className="relative z-10 h-full w-full rounded-[1.32rem] object-cover"
                  />
                </div>
              ) : (
                <div className="h-0 w-0" />
              )}
            </aside>
          </div>

          <div className="mt-6 border-t border-[rgb(var(--shiro-divider-rgb)/0.16)] pt-8">
            <MarkdownRenderer
              content={content}
              className="resume-markdown single-resume-markdown"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
