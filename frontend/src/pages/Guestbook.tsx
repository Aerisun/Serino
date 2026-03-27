import CommentSection from "@/components/CommentSection";
import PageShell from "@/components/PageShell";
import { usePageConfig } from "@/contexts/runtime-config";
import type { BaseViewPageConfig } from "@/lib/page-config";

interface GuestbookPageConfig extends BaseViewPageConfig {
  promptTitle?: string;
  nameFieldLabel?: string;
  contentFieldLabel?: string;
  submitFieldLabel?: string;
  namePlaceholder?: string;
  contentPlaceholder?: string;
  submitLabel?: string;
}

const Guestbook = () => {
  const config = usePageConfig().guestbook as unknown as GuestbookPageConfig;

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
    >
      <div className="mt-10">
        <CommentSection contentType="guestbook" />
      </div>
    </PageShell>
  );
};

export default Guestbook;
