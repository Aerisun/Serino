import { lazy, Suspense } from "react";
import { PageHeader } from "@/components/PageHeader";
import { useI18n } from "@/i18n";
import { Navigate, useParams } from "react-router-dom";
import { MoreSectionSwitch } from "./MoreSectionSwitch";
import { SectionLoader } from "@/components/SectionLoader";
import AdminNotFoundPage from "@/pages/AdminNotFoundPage";

const ApiConfigSection = lazy(() =>
  import("./ApiConfigSection").then((module) => ({
    default: module.ApiConfigSection,
  })),
);
const ExternalConfigSection = lazy(() =>
  import("./ExternalConfigSection").then((module) => ({
    default: module.ExternalConfigSection,
  })),
);
const FeatureTogglesSection = lazy(() =>
  import("./FeatureTogglesSection").then((module) => ({
    default: module.FeatureTogglesSection,
  })),
);
const ProxyConfigSection = lazy(() =>
  import("./ProxyConfigSection").then((module) => ({
    default: module.ProxyConfigSection,
  })),
);
const ObjectStorageSection = lazy(() =>
  import("./ObjectStorageSection").then((module) => ({
    default: module.ObjectStorageSection,
  })),
);

export default function MorePage() {
  const { t } = useI18n();
  const { section } = useParams();
  const validSections = ["feature-flags", "mail-config", "api-config", "proxy-config", "object-storage"] as const;

  if (!section) {
    return <Navigate to="/more/feature-flags" replace />;
  }

  if (!validSections.includes(section as (typeof validSections)[number])) {
    return <AdminNotFoundPage />;
  }

  return (
    <div>
      <PageHeader
        title={t("nav.more")}
        description={t("more.description")}
        secondary={<MoreSectionSwitch />}
      />
      <Suspense fallback={<SectionLoader label={t("common.loading")} />}>
        {section === "mail-config" ? (
          <ExternalConfigSection />
        ) : section === "api-config" ? (
          <ApiConfigSection />
        ) : section === "object-storage" ? (
          <ObjectStorageSection />
        ) : section === "proxy-config" ? (
          <ProxyConfigSection />
        ) : (
          <FeatureTogglesSection />
        )}
      </Suspense>
    </div>
  );
}
