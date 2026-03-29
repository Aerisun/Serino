import type { ContentSubscriptionConfigAdminUpdate } from "@serino/api-client/models";
import { adminRequest } from "./admin-request";

export interface SubscriptionTestResult {
  recipient: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface SubscriptionSubscriberItem {
  email: string;
  is_active: boolean;
  content_types: string[];
  auth_mode: "email" | "binding" | "unknown";
  initiator_email: string | null;
  display_name: string | null;
  avatar_url: string | null;
  primary_auth_provider: string | null;
  oauth_providers: string[];
  sent_count: number;
  last_sent_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubscriptionDeliveryItem {
  id: string;
  subscriber_email: string;
  content_type: string;
  content_slug: string;
  content_title: string;
  content_url: string;
  status: string;
  error_message: string | null;
  sent_at: string | null;
  created_at: string;
  updated_at: string;
}

interface ListSubscribersParams {
  mode?: "all" | "email" | "binding" | "subscriber";
  search?: string;
  page?: number;
  page_size?: number;
}

interface ListSubscriberMessagesParams {
  page?: number;
  page_size?: number;
}

export const SUBSCRIPTION_TEST_RECIPIENT = "do-not-reply@course.pku.edu.cn";

export function buildSubscriptionTestFailureMessage(detail?: string): string {
  const base = `给测试邮箱：${SUBSCRIPTION_TEST_RECIPIENT}发送邮件失败`;
  return detail?.trim() ? `${base}。${detail.trim()}` : base;
}

export async function sendSubscriptionTestEmail(
  data: ContentSubscriptionConfigAdminUpdate,
): Promise<SubscriptionTestResult> {
  try {
    return await adminRequest<SubscriptionTestResult>(
      "/api/v1/admin/subscriptions/config/test",
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    );
  } catch (error) {
    const detail =
      error instanceof Error ? error.message : "请检查网络连接或后端服务状态";
    throw new Error(buildSubscriptionTestFailureMessage(detail));
  }
}

export function listSubscriptionSubscribers(
  params: ListSubscribersParams = {},
): Promise<PaginatedResponse<SubscriptionSubscriberItem>> {
  const query = new URLSearchParams();
  query.set("mode", params.mode ?? "all");
  query.set("page", String(params.page ?? 1));
  query.set("page_size", String(params.page_size ?? 20));
  if (params.search?.trim()) {
    query.set("search", params.search.trim());
  }
  return adminRequest<PaginatedResponse<SubscriptionSubscriberItem>>(
    `/api/v1/admin/subscriptions/subscribers?${query.toString()}`,
  );
}

export function listSubscriptionSubscriberMessages(
  email: string,
  params: ListSubscriberMessagesParams = {},
): Promise<PaginatedResponse<SubscriptionDeliveryItem>> {
  const query = new URLSearchParams();
  query.set("page", String(params.page ?? 1));
  query.set("page_size", String(params.page_size ?? 20));
  return adminRequest<PaginatedResponse<SubscriptionDeliveryItem>>(
    `/api/v1/admin/subscriptions/subscribers/${encodeURIComponent(email)}/messages?${query.toString()}`,
  );
}
