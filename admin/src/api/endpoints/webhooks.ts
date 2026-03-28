import { getAdminToken } from "@/lib/storage";
import type { WebhookSubscriptionCreate } from "@serino/api-client/models";

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

async function adminRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAdminToken();
  if (!token) {
    throw new Error("未登录，无法执行管理操作");
  }

  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new Error("请求失败，请检查网络连接或后端服务状态");
  }

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? payload.detail
        : undefined;
    throw new Error(typeof detail === "string" ? detail : "操作失败");
  }
  return payload as T;
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
