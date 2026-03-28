import { PageHeader } from "@/components/PageHeader";
import { Tabs, TabsContent } from "@/components/ui/Tabs";
import { useI18n } from "@/i18n";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { AgentActivitySection } from "./AgentActivitySection";
import { AgentModelConfigSection } from "./AgentModelConfigSection";
import { AgentSectionSwitch } from "./AgentSectionSwitch";
import { AgentWebhooksSection } from "./AgentWebhooksSection";
import { AgentWorkflowsSection } from "./AgentWorkflowsSection";

const validSections = ["model-config", "workflows", "activity", "webhooks"] as const;

export default function AgentPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { section } = useParams();

  if (!section || !validSections.includes(section as (typeof validSections)[number])) {
    return <Navigate to="/agent/workflows" replace />;
  }

  const goToSection = (value: string) => {
    navigate(`/agent/${value}`);
  };

  return (
    <div>
      <PageHeader
        title={t("nav.agent")}
        description={t("agent.description")}
        secondary={<AgentSectionSwitch />}
      />
      <Tabs value={section} onValueChange={goToSection}>
        <TabsContent value="model-config">
          <AgentModelConfigSection />
        </TabsContent>
        <TabsContent value="workflows">
          <AgentWorkflowsSection />
        </TabsContent>
        <TabsContent value="activity">
          <AgentActivitySection />
        </TabsContent>
        <TabsContent value="webhooks">
          <AgentWebhooksSection />
        </TabsContent>
      </Tabs>
    </div>
  );
}
