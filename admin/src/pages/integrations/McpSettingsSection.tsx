import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getMcpConfig, updateMcpConfig } from "@/api/endpoints/mcp";
import { AdminSurface } from "@/components/AdminSurface";
import { AppleSwitch } from "@/components/ui/AppleSwitch";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import { McpApiKeysSection } from "./McpApiKeysSection";

const MCP_SETTINGS_QUERY_KEY = ["admin", "mcp-config", "settings"];

function ReadonlyField({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-[var(--admin-radius-lg)] border border-border/60 bg-background/55 px-4 py-4">
      <div className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
      <code className="mt-3 block break-all rounded-md bg-muted/60 px-3 py-2 text-xs">{value}</code>
      {hint ? <p className="mt-3 text-sm text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function McpSettingsSection() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: config, isLoading } = useQuery({
    queryKey: MCP_SETTINGS_QUERY_KEY,
    queryFn: () => getMcpConfig(),
  });

  const save = useMutation({
    mutationFn: (checked: boolean) => updateMcpConfig({ public_access: checked }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin", "mcp-config"] });
      toast.success(t("common.operationSuccess"));
    },
    onError: (error: Error) => {
      toast.error(error.message || t("common.operationFailed"));
    },
  });

  const togglePublicAccess = async (checked: boolean) => {
    try {
      await save.mutateAsync(checked);
    } catch {
      return;
    }
  };

  if (isLoading || !config) {
    return <p className="py-4 text-sm text-muted-foreground">{t("common.loading")}</p>;
  }

  return (
    <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,7fr)]">
      <AdminSurface
        eyebrow={t("integrations.tabs.settings")}
        title={t("integrations.mcpAccess")}
        description={t("integrations.mcpAccessDescription")}
      >
        <div className="space-y-4">
          <AppleSwitch
            checked={config.public_access}
            onCheckedChange={(checked) => void togglePublicAccess(checked)}
            label={config.public_access ? t("integrations.mcpEnabled") : t("integrations.mcpDisabled")}
            description={t("integrations.mcpSettingsDescription")}
            disabled={save.isPending}
          />

          <ReadonlyField
            label={t("integrations.mcpEndpoint")}
            value={config.endpoint}
            hint={t("integrations.mcpEndpointHint")}
          />
          <ReadonlyField
            label={t("integrations.usageUrl")}
            value={config.usage_url}
            hint={t("integrations.usageUrlHint")}
          />
        </div>
      </AdminSurface>

      <McpApiKeysSection />
    </div>
  );
}
