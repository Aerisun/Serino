import { useGetDeliveriesApiV1AdminAutomationDeliveriesGet, usePostDeliveryRetryApiV1AdminAutomationDeliveriesDeliveryIdRetryPost } from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { AdminSurface } from "@/components/AdminSurface";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useI18n } from "@/i18n";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

export default function DeliveriesPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: deliveriesRaw, isLoading: deliveriesLoading } = useGetDeliveriesApiV1AdminAutomationDeliveriesGet();
  const deliveries = deliveriesRaw?.data ?? [];

  const retryDelivery = usePostDeliveryRetryApiV1AdminAutomationDeliveriesDeliveryIdRetryPost({
    mutation: {
      onSuccess: () => { queryClient.invalidateQueries(); toast.success(t("common.operationSuccess")); },
      onError: (error: any) => { toast.error(error?.response?.data?.detail || t("common.operationFailed")); },
    },
  });

  return (
    <div>
      <PageHeader title={t("automation.deliveries")} description={t("automation.deliveriesDescription")} />
      <AdminSurface eyebrow="Deliveries" title={t("automation.deliveries")} description={t("automation.deliveriesDescription")}>
        <DataTable
          columns={[
            { header: "ID", accessor: (row) => <code className="text-xs">{row.id}</code> },
            { header: "Event", accessor: "event_type" },
            { header: "Target URL", accessor: (row) => <code className="text-xs break-all">{row.target_url}</code> },
            { header: t("automation.status"), accessor: (row) => <Badge variant="outline">{row.status}</Badge> },
            { header: "Attempts", accessor: "attempt_count" },
            { header: "HTTP", accessor: (row) => row.last_response_status ?? "-" },
            { header: "Error", accessor: (row) => row.last_error || "-" },
            { header: "Next Retry", accessor: (row) => row.next_attempt_at || "-" },
            { header: t("common.actions"), accessor: (row) => <Button size="sm" onClick={() => retryDelivery.mutate({ deliveryId: row.id })}>Retry</Button> },
          ]}
          data={deliveries as any[]}
          isLoading={deliveriesLoading}
        />
      </AdminSurface>
    </div>
  );
}
