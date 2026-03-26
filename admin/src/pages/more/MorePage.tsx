import { PageHeader } from "@/components/PageHeader";
import { useI18n } from "@/i18n";
import { MoreTab } from "@/pages/site-config/tabs/MoreTab";

export default function MorePage() {
  const { t } = useI18n();

  return (
    <div>
      <PageHeader
        title={t("nav.more")}
        description={t("siteConfig.featureFlagsDescription")}
      />
      <MoreTab />
    </div>
  );
}