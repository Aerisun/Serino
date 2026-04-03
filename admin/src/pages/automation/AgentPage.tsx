import { lazy, Suspense } from "react";
import { PageHeader } from "@/components/PageHeader";
import { useI18n } from "@/i18n";
import { Navigate, useParams } from "react-router-dom";
import { AgentSectionSwitch } from "./AgentSectionSwitch";
import { SectionLoader } from "@/components/SectionLoader";
import AdminNotFoundPage from "@/pages/AdminNotFoundPage";

const AgentActivitySection = lazy(() =>
  import("./AgentActivitySection").then((module) => ({
    default: module.AgentActivitySection,
  })),
);
const AgentWebhooksSection = lazy(() =>
  import("./AgentWebhooksSection").then((module) => ({
    default: module.AgentWebhooksSection,
  })),
);
const AgentWorkflowsSection = lazy(() =>
  import("./AgentWorkflowsSection").then((module) => ({
    default: module.AgentWorkflowsSection,
  })),
);

const validSections = ["workflows", "activity", "webhooks"] as const;

export default function AgentPage() {
  const { t } = useI18n();
  const { section } = useParams();

  if (!section) {
    return <Navigate to="/agent/workflows" replace />;
  }

  if (!validSections.includes(section as (typeof validSections)[number])) {
    return <AdminNotFoundPage />;
  }

  const sectionContent =
    section === "activity" ? (
      <AgentActivitySection />
    ) : section === "webhooks" ? (
      <AgentWebhooksSection />
    ) : (
      <AgentWorkflowsSection />
    );

  return (
    <div>
      <PageHeader
        title={t("nav.agent")}
        description={t("agent.description")}
        secondary={<AgentSectionSwitch />}
      />
      <Suspense fallback={<SectionLoader label={t("common.loading")} />}>
        {sectionContent}
      </Suspense>
    </div>
  );
}
