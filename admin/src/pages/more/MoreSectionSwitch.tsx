import { AdminSectionTabs } from "@/components/ui/AdminSectionTabs";
import { useI18n } from "@/i18n";
import { Mail, Settings2 } from "lucide-react";

export function MoreSectionSwitch() {
  const { t } = useI18n();

  const items = [
    {
      value: "feature-flags",
      to: "/more/feature-flags",
      label: t("more.tabs.featureFlags"),
      description: t("more.sectionDescriptions.featureFlags"),
      icon: Settings2,
    },
    {
      value: "external-config",
      to: "/more/external-config",
      label: t("more.tabs.externalConfig"),
      description: t("more.sectionDescriptions.externalConfig"),
      icon: Mail,
    },
  ] as const;

  return <AdminSectionTabs items={items} />;
}
