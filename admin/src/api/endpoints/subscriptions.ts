import type { ContentSubscriptionConfigAdminUpdate } from "@serino/api-client/models";
import { getAdminToken } from "@/lib/storage";

export interface SubscriptionTestResult {
  recipient: string;
}

export const SUBSCRIPTION_TEST_RECIPIENT = "do-not-reply@course.pku.edu.cn";

export function buildSubscriptionTestFailureMessage(detail?: string): string {
  const base = `给测试邮箱：${SUBSCRIPTION_TEST_RECIPIENT}发送邮件失败`;
  return detail?.trim() ? `${base}。${detail.trim()}` : base;
}

export async function sendSubscriptionTestEmail(
  data: ContentSubscriptionConfigAdminUpdate,
): Promise<SubscriptionTestResult> {
  const token = getAdminToken();
  if (!token) {
    throw new Error("未登录，无法测试发信");
  }

  let response: Response;
  try {
    response = await fetch("/api/v1/admin/subscriptions/config/test", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    });
  } catch {
    throw new Error(buildSubscriptionTestFailureMessage("请检查网络连接或后端服务状态"));
  }

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(
      buildSubscriptionTestFailureMessage(
        typeof payload?.detail === "string" ? payload.detail : undefined,
      ),
    );
  }
  return payload as SubscriptionTestResult;
}
