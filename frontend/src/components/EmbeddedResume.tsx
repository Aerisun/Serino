import { ArrowUpRight, Mail, MapPin } from "lucide-react";
import MarkdownRenderer from "@/components/MarkdownRenderer";

interface EmbeddedResumeProps {
  name: string;
  role?: string;
  content: string;
  profileImageUrl?: string;
  contacts?: {
    location?: string;
    email?: string;
    website?: string;
  };
}

function normalizeWebsite(website?: string) {
  if (!website) return "";
  if (website.startsWith("http://") || website.startsWith("https://")) return website;
  return `https://${website}`;
}

export default function EmbeddedResume({
  name,
  role,
  content,
  profileImageUrl,
  contacts,
}: EmbeddedResumeProps) {
  const contactItems = [
    contacts?.location ? { key: "location", label: "Base", value: contacts.location, icon: MapPin } : null,
    contacts?.email ? { key: "email", label: "Email", value: contacts.email, icon: Mail } : null,
  ].filter(Boolean) as Array<{ key: string; label: string; value: string; icon: typeof MapPin }>;

  return (
    <section className="relative mx-auto max-w-[960px] px-2 py-3">
      <div className="pointer-events-none absolute inset-x-12 bottom-5 top-10 rounded-[2rem] bg-[radial-gradient(circle_at_center,rgba(250,226,181,0.08),transparent_70%)] blur-3xl" />
      <div className="pointer-events-none absolute inset-x-6 inset-y-5 rounded-[2.2rem] border border-white/6 bg-[rgba(252,245,232,0.05)] rotate-[-1.2deg]" />
      <div className="pointer-events-none absolute inset-x-7 inset-y-4 rounded-[2.2rem] border border-white/8 bg-[rgba(255,248,238,0.05)] rotate-[0.8deg]" />

      <div className="relative overflow-hidden rounded-[2rem] border border-white/55 bg-[linear-gradient(165deg,rgba(253,248,242,0.95),rgba(249,251,255,0.96))] shadow-[0_26px_80px_rgba(6,10,18,0.18)]">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-[radial-gradient(circle_at_top,rgba(214,163,92,0.08),transparent_72%)]" />

        <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_280px]">
          <div className="px-6 py-8 md:px-10 md:py-9">
            <div className="border-b border-black/7 pb-5">
              <div className="mb-3 flex items-center gap-3">
                <span className="text-[0.72rem] font-semibold uppercase tracking-[0.32em] text-black/34">
                  Resume
                </span>
                <span className="h-px flex-1 bg-gradient-to-r from-black/10 to-transparent" />
              </div>
              <h2
                className="font-['Instrument_Serif'] text-[3.2rem] leading-[0.92] tracking-[-0.06em] text-black/88 md:text-[4.25rem]"
                style={{ fontFamily: '"Instrument Serif", serif' }}
              >
                {name || "Your Name"}
              </h2>
              {role ? (
                <p className="mt-3 max-w-2xl text-[0.98rem] font-medium uppercase tracking-[0.16em] text-black/52">
                  {role}
                </p>
              ) : null}
            </div>

            <div className="pt-6">
              <MarkdownRenderer content={content} className="resume-markdown single-resume-markdown text-black/72" />
            </div>
          </div>

          <aside className="border-t border-black/7 bg-[linear-gradient(180deg,rgba(255,255,255,0.42),rgba(255,255,255,0.58))] px-6 py-8 backdrop-blur lg:border-l lg:border-t-0 md:px-7 md:py-9">
            {profileImageUrl ? (
              <div className="mb-6">
                <div className="relative mx-auto h-28 w-28 overflow-hidden rounded-[1.9rem] border border-white/85 bg-[linear-gradient(145deg,rgba(255,255,255,0.9),rgba(248,240,229,0.9))] p-1.5 shadow-[0_14px_30px_rgba(15,23,42,0.12)]">
                  <div className="absolute inset-1 rounded-[1.45rem] bg-[radial-gradient(circle_at_30%_30%,rgba(214,163,92,0.14),transparent_55%)]" />
                  <img src={profileImageUrl} alt="" className="relative z-10 h-full w-full rounded-[1.35rem] object-cover" />
                </div>
                <p className="mt-3 text-center text-[10px] uppercase tracking-[0.22em] text-black/38">
                  Portrait
                </p>
              </div>
            ) : null}

            <div className="space-y-3">
              {contactItems.map(({ key, label, value, icon: Icon }) => (
                <div key={key} className="rounded-[1rem] border border-black/7 bg-white/78 px-4 py-3 shadow-[0_8px_24px_rgba(15,23,42,0.03)]">
                  <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] text-black/34">
                    <Icon className="h-3 w-3" />
                    {label}
                  </div>
                  <div className="mt-2 break-all text-sm leading-7 text-black/68">{value}</div>
                </div>
              ))}

              {contacts?.website ? (
                <a
                  href={normalizeWebsite(contacts.website)}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-between rounded-[1rem] border border-black/7 bg-white/78 px-4 py-3 text-sm text-black/68 shadow-[0_8px_24px_rgba(15,23,42,0.03)] transition hover:border-black/18 hover:text-black/86"
                >
                  <span className="truncate">{contacts.website}</span>
                  <ArrowUpRight className="ml-3 h-4 w-4 shrink-0" />
                </a>
              ) : null}
            </div>
          </aside>
        </div>
      </div>
    </section>
  );
}
