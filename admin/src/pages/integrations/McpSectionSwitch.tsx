import { AdminSectionTabs } from "@/components/ui/AdminSectionTabs";
import { useI18n } from "@/i18n";
import { Settings2, ShieldCheck } from "lucide-react";

export function McpSectionSwitch() {
  const { t } = useI18n();

  const items = [
    {
      value: "settings",
      to: "/integrations/mcp/settings",
      label: t("integrations.tabs.settings"),
      description: t("integrations.sectionDescriptions.mcpSettings"),
      icon: Settings2,
    },
    {
      value: "permissions",
      to: "/integrations/mcp/permissions",
      label: t("integrations.tabs.permissions"),
      description: t("integrations.sectionDescriptions.mcpPermissions"),
      icon: ShieldCheck,
    },
  ] as const;

  return <AdminSectionTabs items={items} />;
}
