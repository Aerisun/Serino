import { lazy, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { getMcpConfig } from "@/pages/integrations/api";
import { useI18n } from "@/i18n";
import { Navigate, useParams } from "react-router-dom";
import { McpSectionSwitch } from "./McpSectionSwitch";
import { SectionLoader } from "@/components/SectionLoader";
import AdminNotFoundPage from "@/pages/AdminNotFoundPage";

const McpPermissionsSection = lazy(() =>
  import("./McpPermissionsSection").then((module) => ({
    default: module.McpPermissionsSection,
  })),
);
const McpSettingsSection = lazy(() =>
  import("./McpSettingsSection").then((module) => ({
    default: module.McpSettingsSection,
  })),
);

const validSections = ["settings", "permissions"] as const;

export default function McpPage() {
  const { t } = useI18n();
  const { section } = useParams();
  const { data: config } = useQuery({
    queryKey: ["admin", "mcp-config", "settings"],
    queryFn: () => getMcpConfig(),
  });

  if (!section) {
    return <Navigate to="/integrations/mcp/settings" replace />;
  }

  if (!validSections.includes(section as (typeof validSections)[number])) {
    return <AdminNotFoundPage />;
  }

  if (section === "permissions" && config && !config.public_access) {
    return <Navigate to="/integrations/mcp/settings" replace />;
  }

  return (
    <div>
      <PageHeader
        title={t("integrations.mcp")}
        description={t("integrations.mcpDescription")}
        secondary={<McpSectionSwitch permissionsDisabled={Boolean(config && !config.public_access)} />}
      />
      <Suspense fallback={<SectionLoader label={t("common.loading")} />}>
        {section === "permissions" ? <McpPermissionsSection /> : <McpSettingsSection />}
      </Suspense>
    </div>
  );
}
