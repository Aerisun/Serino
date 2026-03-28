import { PageHeader } from "@/components/PageHeader";
import { Tabs, TabsContent } from "@/components/ui/Tabs";
import { useI18n } from "@/i18n";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { ExternalConfigSection } from "./ExternalConfigSection";
import { FeatureTogglesSection } from "./FeatureTogglesSection";
import { MoreSectionSwitch } from "./MoreSectionSwitch";

export default function MorePage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { section } = useParams();
  const validSections = ["feature-flags", "external-config"] as const;

  if (!section || !validSections.includes(section as (typeof validSections)[number])) {
    return <Navigate to="/more/feature-flags" replace />;
  }

  const goToSection = (value: string) => {
    navigate(`/more/${value}`);
  };

  return (
    <div>
      <PageHeader
        title={t("nav.more")}
        description={t("more.description")}
        secondary={<MoreSectionSwitch />}
      />
      <Tabs value={section} onValueChange={goToSection}>
        <TabsContent value="feature-flags">
          <FeatureTogglesSection />
        </TabsContent>
        <TabsContent value="external-config">
          <ExternalConfigSection />
        </TabsContent>
      </Tabs>
    </div>
  );
}
