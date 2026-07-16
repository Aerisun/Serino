import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getGetContentSubscriptionConfigApiV1AdminSubscriptionsConfigGetQueryKey,
  getGetProfileApiV1AdminSiteConfigProfileGetQueryKey,
  getListDiaryAccessRequestsApiV1AdminModerationDiaryAccessRequestsGetQueryKey,
  listDiaryAccessRequestsApiV1AdminModerationDiaryAccessRequestsGet,
  updateDiaryAccessRequestApiV1AdminModerationDiaryAccessRequestsRequestIdPatch,
  useGetContentSubscriptionConfigApiV1AdminSubscriptionsConfigGet,
  useGetProfileApiV1AdminSiteConfigProfileGet,
  useUpdateProfileApiV1AdminSiteConfigProfilePut,
} from "@serino/api-client/admin";
import type {
  DiaryAccessRequestAdminList,
  DiaryAccessRequestAdminRead,
  SiteProfileAdminRead,
} from "@serino/api-client/models";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { DataTable } from "@/components/DataTable";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import { Textarea } from "@/components/ui/Textarea";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { formatDate } from "@/lib/utils";
import { toast } from "sonner";
import { MODERATION_ATTENTION_COUNT_QUERY_KEY } from "./moderationQueries";

const PAGE_SIZE = 20;
const DEFAULT_ACCESS_DAYS = 7;
const DIARY_ACCESS_FEEDBACK_TEMPLATE_FLAG = "diary_access_feedback_template";
const DEFAULT_DIARY_ACCESS_FEEDBACK_TEMPLATE =
  "你好，{visitor_name}：\n\n站长已处理你的日记查看申请。\n审核结果：{decision}\n权限到期时间：{expires_at}\n\n站点地址：{site_url}";

interface DiaryAccessRow {
  id: string;
  siteUserId: string;
  visitorEmail: string;
  visitorDisplayName: string;
  visitorAvatarUrl: string;
  visitorAuthProvider: string;
  visitorOauthProviders: string[];
  reason: string;
  status: string;
  hasAccess: boolean;
  accessGrantedAt: string | null;
  accessExpiresAt: string | null;
  accessRevokedAt: string | null;
  remainingSeconds: number | null;
  createdAt: string;
  updatedAt: string;
}

const stringify = (value: unknown) => (typeof value === "string" ? value : value == null ? "" : String(value));
const toBoolean = (value: unknown) => value === true;
const toNumberOrNull = (value: unknown) => {
  const numberValue = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numberValue) ? numberValue : null;
};
const toRecord = (value: unknown): Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value) ? (value as Record<string, unknown>) : {};

type SubscriptionMailConfig = {
  smtp_test_passed?: boolean;
  smtp_auth_mode?: string;
  smtp_host?: string;
  smtp_port?: number;
  smtp_username?: string;
  smtp_password?: string;
  smtp_from_email?: string;
  smtp_oauth_tenant?: string;
  smtp_oauth_client_id?: string;
  smtp_oauth_client_secret?: string;
  smtp_oauth_refresh_token?: string;
};

const normalizeRow = (item: DiaryAccessRequestAdminRead): DiaryAccessRow => ({
  id: stringify(item.id),
  siteUserId: stringify(item.site_user_id),
  visitorEmail: stringify(item.visitor_email),
  visitorDisplayName: stringify(item.visitor_display_name),
  visitorAvatarUrl: stringify(item.visitor_avatar_url),
  visitorAuthProvider: stringify(item.visitor_auth_provider),
  visitorOauthProviders: Array.isArray(item.visitor_oauth_providers)
    ? item.visitor_oauth_providers.map(stringify).filter(Boolean)
    : [],
  reason: stringify(item.reason),
  status: stringify(item.status),
  hasAccess: toBoolean(item.has_access),
  accessGrantedAt: stringify(item.access_granted_at) || null,
  accessExpiresAt: stringify(item.access_expires_at) || null,
  accessRevokedAt: stringify(item.access_revoked_at) || null,
  remainingSeconds: toNumberOrNull(item.remaining_seconds),
  createdAt: stringify(item.created_at),
  updatedAt: stringify(item.updated_at),
});

