import { useQuery } from "@tanstack/react-query";
import { getSystemInfo } from "@/api/endpoints/system";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Server, Database, HardDrive, Clock, Code } from "lucide-react";
import { useI18n } from "@/i18n";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export default function SystemInfoPage() {
  const { t } = useI18n();
  const { data, isLoading } = useQuery({
    queryKey: ["system-info"],
    queryFn: getSystemInfo,
    refetchInterval: 30000,
  });

  const items = data ? [
    { label: t("systemInfo.version"), value: data.version, icon: Code },
    { label: t("systemInfo.python"), value: data.python_version, icon: Server },
    { label: t("systemInfo.dbSize"), value: formatBytes(data.db_size_bytes), icon: Database },
    { label: t("systemInfo.mediaSize"), value: formatBytes(data.media_dir_size_bytes), icon: HardDrive },
    { label: t("systemInfo.uptime"), value: formatUptime(data.uptime_seconds), icon: Clock },
    { label: t("systemInfo.environment"), value: data.environment, icon: Server },
  ] : [];

  return (
    <div>
      <PageHeader title={t("systemInfo.title")} description={t("systemInfo.description")} />
      {isLoading ? (
        <p className="text-muted-foreground">{t("common.loading")}</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <Card key={item.label}>
              <CardContent className="pt-4 pb-4 px-4">
                <div className="flex items-center gap-3">
                  <item.icon className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="text-xs text-muted-foreground">{item.label}</p>
                    <p className="text-lg font-semibold">{item.value}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
