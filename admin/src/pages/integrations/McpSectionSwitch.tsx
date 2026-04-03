import { AdminSectionTabs } from "@/components/ui/AdminSectionTabs";
import { useI18n } from "@/i18n";
import { Settings2, ShieldCheck } from "lucide-react";

interface McpSectionSwitchProps {
  permissionsDisabled?: boolean;
}

export function McpSectionSwitch({ permissionsDisabled = false }: McpSectionSwitchProps) {
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
      disabled: permissionsDisabled,
    },
  ] as const;

  return <AdminSectionTabs items={items} className="w-fit" />;
}
