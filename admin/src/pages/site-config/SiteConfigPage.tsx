import { PageHeader } from "@/components/PageHeader";
import { AdminSectionTabs } from "@/components/ui/AdminSectionTabs";
import { Tabs, TabsContent } from "@/components/ui/Tabs";
import { useI18n } from "@/i18n";
import { Blocks, FileText, MessageSquareMore, Quote, ScrollText, UserRound, Globe } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { ProfileTab } from "./tabs/ProfileTab";
import { RuntimeTab } from "./tabs/RuntimeTab";
import { SocialLinksTab } from "./tabs/SocialLinksTab";
import { PoemsTab } from "./tabs/PoemsTab";
import { PagesTab } from "./tabs/PagesTab";
import { NavItemsTab } from "./tabs/NavItemsTab";
import { CommunityTab } from "./tabs/CommunityTab";

export default function SiteConfigPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { section } = useParams();
  const tab =
    section && ["profile", "runtime", "social", "poems", "pages", "nav", "community"].includes(section)
      ? section
      : "profile";

  const goToTab = (value: string) => {
    navigate(value === "profile" ? "/site-config" : `/site-config/${value}`);
  };

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
      value: "runtime",
      to: "/site-config/runtime",
      label: t("siteConfig.tabs.runtime"),
      description: t("siteConfig.sectionDescriptions.runtime"),
      icon: Globe,
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
        secondary={<AdminSectionTabs items={items} />}
      />
      <Tabs value={tab} onValueChange={goToTab}>
        <TabsContent value="profile">
          <ProfileTab />
        </TabsContent>
        <TabsContent value="runtime">
          <RuntimeTab />
        </TabsContent>
        <TabsContent value="social">
          <SocialLinksTab />
        </TabsContent>
        <TabsContent value="poems">
          <PoemsTab />
        </TabsContent>
        <TabsContent value="pages">
          <PagesTab />
        </TabsContent>
        <TabsContent value="nav">
          <NavItemsTab />
        </TabsContent>
        <TabsContent value="community">
          <CommunityTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
