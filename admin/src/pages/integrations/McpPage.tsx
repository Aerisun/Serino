import { PageHeader } from "@/components/PageHeader";
import { Tabs, TabsContent } from "@/components/ui/Tabs";
import { useI18n } from "@/i18n";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { McpPermissionsSection } from "./McpPermissionsSection";
import { McpSectionSwitch } from "./McpSectionSwitch";
import { McpSettingsSection } from "./McpSettingsSection";

const validSections = ["settings", "permissions"] as const;

export default function McpPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { section } = useParams();

  if (!section || !validSections.includes(section as (typeof validSections)[number])) {
    return <Navigate to="/integrations/mcp/settings" replace />;
  }

  const goToSection = (value: string) => {
    navigate(`/integrations/mcp/${value}`);
  };

  return (
    <div>
      <PageHeader
        title={t("integrations.mcp")}
        description={t("integrations.mcpDescription")}
        secondary={<McpSectionSwitch />}
      />
      <Tabs value={section} onValueChange={goToSection}>
        <TabsContent value="settings">
          <McpSettingsSection />
        </TabsContent>
        <TabsContent value="permissions">
          <McpPermissionsSection />
        </TabsContent>
      </Tabs>
    </div>
  );
}