const formatDateTimeLocalInput = (date: Date) => {
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

const defaultExpiryInput = () => {
  const date = new Date();
  date.setDate(date.getDate() + DEFAULT_ACCESS_DAYS);
  return formatDateTimeLocalInput(date);
};

const toDateTimeLocalInput = (value?: string | null) => {
  if (!value) {
    return defaultExpiryInput();
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? defaultExpiryInput() : formatDateTimeLocalInput(date);
};

const fromDateTimeLocalInput = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
};

function formatRemaining(seconds: number | null, t: (key: string, values?: Record<string, string | number>) => string) {
  if (seconds == null || seconds <= 0) {
    return "";
  }
  const days = Math.floor(seconds / 86_400);
  const hours = Math.floor((seconds % 86_400) / 3_600);
  if (days > 0) {
    return t("moderation.diaryAccessRemainingDays", { days, hours });
  }
  const minutes = Math.max(1, Math.floor((seconds % 3_600) / 60));
  if (hours > 0) {
    return t("moderation.diaryAccessRemainingHours", { hours, minutes });
  }
  return t("moderation.diaryAccessRemainingMinutes", { minutes });
}

function identityLabel(row: DiaryAccessRow) {
  return row.visitorDisplayName || row.visitorEmail || row.siteUserId;
}

function readFeedbackTemplate(profile?: SiteProfileAdminRead) {
  const template = toRecord(profile?.feature_flags)[DIARY_ACCESS_FEEDBACK_TEMPLATE_FLAG];
  return typeof template === "string" && template.trim()
    ? template
    : DEFAULT_DIARY_ACCESS_FEEDBACK_TEMPLATE;
}

function isMailFeedbackAvailable(config?: SubscriptionMailConfig) {
  if (!config?.smtp_test_passed || !config.smtp_host?.trim() || !config.smtp_port || !config.smtp_from_email?.trim()) {
    return false;
  }
  if (config.smtp_auth_mode === "microsoft_oauth2") {
    return Boolean(
      config.smtp_oauth_tenant?.trim() &&
        config.smtp_oauth_client_id?.trim() &&
        config.smtp_oauth_client_secret?.trim() &&
        config.smtp_oauth_refresh_token?.trim(),
    );
  }
  if (config.smtp_username?.trim() && !config.smtp_password?.trim()) {
    return false;
  }
  return true;
}

export function DiaryAccessRequestsPanel() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [expiresById, setExpiresById] = useState<Record<string, string>>({});
  const [feedbackTemplateOpen, setFeedbackTemplateOpen] = useState(false);
  const [feedbackTemplate, setFeedbackTemplate] = useState(DEFAULT_DIARY_ACCESS_FEEDBACK_TEMPLATE);
  const { data: profileRaw } = useGetProfileApiV1AdminSiteConfigProfileGet();
  const { data: subscriptionRaw } = useGetContentSubscriptionConfigApiV1AdminSubscriptionsConfigGet();
  const profile = profileRaw?.data as SiteProfileAdminRead | undefined;
  const subscriptionConfig = subscriptionRaw?.data as SubscriptionMailConfig | undefined;
  const mailFeedbackAvailable = isMailFeedbackAvailable(subscriptionConfig);
  const savedFeedbackTemplate = useMemo(() => readFeedbackTemplate(profile), [profile]);

  const params = useMemo(() => ({ page, page_size: PAGE_SIZE }), [page]);
  const queryKey = getListDiaryAccessRequestsApiV1AdminModerationDiaryAccessRequestsGetQueryKey(params);
  const { data, isLoading } = useQuery({
    queryKey,
    queryFn: () => listDiaryAccessRequestsApiV1AdminModerationDiaryAccessRequestsGet(params),
  });

  const rows = useMemo(
    () => (data?.data.items ?? []).map((item) => normalizeRow(item as DiaryAccessRequestAdminRead)),
    [data?.data.items],
  );
  const summary = data?.data as DiaryAccessRequestAdminList | undefined;
  const total = Number(summary?.total ?? 0);
  const peopleTotal = Number(summary?.people_total ?? 0);
  const pendingTotal = Number(summary?.pending_total ?? 0);
  const authorizedTotal = Number(summary?.authorized_total ?? 0);

  const updateAccess = useMutation({
    mutationFn: ({
      row,
      grant,
      revoke,
    }: {
      row: DiaryAccessRow;
      grant?: boolean;
      revoke?: boolean;
    }) => {
      const expiresInput = expiresById[row.id] ?? toDateTimeLocalInput(row.accessExpiresAt) ?? defaultExpiryInput();
      const expiresAt = fromDateTimeLocalInput(expiresInput) ?? fromDateTimeLocalInput(defaultExpiryInput());
      return updateDiaryAccessRequestApiV1AdminModerationDiaryAccessRequestsRequestIdPatch(row.id, {
        grant_access: grant,
        revoke_access: Boolean(revoke),
        expires_at: grant ? expiresAt : undefined,
      });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: getListDiaryAccessRequestsApiV1AdminModerationDiaryAccessRequestsGetQueryKey(),
        }),
        queryClient.invalidateQueries({ queryKey: MODERATION_ATTENTION_COUNT_QUERY_KEY }),
      ]);
      toast.success(t("common.operationSuccess"));
    },
    onError: (error) => {
      toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
    },
  });

  const saveProfile = useUpdateProfileApiV1AdminSiteConfigProfilePut({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getGetProfileApiV1AdminSiteConfigProfileGetQueryKey(),
        });
        queryClient.invalidateQueries({
          queryKey: getGetContentSubscriptionConfigApiV1AdminSubscriptionsConfigGetQueryKey(),
        });
        setFeedbackTemplateOpen(false);
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const openFeedbackTemplateDialog = () => {
    setFeedbackTemplate(savedFeedbackTemplate);
    setFeedbackTemplateOpen(true);
  };

  const saveFeedbackTemplate = () => {
    const nextFeatureFlags = {
      ...toRecord(profile?.feature_flags),
      [DIARY_ACCESS_FEEDBACK_TEMPLATE_FLAG]: feedbackTemplate.trim() || DEFAULT_DIARY_ACCESS_FEEDBACK_TEMPLATE,
    };
    saveProfile.mutate({
      data: {
        name: profile?.name ?? "",
        title: profile?.title ?? "",
        bio: profile?.bio ?? "",
        role: profile?.role ?? "",
        hero_video_url: profile?.hero_video_url ?? "",
        feature_flags: nextFeatureFlags,
      },
    });
  };

  const renderPermissionStatus = (row: DiaryAccessRow) => {
    if (row.status === "pending") {
      return (
        <div className="flex items-center gap-2">
          <Badge variant="warning">{t("moderation.diaryAccessPending")}</Badge>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-auto px-0 py-0 text-xs font-medium text-destructive underline-offset-4 hover:bg-transparent hover:text-destructive/80 hover:underline"
            onClick={(event) => {
              event.stopPropagation();
              updateAccess.mutate({ row, revoke: true });
            }}
            disabled={updateAccess.isPending}
          >
            {t("moderation.diaryAccessIgnore")}
          </Button>
        </div>
      );
    }

    if (row.hasAccess) {
      return (
        <Badge variant="success">
          {t("moderation.diaryAccessAuthorized")}（{formatRemaining(row.remainingSeconds, t)}）
        </Badge>
      );
    }

    return <Badge variant="secondary">{t("moderation.diaryAccessUnauthorized")}</Badge>;
  };

  return (
    <>
      <Card>
        <CardContent className="space-y-5 pt-6">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="text-lg font-semibold tracking-tight">
                  {t("moderation.diaryAccessRequests")}
                </h2>
                {mailFeedbackAvailable ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="sm:ml-2"
                    onClick={openFeedbackTemplateDialog}
                  >
                    {t("moderation.diaryAccessFeedbackTemplateAction")}
                  </Button>
                ) : null}
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {t("moderation.diaryAccessRequestsDescription")}
              </p>
            </div>
            <div className="flex max-w-full flex-wrap items-center gap-2 xl:justify-end">
              <Badge variant="secondary" className="gap-2 px-3.5 py-2 text-sm">
                <span className="text-muted-foreground">{t("common.all")}</span>
                <span className="text-base font-semibold tabular-nums">{peopleTotal}</span>
              </Badge>
              <Badge variant="destructive" className="gap-2 px-3.5 py-2 text-sm">
                <span>{t("moderation.statPending")}</span>
                <span className="text-base font-semibold tabular-nums">{pendingTotal}</span>
              </Badge>
              <Badge variant="success" className="gap-2 px-3.5 py-2 text-sm">
                <span>{t("moderation.diaryAccessAuthorizedTotal")}</span>
                <span className="text-base font-semibold tabular-nums">{authorizedTotal}</span>
              </Badge>
            </div>
          </div>

          <DataTable
            data={rows}
            total={total}
            page={page}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
            isLoading={isLoading}
            expandOnRowClick
            columns={[
              {
                header: t("moderation.diaryAccessVisitor"),
                accessor: (row) => identityLabel(row),
              },
              {
                header: t("moderation.diaryAccessRequestedAt"),
                accessor: (row) => formatDate(row.createdAt),
              },
              {
                header: t("moderation.diaryAccessPermissionStatus"),
                className: "min-w-[8.5rem] whitespace-nowrap",
                accessor: renderPermissionStatus,
              },
            ]}
            renderCells={(row) => (
              <>
                <td className="p-4 align-middle">
                  <div className="flex items-center gap-3">
                    {row.visitorAvatarUrl ? (
                      <img
                        src={row.visitorAvatarUrl}
                        alt=""
                        className="h-9 w-9 rounded-full border border-border/50 object-cover"
                      />
                    ) : (
                      <div className="flex h-9 w-9 items-center justify-center rounded-full border border-border/50 bg-muted text-xs text-muted-foreground">
                        {identityLabel(row).slice(0, 1).toUpperCase()}
                      </div>
                    )}
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{identityLabel(row)}</div>
                      <div className="truncate text-xs text-muted-foreground">{row.visitorEmail}</div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        <Badge variant="outline">{row.visitorAuthProvider || "email"}</Badge>
                        {row.visitorOauthProviders.map((provider) => (
                          <Badge key={provider} variant="secondary">
                            {provider}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                </td>
                <td className="p-4 align-middle text-sm text-muted-foreground">{formatDate(row.createdAt)}</td>
                <td className="min-w-[8.5rem] whitespace-nowrap p-4 align-middle">
                  {renderPermissionStatus(row)}
                </td>
              </>
            )}
            renderExpandedRow={(row) => {
              const expiresValue = expiresById[row.id] ?? toDateTimeLocalInput(row.accessExpiresAt) ?? defaultExpiryInput();
              return (
                <div className="space-y-5 py-5">
                  <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
                    <div className="rounded-2xl border border-border/45 bg-background/70 p-4">
                      <p className="text-xs font-medium text-muted-foreground">
                        {t("moderation.diaryAccessReason")}
                      </p>
                      <p className="mt-2 max-h-40 overflow-y-auto whitespace-pre-wrap pr-2 text-sm leading-6 text-foreground/82">
                        {row.reason || t("common.noData")}
                      </p>
                    </div>
                    <div className="space-y-3 rounded-2xl border border-border/45 bg-background/70 p-4">
                      <div className="space-y-2">
                        <Label>{t("moderation.diaryAccessExpiresAt")}</Label>
                        <Input
                          type="datetime-local"
                          value={expiresValue}
                          onChange={(event) =>
                            setExpiresById((current) => ({
                              ...current,
                              [row.id]: event.target.value,
                            }))
                          }
                        />
                      </div>
                      <div className="flex flex-wrap items-center justify-between gap-3 px-3 sm:px-4">
                        <Button
                          size="sm"
                          className="min-w-[7rem] justify-center"
                          onClick={() => updateAccess.mutate({ row, grant: true })}
                          disabled={updateAccess.isPending}
                        >
                          {row.hasAccess
                            ? t("moderation.diaryAccessExtend")
                            : t("moderation.diaryAccessGrantNow")}
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          className="min-w-[7rem] justify-center"
                          onClick={() => updateAccess.mutate({ row, revoke: true })}
                          disabled={updateAccess.isPending || !row.hasAccess}
                        >
                          {t("moderation.diaryAccessRevokeNow")}
                        </Button>
                      </div>
                    </div>
                  </div>
                  <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-3">
                    <span>{t("moderation.diaryAccessStatus")}: {row.status}</span>
                    <span>{t("moderation.diaryAccessGrantedAt")}: {formatDate(row.accessGrantedAt)}</span>
                    <span>{t("moderation.diaryAccessRevokedAt")}: {formatDate(row.accessRevokedAt)}</span>
                  </div>
                </div>
              );
            }}
          />
        </CardContent>
      </Card>

      <Dialog open={feedbackTemplateOpen} onOpenChange={setFeedbackTemplateOpen}>
        <DialogContent className="max-w-2xl rounded-2xl">
          <DialogHeader className="text-left">
            <DialogTitle>{t("moderation.diaryAccessFeedbackTemplateTitle")}</DialogTitle>
            <DialogDescription>
              {t("moderation.diaryAccessFeedbackTemplateDescription")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>{t("moderation.diaryAccessFeedbackTemplateField")}</Label>
              <Textarea
                value={feedbackTemplate}
                onChange={(event) => setFeedbackTemplate(event.target.value)}
                rows={11}
                className="min-h-72 font-mono text-xs leading-5"
              />
              <div className="flex justify-start pt-1">
                <LabelWithHelp
                  className="gap-1.5"
                  label={
                    <span className="text-xs font-medium text-muted-foreground">
                      {t("moderation.diaryAccessFeedbackTemplateVariablesHelpLabel")}
                    </span>
                  }
                  title={t("moderation.diaryAccessFeedbackTemplateVariables")}
                  description={t("moderation.diaryAccessFeedbackTemplateVariablesDescription")}
                  usageTitle={t("moderation.diaryAccessFeedbackTemplateVariablesUsage")}
                  usageItems={[
                    t("moderation.diaryAccessFeedbackTemplatePlaceholderSiteName"),
                    t("moderation.diaryAccessFeedbackTemplatePlaceholderSiteUrl"),
                    t("moderation.diaryAccessFeedbackTemplatePlaceholderVisitorName"),
                    t("moderation.diaryAccessFeedbackTemplatePlaceholderVisitorEmail"),
                    t("moderation.diaryAccessFeedbackTemplatePlaceholderDecision"),
                    t("moderation.diaryAccessFeedbackTemplatePlaceholderExpiresAt"),
                    t("moderation.diaryAccessFeedbackTemplatePlaceholderReason"),
                    t("moderation.diaryAccessFeedbackTemplatePlaceholderRequestedAt"),
                    t("moderation.diaryAccessFeedbackTemplatePlaceholderReviewedAt"),
                  ]}
                />
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setFeedbackTemplate(DEFAULT_DIARY_ACCESS_FEEDBACK_TEMPLATE)}
              disabled={saveProfile.isPending}
            >
              {t("moderation.diaryAccessFeedbackTemplateRestoreDefault")}
            </Button>
            <Button
              type="button"
              onClick={saveFeedbackTemplate}
              disabled={saveProfile.isPending}
            >
              {t("moderation.diaryAccessFeedbackTemplateConfirm")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
