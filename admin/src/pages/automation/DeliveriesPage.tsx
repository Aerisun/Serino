import { useGetDeliveriesApiV1AdminAutomationDeliveriesGet, usePostDeliveryRetryApiV1AdminAutomationDeliveriesDeliveryIdRetryPost } from "@serino/api-client/admin";
import type { WebhookDeliveryRead } from "@serino/api-client/models";
import { PageHeader } from "@/components/PageHeader";
import { AdminSurface } from "@/components/AdminSurface";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useI18n } from "@/i18n";
import { formatDate } from "@/lib/utils";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

const HTTP_ERROR_PATTERN = /http\s+(\d{3})/i;

function formatHttpFailure(status: number, lang: "zh" | "en") {
  if (lang === "zh") {
    if (status === 400) return "请求参数错误";
    if (status === 401 || status === 403) return "鉴权失败";
    if (status === 404) return "目标地址不存在";
    if (status === 429) return "请求过于频繁";
    if (status >= 500) return "目标服务异常";
    return "请求失败";
  }

  if (status === 400) return "Bad request";
  if (status === 401 || status === 403) return "Unauthorized or forbidden";
  if (status === 404) return "Target not found";
  if (status === 429) return "Rate limited";
  if (status >= 500) return "Target service error";
  return "Request failed";
}

function toFailureReason(row: WebhookDeliveryRead, lang: "zh" | "en") {
  const text = row.last_error?.trim();
  if (text) {
    const statusMatch = text.match(HTTP_ERROR_PATTERN);
    if (statusMatch) {
      return formatHttpFailure(Number(statusMatch[1]), lang);
    }
    if (/timeout|timed?\s*out/i.test(text)) {
      return lang === "zh" ? "请求超时" : "Request timed out";
    }
    if (/connection|network|refused|unreachable/i.test(text)) {
      return lang === "zh" ? "网络连接失败" : "Network error";
    }
    return lang === "zh" ? "发送失败" : "Delivery failed";
  }

  if (typeof row.last_response_status === "number") {
    return formatHttpFailure(row.last_response_status, lang);
  }

  return lang === "zh" ? "发送失败" : "Delivery failed";
}

function toStatusPresentation(row: WebhookDeliveryRead, lang: "zh" | "en") {
  if (row.status === "succeeded") {
    return {
      variant: "success" as const,
      borderClass: "border-green-300/80 dark:border-green-700/60",
      text: lang === "zh" ? "成功" : "Succeeded",
    };
  }

  if (row.last_error || (row.last_response_status ?? 0) >= 400 || row.status === "failed" || row.status === "dead_lettered") {
    return {
      variant: "destructive" as const,
      borderClass: "border-red-300/80 dark:border-red-700/60",
      text: toFailureReason(row, lang),
    };
  }

  return {
    variant: "outline" as const,
    borderClass: "",
    text: lang === "zh" ? "处理中" : "In progress",
  };
}

function toDisplayTime(row: WebhookDeliveryRead) {
  return row.last_attempt_at ?? row.delivered_at ?? row.created_at;
}

export function DeliveriesPanel() {
  const { lang, t } = useI18n();
  const queryClient = useQueryClient();
  const { data: deliveriesRaw, isLoading: deliveriesLoading } = useGetDeliveriesApiV1AdminAutomationDeliveriesGet();
  const deliveries = (deliveriesRaw?.data ?? []) as WebhookDeliveryRead[];
  const timeHeader = lang === "zh" ? "时间" : "Time";

  const retryDelivery = usePostDeliveryRetryApiV1AdminAutomationDeliveriesDeliveryIdRetryPost({
    mutation: {
      onSuccess: () => { queryClient.invalidateQueries(); toast.success(t("common.operationSuccess")); },
      onError: (error: any) => { toast.error(error?.response?.data?.detail || t("common.operationFailed")); },
    },
  });

  return (
    <AdminSurface eyebrow="Deliveries" title={t("automation.deliveries")} description={t("automation.deliveriesDescription")}>
      <DataTable<WebhookDeliveryRead>
        columns={[
          { header: "Event", accessor: "event_type" },
          {
            header: t("automation.status"),
            accessor: (row) => {
              const status = toStatusPresentation(row, lang);
              return <Badge variant={status.variant} className={status.borderClass}>{status.text}</Badge>;
            },
          },
          { header: "Attempts", accessor: "attempt_count" },
          { header: timeHeader, accessor: (row) => formatDate(toDisplayTime(row)) },
          { header: t("common.actions"), accessor: (row) => <Button size="sm" onClick={() => retryDelivery.mutate({ deliveryId: row.id })}>Retry</Button> },
        ]}
        data={deliveries}
        isLoading={deliveriesLoading}
      />
    </AdminSurface>
  );
}

export default function DeliveriesPage() {
  const { t } = useI18n();

  return (
    <div>
      <PageHeader title={t("automation.deliveries")} description={t("automation.deliveriesDescription")} />
      <DeliveriesPanel />
    </div>
  );
}
