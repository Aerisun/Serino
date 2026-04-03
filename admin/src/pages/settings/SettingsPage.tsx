import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuth } from "@/auth/useAuth";
import {
  changePasswordApiV1AdminAuthPasswordPut,
  updateProfileEndpointApiV1AdminAuthProfilePut,
  listSessionsEndpointApiV1AdminAuthSessionsGet,
  revokeSessionApiV1AdminAuthSessionsSessionIdDelete,
} from "@serino/api-client/admin";
import type { AdminSessionRead } from "@serino/api-client/models";
import { PageHeader } from "@/components/PageHeader";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/Tabs";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Monitor, Trash2 } from "lucide-react";
import { useI18n } from "@/i18n";

export default function SettingsPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const queryClient = useQueryClient();

  // Profile state
  const [username, setUsername] = useState(user?.username || "");
  const [profileSaving, setProfileSaving] = useState(false);

  // Password state
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);

  // Sessions
  const { data: sessions = [], isLoading: sessionsLoading } = useQuery({
    queryKey: ["admin-sessions"],
    queryFn: () => listSessionsEndpointApiV1AdminAuthSessionsGet().then((r) => r.data),
  });

  const [revokeTarget, setRevokeTarget] = useState<string | null>(null);

  const revokeMutation = useMutation({
    mutationFn: (id: string) => revokeSessionApiV1AdminAuthSessionsSessionIdDelete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-sessions"] });
      toast.success(t("common.operationSuccess"));
      setRevokeTarget(null);
    },
    onError: () => toast.error(t("common.operationFailed")),
  });

  const handleProfileSave = async () => {
    setProfileSaving(true);
    try {
      await updateProfileEndpointApiV1AdminAuthProfilePut({ username });
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
      await changePasswordApiV1AdminAuthPasswordPut({ current_password: currentPassword, new_password: newPassword });
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

  const formatDateTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  return (
    <div>
      <PageHeader title={t("settings.title")} description={t("settings.description")} />

      <Tabs defaultValue="profile">
        <TabsList className="mb-6">
          <TabsTrigger value="profile">{t("settings.profile")}</TabsTrigger>
          <TabsTrigger value="password">{t("settings.password")}</TabsTrigger>
          <TabsTrigger value="sessions">{t("settings.sessions")}</TabsTrigger>
        </TabsList>

        <TabsContent value="profile">
          <Card>
            <CardHeader>
              <CardTitle>{t("settings.profileInfo")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 max-w-md">
              <div>
                <label className="text-sm font-medium mb-1 block">{t("settings.username")}</label>
                <Input value={username} onChange={(e) => setUsername(e.target.value)} />
              </div>
              <Button onClick={handleProfileSave} disabled={profileSaving}>
                {profileSaving ? t("common.loading") : t("common.save")}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="password">
          <Card>
            <CardHeader>
              <CardTitle>{t("settings.changePassword")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 max-w-md">
              <div>
                <label className="text-sm font-medium mb-1 block">{t("settings.currentPassword")}</label>
                <Input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
              </div>
              <div>
                <label className="text-sm font-medium mb-1 block">{t("settings.newPassword")}</label>
                <Input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
              </div>
              <div>
                <label className="text-sm font-medium mb-1 block">{t("settings.confirmPassword")}</label>
                <Input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
              </div>
              <Button onClick={handlePasswordChange} disabled={passwordSaving}>
                {passwordSaving ? t("common.loading") : t("settings.changePassword")}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="sessions">
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
                  {sessions.map((s: AdminSessionRead) => (
                    <div key={s.id} className="flex items-center justify-between rounded-lg admin-glass p-3">
                      <div className="flex items-center gap-3">
                        <Monitor className="h-5 w-5 text-muted-foreground" />
                        <div>
                          <p className="text-sm font-medium">
                            {s.is_current && <span className="text-green-600 mr-2">({t("settings.currentSession")})</span>}
                            {t("settings.sessionCreated")}: {formatDateTime(s.created_at)}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {t("settings.sessionExpires")}: {formatDateTime(s.expires_at)}
                          </p>
                        </div>
                      </div>
                      {!s.is_current && (
                        <Button variant="ghost" size="sm" onClick={() => setRevokeTarget(s.id)}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

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
