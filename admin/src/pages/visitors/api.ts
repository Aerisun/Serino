import {
  deleteContentSubscriberApiV1AdminSubscriptionsSubscribersEmailDelete,
  listContentSubscriberMessagesApiV1AdminSubscriptionsSubscribersEmailMessagesGet,
  listContentSubscribersApiV1AdminSubscriptionsSubscribersGet,
  testContentSubscriptionConfigApiV1AdminSubscriptionsConfigTestPost,
  updateContentSubscriberApiV1AdminSubscriptionsSubscribersEmailPatch,
} from "@serino/api-client/admin";
import type {
  ContentNotificationDeliveryAdminRead,
  ContentSubscriberAdminRead,
  ContentSubscriberAdminUpdate,
  ContentSubscriptionConfigAdminUpdate,
  ContentSubscriptionTestResult,
  ListContentSubscriberMessagesApiV1AdminSubscriptionsSubscribersEmailMessagesGetParams,
  ListContentSubscribersApiV1AdminSubscriptionsSubscribersGetParams,
  PaginatedResponseContentNotificationDeliveryAdminRead,
  PaginatedResponseContentSubscriberAdminRead,
  TestContentSubscriptionConfigApiV1AdminSubscriptionsConfigTestPostParams,
} from "@serino/api-client/models";

export type SubscriptionTestResult = ContentSubscriptionTestResult;
export type PaginatedResponse<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};
export type SubscriptionSubscriberItem = ContentSubscriberAdminRead;
export type SubscriptionDeliveryItem = ContentNotificationDeliveryAdminRead;
type ListSubscribersParams = ListContentSubscribersApiV1AdminSubscriptionsSubscribersGetParams;
type ListSubscriberMessagesParams = ListContentSubscriberMessagesApiV1AdminSubscriptionsSubscribersEmailMessagesGetParams;
type UpdateSubscriberParams = ContentSubscriberAdminUpdate;

export const SUBSCRIPTION_TEST_RECIPIENT = "do-not-reply@course.pku.edu.cn";

export function buildSubscriptionTestFailureMessage(detail?: string): string {
  const base = `给测试邮箱：${SUBSCRIPTION_TEST_RECIPIENT}发送邮件失败`;
  return detail?.trim() ? `${base}。${detail.trim()}` : base;
}

export async function sendSubscriptionTestEmail(
  data: ContentSubscriptionConfigAdminUpdate,
  options?: { persistSuccess?: boolean },
): Promise<SubscriptionTestResult> {
  try {
    const params: TestContentSubscriptionConfigApiV1AdminSubscriptionsConfigTestPostParams | undefined =
      options?.persistSuccess ? { persist_success: true } : undefined;

    return await testContentSubscriptionConfigApiV1AdminSubscriptionsConfigTestPost(data, params).then(
      ({ data: result }) => result,
    );
  } catch (error) {
    const detail =
      error instanceof Error ? error.message : "请检查网络连接或后端服务状态";
    throw new Error(buildSubscriptionTestFailureMessage(detail));
  }
}

export function listSubscriptionSubscribers(
  params: ListSubscribersParams = {},
): Promise<PaginatedResponseContentSubscriberAdminRead> {
  return listContentSubscribersApiV1AdminSubscriptionsSubscribersGet({
    mode: params.mode ?? "all",
    page: params.page ?? 1,
    page_size: params.page_size ?? 20,
    search: params.search?.trim() || undefined,
  }).then(({ data }) => data);
}

export function listSubscriptionSubscriberMessages(
  email: string,
  params: ListSubscriberMessagesParams = {},
): Promise<PaginatedResponseContentNotificationDeliveryAdminRead> {
  return listContentSubscriberMessagesApiV1AdminSubscriptionsSubscribersEmailMessagesGet(email, {
    page: params.page ?? 1,
    page_size: params.page_size ?? 20,
  }).then(({ data }) => data);
}

export function updateSubscriptionSubscriber(
  email: string,
  params: UpdateSubscriberParams,
): Promise<SubscriptionSubscriberItem> {
  return updateContentSubscriberApiV1AdminSubscriptionsSubscribersEmailPatch(email, params).then(
    ({ data }) => data,
  );
}

export async function deleteSubscriptionSubscriber(email: string): Promise<null> {
  await deleteContentSubscriberApiV1AdminSubscriptionsSubscribersEmailDelete(email);
  return null;
}
