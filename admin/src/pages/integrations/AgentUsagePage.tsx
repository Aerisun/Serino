import { useGetAgentUsageApiV1AdminIntegrationsAgentUsageGet } from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { AdminSurface } from "@/components/AdminSurface";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/i18n";
import { Copy } from "lucide-react";
import { toast } from "sonner";

export default function AgentUsagePage() {
  const { t } = useI18n();
  const { data: raw, isLoading } = useGetAgentUsageApiV1AdminIntegrationsAgentUsageGet();
  const item = raw?.data?.item;

  const copyText = async (text: string) => {
    await navigator.clipboard.writeText(text);
    toast.success(t("common.operationSuccess"));
  };

  const docsUrl = item?.docs_url ?? "/api/agent/usage";
  const mcpEndpoint = item?.mcp?.endpoint ?? "/api/mcp";

  return (
    <div>
      <PageHeader title={t("integrations.agentUsage")} description={t("integrations.agentUsageDescription")} />

      <div className="grid gap-4">
        <AdminSurface eyebrow="Docs" title={t("integrations.usageUrl")} description={t("integrations.usageUrlHint")}
        >
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <code className="block break-all rounded-md bg-muted/60 px-3 py-2 text-xs">{docsUrl}</code>
            <Button variant="outline" size="sm" onClick={() => copyText(docsUrl)}>
              <Copy className="mr-2 h-4 w-4" />
              Copy
            </Button>
          </div>
        </AdminSurface>

        <AdminSurface eyebrow="MCP" title={t("integrations.mcpEndpoint")} description={t("integrations.mcpEndpointHint")}
        >
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <code className="block break-all rounded-md bg-muted/60 px-3 py-2 text-xs">{mcpEndpoint}</code>
            <Button variant="outline" size="sm" onClick={() => copyText(mcpEndpoint)}>
              <Copy className="mr-2 h-4 w-4" />
              Copy
            </Button>
          </div>
        </AdminSurface>

        <AdminSurface
          eyebrow={t("integrations.capabilities")}
          title={t("integrations.visibleTools")}
          description={t("integrations.visibleToolsHint")}
        >
          {isLoading ? (
            <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
          ) : (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                {(item?.mcp?.tools ?? []).map((tool) => (
                  <Badge key={tool.name} variant="outline" className="font-mono">
                    {tool.name}
                  </Badge>
                ))}
                {(item?.mcp?.tools ?? []).length === 0 && (
                  <p className="text-sm text-muted-foreground">{t("integrations.noVisibleTools")}</p>
                )}
              </div>

              <div className="flex flex-wrap gap-2">
                {(item?.mcp?.resources ?? []).map((res) => (
                  <Badge key={res.name} variant="outline" className="font-mono">
                    {res.name}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </AdminSurface>

        <AdminSurface
          eyebrow={t("integrations.skillMaps")}
          title={t("integrations.skillMaps")}
          description={t("integrations.skillMapsHint")}
        >
          {isLoading ? (
            <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
          ) : (
            <div className="space-y-2">
              {(item?.skill_maps ?? []).map((m) => (
                <div
                  key={m.id}
                  className="rounded-[var(--admin-radius-lg)] border border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))] p-4"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="font-medium truncate">{m.name}</div>
                      <div className="text-xs text-muted-foreground break-words">{m.description}</div>
                    </div>
                    <Badge variant="outline" className="font-mono">
                      v{m.version}
                    </Badge>
                  </div>
                </div>
              ))}
              {(item?.skill_maps ?? []).length === 0 && (
                <p className="text-sm text-muted-foreground">{t("integrations.noSkillMaps")}</p>
              )}
            </div>
          )}
        </AdminSurface>

        <AdminSurface eyebrow="Auth" title={t("integrations.recommendedScopes")} description={t("integrations.mcpScopesHint")}>
          <div className="flex flex-wrap gap-2">
            {(item?.recommended_scopes ?? []).map((s) => (
              <Badge key={s} variant="outline" className="font-mono">
                {s}
              </Badge>
            ))}
          </div>
        </AdminSurface>
      </div>
    </div>
  );
}
