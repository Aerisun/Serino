import { useListFeedsApiV1AdminIntegrationsFeedsGet } from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { AdminSurface } from "@/components/AdminSurface";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useI18n } from "@/i18n";
import { Copy, ExternalLink, Rss } from "lucide-react";
import { toast } from "sonner";
import type { FeedLinkRead } from "@serino/api-client/models";

export default function FeedsPage() {
  const { t } = useI18n();
  const { data: raw, isLoading } = useListFeedsApiV1AdminIntegrationsFeedsGet();
  const items = (raw?.data?.items ?? []) as FeedLinkRead[];

  const copyUrl = async (url: string) => {
    await navigator.clipboard.writeText(url);
    toast.success(t("integrations.feedCopied"));
  };

  return (
    <div>
      <PageHeader title={t("integrations.feeds")} description={t("integrations.feedsDescription")} />

      <div className="grid gap-4">
        <AdminSurface
          eyebrow="RSS"
          title={t("integrations.feedList")}
          description={t("integrations.feedListHint")}
        >
          {isLoading ? (
            <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
          ) : (
            <div className="space-y-3">
              {items.map((item) => (
                <div
                  key={item.key}
                  className="flex flex-col gap-3 rounded-[var(--admin-radius-lg)] border border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))] p-4 md:flex-row md:items-center md:justify-between"
                >
                  <div className="min-w-0 space-y-2">
                    <div className="flex items-center gap-2">
                      <Rss className="h-4 w-4 text-[rgb(var(--admin-accent-rgb)/0.8)]" />
                      <span className="font-medium text-foreground/95">{item.title}</span>
                      <Badge variant={item.enabled ? "success" : "outline"}>
                        {item.enabled ? t("integrations.enabled") : t("integrations.disabled")}
                      </Badge>
                    </div>
                    <code className="block break-all rounded-md bg-muted/60 px-3 py-2 text-xs">{item.url}</code>
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <Button variant="outline" size="sm" onClick={() => copyUrl(item.url)}>
                      <Copy className="mr-2 h-4 w-4" />
                      {t("integrations.copyUrl")}
                    </Button>
                    <Button variant="ghost" size="sm" asChild>
                      <a href={item.url} target="_blank" rel="noreferrer">
                        <ExternalLink className="mr-2 h-4 w-4" />
                        {t("integrations.open")}
                      </a>
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </AdminSurface>
      </div>
    </div>
  );
}
