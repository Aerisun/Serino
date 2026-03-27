import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  getGetProfileApiV1AdminSiteConfigProfileGetQueryKey,
  useGetProfileApiV1AdminSiteConfigProfileGet,
  useUpdateProfileApiV1AdminSiteConfigProfilePut,
} from "@serino/api-client/admin";
import type { SiteProfileAdminRead } from "@serino/api-client/models";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { AppleSwitch } from "@/components/ui/AppleSwitch";
import { useI18n } from "@/i18n";
import { toast } from "sonner";

const recommendedScopes = ["mcp:connect", "mcp:content:read", "mcp:config:read"];
const liveTools = ["get_site_config", "list_posts", "get_post", "search_content"];
const liveResources = [
  "aerisun://site-config",
  "aerisun://posts",
  "aerisun://posts/{slug}",
  "aerisun://feeds/posts",
];

export default function McpPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: raw, isLoading } = useGetProfileApiV1AdminSiteConfigProfileGet();
  const profile = raw?.data as SiteProfileAdminRead | undefined;
  const [mcpEnabled, setMcpEnabled] = useState(false);

  useEffect(() => {
    setMcpEnabled(Boolean(profile?.feature_flags?.mcp_public_access));
  }, [profile]);

  const save = useUpdateProfileApiV1AdminSiteConfigProfilePut({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetProfileApiV1AdminSiteConfigProfileGetQueryKey() });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        const msg = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  const toggleMcp = async (checked: boolean) => {
    if (!profile) return;
    const previous = mcpEnabled;
    setMcpEnabled(checked);
    try {
      await save.mutateAsync({
        data: {
          name: profile.name,
          title: profile.title,
          bio: profile.bio,
          role: profile.role,
          footer_text: profile.footer_text,
          feature_flags: { ...(profile.feature_flags ?? {}), mcp_public_access: checked },
        },
      });
    } catch {
      setMcpEnabled(previous);
    }
  };

  return (
    <div>
      <PageHeader title={t("integrations.mcp")} description={t("integrations.mcpDescription")} />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t("integrations.endpoint")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <code className="block rounded-md bg-muted/60 px-3 py-2 text-sm">/api/mcp</code>
            <p className="text-sm text-muted-foreground">{t("integrations.mcpEndpointHint")}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t("integrations.authMethod")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Badge variant="info">Bearer API Key</Badge>
            <p className="text-sm text-muted-foreground">{t("integrations.mcpAuthHint")}</p>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg">{t("integrations.mcpAccess")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between gap-4 rounded-xl border border-border/60 bg-background/60 px-4 py-3">
              <div className="space-y-1">
                <div className="text-sm font-medium text-foreground">
                  {mcpEnabled ? t("integrations.mcpEnabled") : t("integrations.mcpDisabled")}
                </div>
                <div className="text-xs text-muted-foreground">{t("integrations.mcpAccessDescription")}</div>
              </div>
              <AppleSwitch
                checked={mcpEnabled}
                onCheckedChange={(checked) => void toggleMcp(checked)}
                disabled={isLoading || save.isPending}
              />
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg">{t("integrations.recommendedScopes")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {recommendedScopes.map((scope) => (
                <Badge key={scope} variant="outline" className="font-mono">
                  {scope}
                </Badge>
              ))}
            </div>
            <p className="text-sm text-muted-foreground">{t("integrations.mcpScopesHint")}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Live Tools</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {liveTools.map((tool) => (
              <Badge key={tool} variant="outline" className="mr-2 font-mono">
                {tool}
              </Badge>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Live Resources</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {liveResources.map((resource) => (
              <Badge key={resource} variant="outline" className="mr-2 mb-2 font-mono">
                {resource}
              </Badge>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
