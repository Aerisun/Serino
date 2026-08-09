import {
  getGetDeadLettersApiV1AdminAutomationDeadLettersGetQueryKey,
  getGetDeliveriesApiV1AdminAutomationDeliveriesGetQueryKey,
  useGetDeadLettersApiV1AdminAutomationDeadLettersGet,
  usePostDeadLetterReplayApiV1AdminAutomationDeadLettersDeadLetterIdReplayPost,
} from "@serino/api-client/admin";
import type { WebhookDeadLetterRead } from "@serino/api-client/models";
import { PageHeader } from "@/components/PageHeader";
import { AdminSurface } from "@/components/AdminSurface";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useState } from "react";
import { formatDate } from "@/lib/utils";
import { AutomationQueryError } from "./AutomationQueryError";

export function DeadLettersPanel() {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const [pendingReplay, setPendingReplay] = useState<WebhookDeadLetterRead | null>(null);
  const { data: raw, isLoading, isError, refetch } = useGetDeadLettersApiV1AdminAutomationDeadLettersGet();
  const items = raw?.data ?? [];

  const replayDeadLetter = usePostDeadLetterReplayApiV1AdminAutomationDeadLettersDeadLetterIdReplayPost({
    mutation: {
      onSuccess: async () => {
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: getGetDeadLettersApiV1AdminAutomationDeadLettersGetQueryKey() }),
          queryClient.invalidateQueries({ queryKey: getGetDeliveriesApiV1AdminAutomationDeliveriesGetQueryKey() }),
        ]);
        setPendingReplay(null);
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => { toast.error(extractApiErrorMessage(error, t("common.operationFailed"))); },
    },
  });

  return (
    <AdminSurface eyebrow="DLQ" title={t("automation.deadLetters")} description={t("automation.deadLettersDescription")}>
      {isError ? (
        <AutomationQueryError lang={lang} onRetry={() => void refetch()} />
      ) : (
      <DataTable<WebhookDeadLetterRead>
        columns={[
          { header: lang === "zh" ? "事件" : "Event", accessor: "event_type" },
          { header: lang === "zh" ? "失败原因" : "Reason", accessor: "reason" },
          { header: lang === "zh" ? "失败时间" : "Failed at", accessor: (row) => formatDate(row.dead_lettered_at) },
          { header: lang === "zh" ? "投递 ID" : "Delivery ID", accessor: (row) => <code className="text-xs">{row.delivery_id}</code> },
          {
            header: t("common.actions"),
            accessor: (row) => (
              <Button size="sm" variant="outline" onClick={() => setPendingReplay(row)}>
                {lang === "zh" ? "重新投递" : "Replay"}
              </Button>
            ),
          },
        ]}
        data={items}
        isLoading={isLoading}
      />
      )}

      <ConfirmDialog
        open={pendingReplay !== null}
        title={lang === "zh" ? "确认重新投递？" : "Replay this delivery?"}
        description={lang === "zh"
          ? "系统会创建一次新的投递尝试，请先确认目标服务已经恢复。"
          : "A new delivery attempt will be created. Confirm that the target service has recovered."}
        confirmLabel={lang === "zh" ? "确认投递" : "Replay"}
        isPending={replayDeadLetter.isPending}
        onCancel={() => setPendingReplay(null)}
        onConfirm={() => {
          if (pendingReplay) replayDeadLetter.mutate({ deadLetterId: pendingReplay.id });
        }}
      />
    </AdminSurface>
  );
}

export default function DeadLettersPage() {
  const { t } = useI18n();

  return (
    <div>
      <PageHeader title={t("automation.deadLetters")} description={t("automation.deadLettersDescription")} />
      <DeadLettersPanel />
    </div>
  );
}
