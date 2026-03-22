import { PageHeader } from "@/components/PageHeader";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/Tabs";
import { useI18n } from "@/i18n";
import { ProfileTab } from "./tabs/ProfileTab";
import { SocialLinksTab } from "./tabs/SocialLinksTab";
import { PoemsTab } from "./tabs/PoemsTab";
import { PagesTab } from "./tabs/PagesTab";
import { NavItemsTab } from "./tabs/NavItemsTab";
import { CommunityTab } from "./tabs/CommunityTab";

export default function SiteConfigPage() {
  const { t } = useI18n();
  return (
    <div>
      <PageHeader title={t("siteConfig.title")} description={t("siteConfig.description")} />
      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="profile">{t("siteConfig.profile")}</TabsTrigger>
          <TabsTrigger value="social">{t("siteConfig.socialLinks")}</TabsTrigger>
          <TabsTrigger value="poems">{t("siteConfig.poems")}</TabsTrigger>
          <TabsTrigger value="pages">{t("siteConfig.pages")}</TabsTrigger>
          <TabsTrigger value="nav">导航菜单</TabsTrigger>
          <TabsTrigger value="community">{t("siteConfig.community")}</TabsTrigger>
        </TabsList>

        <TabsContent value="profile"><ProfileTab /></TabsContent>
        <TabsContent value="social"><SocialLinksTab /></TabsContent>
        <TabsContent value="poems"><PoemsTab /></TabsContent>
        <TabsContent value="pages"><PagesTab /></TabsContent>
        <TabsContent value="nav"><NavItemsTab /></TabsContent>
        <TabsContent value="community"><CommunityTab /></TabsContent>
      </Tabs>
    </div>
  );
}
