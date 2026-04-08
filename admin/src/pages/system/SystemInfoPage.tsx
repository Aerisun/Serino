import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuth } from "@/auth/useAuth";
import {
  changePasswordApiV1AdminAuthPasswordPut,
  getGetVisitorAuthConfigApiV1AdminVisitorsConfigGetQueryKey,
  listSessionsEndpointApiV1AdminAuthSessionsGet,
  revokeSessionApiV1AdminAuthSessionsSessionIdDelete,
  updateProfileEndpointApiV1AdminAuthProfilePut,
  useGetVisitorAuthConfigApiV1AdminVisitorsConfigGet,
  useListAdminIdentitiesApiV1AdminVisitorsAdminIdentitiesGet,
  useSystemInfoApiV1AdminSystemInfoGet,
  useUpdateVisitorAuthConfigApiV1AdminVisitorsConfigPut,
} from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ConfigSettingsCard } from "@/components/ConfigSettingsCard";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { Input } from "@/components/ui/Input";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Server, Database, HardDrive, Clock, Code, Monitor, Trash2 } from "lucide-react";
import { useI18n } from "@/i18n";
import type { AdminSessionRead, SystemInfo } from "@serino/api-client/models";
import { cn } from "@/lib/utils";
import { formatDateTimeInBeijing } from "@/lib/time";

type AdminConsoleMethod = "email" | "google" | "github";

