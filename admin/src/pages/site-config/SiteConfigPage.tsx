import { PageHeader } from "@/components/PageHeader";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/Tabs";
import { useI18n } from "@/i18n";
import { useNavigate, useParams } from "react-router-dom";
import { ProfileTab } from "./tabs/ProfileTab";
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
    section && ["profile", "social", "poems", "pages", "nav", "community"].includes(section)
      ? section
      : "profile";

  const goToTab = (value: string) => {
    navigate(value === "profile" ? "/site-config" : `/site-config/${value}`);
  };

  return (
    <div>
      <PageHeader
        title={t("siteConfig.title")}
        description={t("siteConfig.description")}
      />
      <Tabs value={tab} onValueChange={goToTab}>
        <div className="overflow-x-auto -mx-1 px-1 pb-1">
          <TabsList className="inline-flex min-w-max">
            <TabsTrigger value="profile">
              {t("siteConfig.tabs.profile")}
            </TabsTrigger>
            <TabsTrigger value="social">
              {t("siteConfig.tabs.social")}
            </TabsTrigger>
            <TabsTrigger value="poems">
              {t("siteConfig.tabs.poems")}
            </TabsTrigger>
            <TabsTrigger value="pages">
              {t("siteConfig.tabs.pages")}
            </TabsTrigger>
            <TabsTrigger value="nav">{t("siteConfig.tabs.nav")}</TabsTrigger>
            <TabsTrigger value="community">
              {t("siteConfig.tabs.community")}
            </TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="profile">
          <ProfileTab />
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
