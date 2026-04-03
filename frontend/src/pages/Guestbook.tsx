import CommentSection from "@/components/CommentSection";
import PageShell from "@/components/PageShell";
import { usePageConfig } from "@/contexts/runtime-config";
import type { BaseViewPageConfig } from "@/lib/page-config";

const Guestbook = () => {
  const config = usePageConfig().guestbook as BaseViewPageConfig;

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
