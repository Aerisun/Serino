import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  getListPageCopyQueryKey,
  useListPageCopy,
  useUpdatePageCopy,
} from "@serino/api-client/admin";
import { ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { DirtySaveButton, PendingSaveBadge } from "@/components/ui/DirtySaveButton";
import { AppleSwitch } from "@/components/ui/AppleSwitch";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { FRIENDS_PAGE_KEY, parseBooleanLike, parsePositiveInteger } from "./friendConfig";

export function FriendsMoreConfigSection() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: pageCopyRaw, isLoading } = useListPageCopy();
  const pageCopy = useMemo(
    () => pageCopyRaw?.data?.items?.find((item) => item.page_key === FRIENDS_PAGE_KEY) ?? null,
    [pageCopyRaw],
  );
  const [form, setForm] = useState({
    randomRecentDays: "7",
    autoRefreshSeconds: "60",
    websiteHealthCheckEnabled: true,
    websiteHealthCheckIntervalMinutes: "360",
    rssHealthCheckEnabled: true,
    rssHealthCheckIntervalMinutes: "360",
  });
  const [websiteExpanded, setWebsiteExpanded] = useState(false);
  const [rssExpanded, setRssExpanded] = useState(false);
  const savedForm = useMemo(
    () => ({
      randomRecentDays: String(pageCopy?.extras?.randomRecentDays ?? 7),
      autoRefreshSeconds: String(pageCopy?.extras?.autoRefreshSeconds ?? 60),
      websiteHealthCheckEnabled: parseBooleanLike(pageCopy?.extras?.websiteHealthCheckEnabled, true),
      websiteHealthCheckIntervalMinutes: String(pageCopy?.extras?.websiteHealthCheckIntervalMinutes ?? 360),
      rssHealthCheckEnabled: parseBooleanLike(pageCopy?.extras?.rssHealthCheckEnabled, true),
      rssHealthCheckIntervalMinutes: String(pageCopy?.extras?.rssHealthCheckIntervalMinutes ?? 360),
    }),
    [pageCopy],
  );

  useEffect(() => {
    if (!pageCopy) {
      return;
    }
    setForm(savedForm);
  }, [pageCopy, savedForm]);

  const saveConfig = useUpdatePageCopy({
    mutation: {
      onSuccess: () => {
        void queryClient.invalidateQueries({ queryKey: getListPageCopyQueryKey() });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const hasChanges =
    form.randomRecentDays !== savedForm.randomRecentDays ||
    form.autoRefreshSeconds !== savedForm.autoRefreshSeconds ||
    form.websiteHealthCheckEnabled !== savedForm.websiteHealthCheckEnabled ||
    form.websiteHealthCheckIntervalMinutes !== savedForm.websiteHealthCheckIntervalMinutes ||
    form.rssHealthCheckEnabled !== savedForm.rssHealthCheckEnabled ||
    form.rssHealthCheckIntervalMinutes !== savedForm.rssHealthCheckIntervalMinutes;

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-10 text-sm text-muted-foreground">{t("common.loading")}</CardContent>
      </Card>
    );
  }

  if (!pageCopy) {
    return (
      <Card>
        <CardContent className="py-10 text-sm text-muted-foreground">
          {t("friends.moreConfigMissing")}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="gap-4 pb-5 sm:flex-row sm:items-start sm:justify-between sm:space-y-0">
        <div className="space-y-1">
          <CardTitle className="text-lg">{t("friends.moreConfigTitle")}</CardTitle>
          <p className="text-sm text-muted-foreground">{t("friends.moreConfigDescription")}</p>
        </div>
        <div className="flex items-center gap-2 self-start">
          {hasChanges ? <PendingSaveBadge /> : null}
          <DirtySaveButton
            dirty={hasChanges}
            saving={saveConfig.isPending}
            onClick={() =>
              saveConfig.mutate({
                itemId: pageCopy.id,
                data: {
                  extras: {
                    ...pageCopy.extras,
                    randomRecentDays: parsePositiveInteger(form.randomRecentDays, 7),
                    autoRefreshSeconds: parsePositiveInteger(form.autoRefreshSeconds, 60),
                    websiteHealthCheckEnabled: form.websiteHealthCheckEnabled,
                    websiteHealthCheckIntervalMinutes: parsePositiveInteger(form.websiteHealthCheckIntervalMinutes, 360),
                    rssHealthCheckEnabled: form.rssHealthCheckEnabled,
                    rssHealthCheckIntervalMinutes: parsePositiveInteger(form.rssHealthCheckIntervalMinutes, 360),
                  },
                },
              })
            }
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>{t("friends.randomRecentDays")}</Label>
            <Input
              type="number"
              min={1}
              value={form.randomRecentDays}
              onChange={(e) => setForm((prev) => ({ ...prev, randomRecentDays: e.target.value }))}
            />
          </div>
          <div className="space-y-2">
            <Label>{t("friends.autoRefreshSeconds")}</Label>
            <Input
              type="number"
              min={1}
              value={form.autoRefreshSeconds}
              onChange={(e) => setForm((prev) => ({ ...prev, autoRefreshSeconds: e.target.value }))}
            />
          </div>
        </div>

        <div className="space-y-4">
          <AppleSwitch
            checked={form.websiteHealthCheckEnabled}
            onCheckedChange={(checked) => setForm((prev) => ({ ...prev, websiteHealthCheckEnabled: checked }))}
            label={t("friends.websiteHealthCheckEnabled")}
            description={
              form.websiteHealthCheckEnabled
                ? t("friends.websiteHealthCheckRunning").replace("{minutes}", form.websiteHealthCheckIntervalMinutes || "360")
                : t("friends.websiteHealthCheckEnabledDesc")
            }
            switchLeading={
              form.websiteHealthCheckEnabled ? (
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    setWebsiteExpanded((current) => !current);
                  }}
                  aria-label={t("friends.websiteHealthCheckInterval")}
                  className="flex h-8 w-8 items-center justify-center rounded-full border border-border/60 bg-background/60 text-muted-foreground transition hover:text-foreground"
                >
                  <ChevronRight className={`h-4 w-4 transition-transform ${websiteExpanded ? "rotate-90" : ""}`} />
                </button>
              ) : null
            }
            expandableOpen={form.websiteHealthCheckEnabled && websiteExpanded}
            expandableDivider={false}
            expandableContent={
              <div className="space-y-2">
                <Label>{t("friends.websiteHealthCheckInterval")}</Label>
                <Input
                  type="number"
                  min={1}
                  value={form.websiteHealthCheckIntervalMinutes}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, websiteHealthCheckIntervalMinutes: event.target.value }))
                  }
                />
              </div>
            }
          />

          <AppleSwitch
            checked={form.rssHealthCheckEnabled}
            onCheckedChange={(checked) => setForm((prev) => ({ ...prev, rssHealthCheckEnabled: checked }))}
            label={t("friends.rssHealthCheckEnabled")}
            description={
              form.rssHealthCheckEnabled
                ? t("friends.rssHealthCheckRunning").replace("{minutes}", form.rssHealthCheckIntervalMinutes || "360")
                : t("friends.rssHealthCheckEnabledDesc")
            }
            switchLeading={
              form.rssHealthCheckEnabled ? (
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    setRssExpanded((current) => !current);
                  }}
                  aria-label={t("friends.rssHealthCheckInterval")}
                  className="flex h-8 w-8 items-center justify-center rounded-full border border-border/60 bg-background/60 text-muted-foreground transition hover:text-foreground"
                >
                  <ChevronRight className={`h-4 w-4 transition-transform ${rssExpanded ? "rotate-90" : ""}`} />
                </button>
              ) : null
            }
            expandableOpen={form.rssHealthCheckEnabled && rssExpanded}
            expandableDivider={false}
            expandableContent={
              <div className="space-y-2">
                <Label>{t("friends.rssHealthCheckInterval")}</Label>
                <Input
                  type="number"
                  min={1}
                  value={form.rssHealthCheckIntervalMinutes}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, rssHealthCheckIntervalMinutes: event.target.value }))
                  }
                />
              </div>
            }
          />
        </div>
      </CardContent>
    </Card>
  );
}
