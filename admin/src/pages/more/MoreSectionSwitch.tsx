import { AdminSectionTabs } from "@/components/ui/AdminSectionTabs";
import { useI18n } from "@/i18n";
import { Cpu, Mail, Plug, Settings2 } from "lucide-react";

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
      value: "mail-config",
      to: "/more/mail-config",
      label: t("more.tabs.mailConfig"),
      description: t("more.sectionDescriptions.mailConfig"),
      icon: Mail,
    },
    {
      value: "api-config",
      to: "/more/api-config",
      label: t("more.tabs.apiConfig"),
      description: t("more.sectionDescriptions.apiConfig"),
      icon: Cpu,
    },
    {
      value: "proxy-config",
      to: "/more/proxy-config",
      label: t("more.tabs.proxyConfig"),
      description: t("more.sectionDescriptions.proxyConfig"),
      icon: Plug,
    },
  ] as const;

  return <AdminSectionTabs items={items} className="w-fit" />;
}
