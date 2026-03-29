import type { WebhookSubscriptionCreate } from "@serino/api-client/models";
import { adminRequest } from "./admin-request";

export interface WebhookTestResult {
  ok: boolean;
  provider: string;
  target_url: string;
  status_code: number | null;
  summary: string;
  response_body?: string | null;
}

export interface TelegramWebhookConnectResult {
  ok: boolean;
  status: string;
  summary: string;
  bot_username?: string | null;
  chat_id?: number | string | null;
  target_url?: string | null;
}

export function testWebhookSubscription(
  data: WebhookSubscriptionCreate,
  options?: { subscriptionId?: string | null },
) {
  const searchParams = new URLSearchParams();
  if (options?.subscriptionId) {
    searchParams.set("subscription_id", options.subscriptionId);
  }
  const path = searchParams.size
    ? `/api/v1/admin/automation/webhooks/test?${searchParams.toString()}`
    : "/api/v1/admin/automation/webhooks/test";

  return adminRequest<WebhookTestResult>(path, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function connectTelegramWebhook(botToken: string, sendTestMessage = true) {
  return adminRequest<TelegramWebhookConnectResult>("/api/v1/admin/automation/webhooks/telegram/connect", {
    method: "POST",
    body: JSON.stringify({
      bot_token: botToken,
      send_test_message: sendTestMessage,
    }),
  });
}