function toAdminConsoleMethods(methods: string[] | undefined): AdminConsoleMethod[] {
  return (methods ?? []).filter(
    (method): method is AdminConsoleMethod =>
      method === "email" || method === "google" || method === "github",
  );
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function formatDateTime(dateStr: string): string {
  return formatDateTimeInBeijing(dateStr) || dateStr;
}

export default function SystemInfoPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [username, setUsername] = useState(user?.username || "");
  const [savedUsername, setSavedUsername] = useState(user?.username || "");
  const [adminConsoleAuthMethods, setAdminConsoleAuthMethods] = useState<
    AdminConsoleMethod[]
  >([]);
  const [savingAdminConsoleMethod, setSavingAdminConsoleMethod] =
    useState<AdminConsoleMethod | null>(null);
  const [profileSaving, setProfileSaving] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<string | null>(null);

  const { data: raw, isLoading } = useSystemInfoApiV1AdminSystemInfoGet({
    query: { refetchInterval: 30000 },
  });
  const { data: visitorAuthConfigRaw } =
    useGetVisitorAuthConfigApiV1AdminVisitorsConfigGet();
  const { data: adminIdentitiesRaw } =
    useListAdminIdentitiesApiV1AdminVisitorsAdminIdentitiesGet();

  const { data: sessions = [], isLoading: sessionsLoading } = useQuery({
    queryKey: ["admin-sessions"],
    queryFn: () => listSessionsEndpointApiV1AdminAuthSessionsGet().then((r) => r.data),
  });

  const saveAdminConfig = useUpdateVisitorAuthConfigApiV1AdminVisitorsConfigPut();

  const revokeMutation = useMutation({
    mutationFn: (id: string) => revokeSessionApiV1AdminAuthSessionsSessionIdDelete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-sessions"] });
      toast.success(t("common.operationSuccess"));
      setRevokeTarget(null);
    },
    onError: () => toast.error(t("common.operationFailed")),
  });

  const data = raw?.data as SystemInfo | undefined;
  const visitorAuthConfig = visitorAuthConfigRaw?.data;
  const adminIdentities = adminIdentitiesRaw?.data ?? [];
  const configuredAdminConsoleMethods = useMemo(() => {
    const methods = new Set<AdminConsoleMethod>();
    adminIdentities.forEach((identity) => {
      if (identity.provider === "email") {
        methods.add("email");
      }
      if (identity.provider === "google" || identity.provider === "github") {
        methods.add(identity.provider);
      }
    });
    return (["email", "google", "github"] as const).filter((method) => {
      if (method === "email") {
        return Boolean(
          visitorAuthConfig?.admin_email_enabled &&
            visitorAuthConfig?.admin_email_password_set &&
            methods.has("email"),
        );
      }
      return methods.has(method);
    });
  }, [adminIdentities, visitorAuthConfig?.admin_email_enabled, visitorAuthConfig?.admin_email_password_set]);
  const consoleButtonProviders: AdminConsoleMethod[] = ["email", "google", "github"];
  const hasUnconfiguredAdminConsoleMethod = consoleButtonProviders.some(
    (provider) => !configuredAdminConsoleMethods.includes(provider),
  );

  useEffect(() => {
    const nextUsername = user?.username || "";
    setUsername(nextUsername);
    setSavedUsername(nextUsername);
  }, [user?.username]);

  useEffect(() => {
    setAdminConsoleAuthMethods(
      toAdminConsoleMethods(visitorAuthConfig?.admin_console_auth_methods),
    );
  }, [visitorAuthConfig]);

  const items = data ? [
    { label: t("systemInfo.version"), value: data.version, icon: Code },
    { label: t("systemInfo.python"), value: data.python_version, icon: Server },
    { label: t("systemInfo.dbSize"), value: formatBytes(data.db_size_bytes), icon: Database },
    { label: t("systemInfo.mediaSize"), value: formatBytes(data.media_dir_size_bytes), icon: HardDrive },
    { label: t("systemInfo.uptime"), value: formatUptime(data.uptime_seconds), icon: Clock },
    { label: t("systemInfo.environment"), value: data.environment, icon: Server },
  ] : [];
  const hasProfileChanges = username.trim() !== savedUsername.trim();

  const handleProfileSave = async () => {
    const nextUsername = username.trim();
    if (!nextUsername) {
      toast.error(t("common.operationFailed"));
      return;
    }
    setProfileSaving(true);
    try {
      await updateProfileEndpointApiV1AdminAuthProfilePut({ username: nextUsername });
      setUsername(nextUsername);
      setSavedUsername(nextUsername);
      toast.success(t("common.operationSuccess"));
    } catch {
      toast.error(t("common.operationFailed"));
    } finally {
      setProfileSaving(false);
    }
  };

  const handlePasswordChange = async () => {
    if (newPassword !== confirmPassword) {
      toast.error(t("settings.passwordMismatch"));
      return;
    }
    if (newPassword.length < 6) {
      toast.error(t("settings.passwordTooShort"));
      return;
    }
    setPasswordSaving(true);
    try {
      await changePasswordApiV1AdminAuthPasswordPut({
        current_password: currentPassword,
        new_password: newPassword,
      });
      toast.success(t("common.operationSuccess"));
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch {
      toast.error(t("settings.passwordChangeFailed"));
    } finally {
      setPasswordSaving(false);
    }
  };

  const handleAdminConsoleMethodToggle = async (provider: AdminConsoleMethod) => {
    const nextMethods = adminConsoleAuthMethods.includes(provider)
      ? adminConsoleAuthMethods.filter((method) => method !== provider)
      : [...adminConsoleAuthMethods, provider];

    setAdminConsoleAuthMethods(nextMethods);
    setSavingAdminConsoleMethod(provider);
    try {
      const response = await saveAdminConfig.mutateAsync({
        data: { admin_console_auth_methods: nextMethods },
      });
      const persisted = toAdminConsoleMethods(
        response.data?.admin_console_auth_methods,
      );
      setAdminConsoleAuthMethods(persisted);
      void queryClient.invalidateQueries({
        queryKey: getGetVisitorAuthConfigApiV1AdminVisitorsConfigGetQueryKey(),
      });
      toast.success(t("common.operationSuccess"));
    } catch {
      setAdminConsoleAuthMethods(
        toAdminConsoleMethods(visitorAuthConfig?.admin_console_auth_methods),
      );
      toast.error(t("common.operationFailed"));
    } finally {
      setSavingAdminConsoleMethod(null);
    }
  };

  return (
    <div>
      <PageHeader title={t("systemInfo.title")} description={t("systemInfo.description")} />
      {isLoading ? (
        <p className="text-muted-foreground">{t("common.loading")}</p>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {items.map((item) => (
              <Card key={item.label}>
                <CardContent className="px-4 pb-4 pt-4">
                  <div className="flex items-center gap-3">
                    <item.icon className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="text-xs text-muted-foreground">{item.label}</p>
                      <p className="text-lg font-semibold">{item.value}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
            <ConfigSettingsCard
              title={t("settings.adminInfo")}
              description={t("settings.description")}
              dirty={hasProfileChanges}
              saving={profileSaving}
              saveDisabled={profileSaving || !hasProfileChanges || !username.trim()}
              onSave={() => void handleProfileSave()}
              className="max-w-none"
            >
              <div className="space-y-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                  <div className="w-full max-w-md space-y-2">
                    <label className="mb-1 block text-sm font-medium">{t("settings.username")}</label>
                    <Input value={username} onChange={(e) => setUsername(e.target.value)} />
                  </div>

                  <div className="space-y-2 lg:ml-auto">
                    {hasUnconfiguredAdminConsoleMethod ? (
                      <div className="flex justify-start lg:justify-end">
                        <LabelWithHelp
                          label={(
                            <span className="inline-flex items-center rounded-full border border-amber-500/30 bg-amber-500/12 px-2.5 py-1 text-xs font-semibold text-amber-700 dark:text-amber-300">
                              {t("settings.oauthLoginConfigLabel")}
                            </span>
                          )}
                          title={t("settings.oauthLoginConfigTitle")}
                          description={t("settings.oauthLoginConfigDesc")}
                          usageItems={[
                            t("settings.oauthLoginConfigStep1"),
                            t("settings.oauthLoginConfigStep2"),
                          ]}
                          className="justify-end"
                        />
                      </div>
                    ) : null}

                    <div className="flex items-center gap-2 lg:justify-end">
                      {consoleButtonProviders.map((provider) => {
                        const enabled = adminConsoleAuthMethods.includes(provider);
                        const configured =
                          configuredAdminConsoleMethods.includes(provider);
                        const saving = savingAdminConsoleMethod === provider;
                        return (
                          <Button
                            key={provider}
                            type="button"
                            size="sm"
                            variant={enabled ? "default" : "outline"}
                            className={cn(
                              "h-8 whitespace-nowrap px-2.5 text-xs",
                              configured
                                ? "border-[rgb(var(--admin-accent-rgb)/0.24)]"
                                : "border-dashed text-muted-foreground/80",
                              enabled && configured && "shadow-[var(--admin-shadow-sm)]",
                            )}
                            disabled={
                              !configured ||
                              savingAdminConsoleMethod !== null ||
                              saveAdminConfig.isPending
                            }
                            onClick={() => void handleAdminConsoleMethodToggle(provider)}
                          >
                            {saving
                              ? t("common.loading")
                              : provider === "email"
                                ? t("settings.allowEmailLogin")
                                : t(
                                    `settings.allow${provider === "google" ? "Google" : "Github"}Login`,
                                  )}
                          </Button>
                        );
                      })}
                    </div>
                  </div>
                </div>

                <CollapsibleSection title={t("settings.changePassword")}>
                  <form
                    className="space-y-4"
                    onSubmit={(event) => {
                      event.preventDefault();
                      if (
                        passwordSaving ||
                        !currentPassword.trim() ||
                        !newPassword.trim() ||
                        !confirmPassword.trim()
                      ) {
                        return;
                      }
                      void handlePasswordChange();
                    }}
                  >
                    <div className="flex items-center justify-end">
                      <Button
                        type="submit"
                        disabled={
                          passwordSaving ||
                          !currentPassword.trim() ||
                          !newPassword.trim() ||
                          !confirmPassword.trim()
                        }
                        size="sm"
                      >
                        {passwordSaving ? t("common.loading") : t("settings.changePassword")}
                      </Button>
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium">{t("settings.currentPassword")}</label>
                      <Input
                        type="password"
                        autoComplete="current-password"
                        value={currentPassword}
                        placeholder="••••••••"
                        onChange={(e) => setCurrentPassword(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium">{t("settings.newPassword")}</label>
                      <Input
                        type="password"
                        autoComplete="new-password"
                        value={newPassword}
                        placeholder="••••••••"
                        onChange={(e) => setNewPassword(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium">{t("settings.confirmPassword")}</label>
                      <Input
                        type="password"
                        autoComplete="new-password"
                        value={confirmPassword}
                        placeholder="••••••••"
                        onChange={(e) => setConfirmPassword(e.target.value)}
                      />
                    </div>
                  </form>
                </CollapsibleSection>
              </div>
            </ConfigSettingsCard>

            <Card>
              <CardHeader>
                <CardTitle>{t("settings.activeSessions")}</CardTitle>
              </CardHeader>
              <CardContent>
                {sessionsLoading ? (
                  <p className="text-muted-foreground">{t("common.loading")}</p>
                ) : sessions.length === 0 ? (
                  <p className="text-muted-foreground">{t("common.noData")}</p>
                ) : (
                  <div className="space-y-3">
                    {sessions.map((session: AdminSessionRead) => (
                      <div key={session.id} className="admin-glass flex items-center justify-between rounded-lg p-3">
                        <div className="flex items-center gap-3">
                          <Monitor className="h-5 w-5 text-muted-foreground" />
                          <div>
                            <p className="text-sm font-medium">
                              {session.is_current && (
                                <span className="mr-2 text-green-600">({t("settings.currentSession")})</span>
                              )}
                              {t("settings.sessionCreated")}: {formatDateTime(session.created_at)}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {t("settings.sessionExpires")}: {formatDateTime(session.expires_at)}
                            </p>
                          </div>
                        </div>

                        {!session.is_current && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setRevokeTarget(session.id)}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}

      <ConfirmDialog
        open={!!revokeTarget}
        onConfirm={() => revokeTarget && revokeMutation.mutate(revokeTarget)}
        onCancel={() => setRevokeTarget(null)}
        title={t("settings.revokeSession")}
        description={t("settings.revokeSessionDesc")}
        variant="destructive"
        isPending={revokeMutation.isPending}
      />
    </div>
  );
}
