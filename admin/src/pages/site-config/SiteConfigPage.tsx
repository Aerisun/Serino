import { lazy, Suspense } from "react";
import { PageHeader } from "@/components/PageHeader";
import { AdminSectionTabs } from "@/components/ui/AdminSectionTabs";
import { useI18n } from "@/i18n";
import { Blocks, FileText, MessageSquareMore, Quote, ScrollText, UserRound } from "lucide-react";
import { useParams } from "react-router-dom";
import { SectionLoader } from "@/components/SectionLoader";
import AdminNotFoundPage from "@/pages/AdminNotFoundPage";

const ProfileTab = lazy(() =>
  import("./tabs/ProfileTab").then((module) => ({
    default: module.ProfileTab,
  })),
);
const SocialLinksTab = lazy(() =>
  import("./tabs/SocialLinksTab").then((module) => ({
    default: module.SocialLinksTab,
  })),
);
const PoemsTab = lazy(() =>
  import("./tabs/PoemsTab").then((module) => ({
    default: module.PoemsTab,
  })),
);
const PagesTab = lazy(() =>
  import("./tabs/PagesTab").then((module) => ({
    default: module.PagesTab,
  })),
);
const NavItemsTab = lazy(() =>
  import("./tabs/NavItemsTab").then((module) => ({
    default: module.NavItemsTab,
  })),
);
const CommunityTab = lazy(() =>
  import("./tabs/CommunityTab").then((module) => ({
    default: module.CommunityTab,
  })),
);

export default function SiteConfigPage() {
  const { t } = useI18n();
  const { section } = useParams();
  const validSections = ["profile", "social", "poems", "pages", "nav", "community"] as const;

  if (section && !validSections.includes(section as (typeof validSections)[number])) {
    return <AdminNotFoundPage />;
  }

  const tab = section ?? "profile";

  const items = [
    {
      value: "profile",
      to: "/site-config",
      end: true,
      label: t("siteConfig.tabs.profile"),
      description: t("siteConfig.sectionDescriptions.profile"),
      icon: UserRound,
    },
    {
      value: "social",
      to: "/site-config/social",
      label: t("siteConfig.tabs.social"),
      description: t("siteConfig.sectionDescriptions.social"),
      icon: Blocks,
    },
    {
      value: "poems",
      to: "/site-config/poems",
      label: t("siteConfig.tabs.poems"),
      description: t("siteConfig.sectionDescriptions.poems"),
      icon: Quote,
    },
    {
      value: "pages",
      to: "/site-config/pages",
      label: t("siteConfig.tabs.pages"),
      description: t("siteConfig.sectionDescriptions.pages"),
      icon: FileText,
    },
    {
      value: "nav",
      to: "/site-config/nav",
      label: t("siteConfig.tabs.nav"),
      description: t("siteConfig.sectionDescriptions.nav"),
      icon: ScrollText,
    },
    {
      value: "community",
      to: "/site-config/community",
      label: t("siteConfig.tabs.community"),
      description: t("siteConfig.sectionDescriptions.community"),
      icon: MessageSquareMore,
    },
  ] as const;

  return (
    <div>
      <PageHeader
        title={t("siteConfig.title")}
        description={t("siteConfig.description")}
        secondary={<AdminSectionTabs items={items} className="w-fit" />}
      />
      <Suspense fallback={<SectionLoader label={t("common.loading")} />}>
        {tab === "social" ? (
          <SocialLinksTab />
        ) : tab === "poems" ? (
          <PoemsTab />
        ) : tab === "pages" ? (
          <PagesTab />
        ) : tab === "nav" ? (
          <NavItemsTab />
        ) : tab === "community" ? (
          <CommunityTab />
        ) : (
          <ProfileTab />
        )}
      </Suspense>
    </div>
  );
}
