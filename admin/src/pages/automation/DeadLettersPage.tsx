import { useGetDeadLettersApiV1AdminAutomationDeadLettersGet, usePostDeadLetterReplayApiV1AdminAutomationDeadLettersDeadLetterIdReplayPost } from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { AdminSurface } from "@/components/AdminSurface";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

export function DeadLettersPanel() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: raw, isLoading } = useGetDeadLettersApiV1AdminAutomationDeadLettersGet();
  const items = raw?.data ?? [];

  const replayDeadLetter = usePostDeadLetterReplayApiV1AdminAutomationDeadLettersDeadLetterIdReplayPost({
    mutation: {
      onSuccess: () => { queryClient.invalidateQueries(); toast.success(t("common.operationSuccess")); },
      onError: (error: any) => { toast.error(extractApiErrorMessage(error, t("common.operationFailed"))); },
    },
  });

  return (
    <AdminSurface eyebrow="DLQ" title={t("automation.deadLetters")} description={t("automation.deadLettersDescription")}>
      <DataTable
        columns={[
          { header: "ID", accessor: (row) => <code className="text-xs">{row.id}</code> },
          { header: "Event", accessor: "event_type" },
          { header: "Reason", accessor: "reason" },
          { header: "Delivery", accessor: (row) => <code className="text-xs">{row.delivery_id}</code> },
          { header: t("common.actions"), accessor: (row) => <Button size="sm" onClick={() => replayDeadLetter.mutate({ deadLetterId: row.id })}>Replay</Button> },
        ]}
        data={items as any[]}
        isLoading={isLoading}
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
