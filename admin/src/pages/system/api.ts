import {
  acknowledgeBackupRecoveryKeyApiV1AdminSystemBackupSyncRecoveryKeyAcknowledgePost,
  ensureBackupCredentialsApiV1AdminSystemBackupSyncCredentialsEnsurePost,
  exportBackupRecoveryKeyApiV1AdminSystemBackupSyncRecoveryKeyExportPost,
  getConfigRevisionDetailApiV1AdminSystemConfigRevisionsRevisionIdGet,
  listConfigRevisionsApiV1AdminSystemConfigRevisionsGet,
  restoreConfigRevisionApiV1AdminSystemConfigRevisionsRevisionIdRestorePost,
  testBackupSyncConfigApiV1AdminSystemBackupSyncConfigTestPost,
} from "@serino/api-client/admin";
import type {
  BackupCredentialAcknowledgeWrite,
  BackupCredentialEnsureRead,
  BackupCredentialEnsureWrite,
  BackupCredentialExportRead,
  BackupCredentialExportWrite,
  BackupSyncConfigTestRead,
  BackupSyncConfigUpdate,
  ConfigDiffLineRead,
  ConfigRevisionDetailRead,
  ConfigRevisionListItemRead,
  ConfigRevisionRestoreWrite,
  ListConfigRevisionsApiV1AdminSystemConfigRevisionsGetParams,
  PaginatedResponseConfigRevisionListItemRead,
} from "@serino/api-client/models";
import { adminApiRequest } from "@/lib/adminApi";

export type ConfigRevisionListItem = ConfigRevisionListItemRead;
export type ConfigDiffLine = ConfigDiffLineRead;
export type ConfigRevisionDetail = ConfigRevisionDetailRead;
export type PaginatedResponse<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};
export type ConfigRevisionListParams = ListConfigRevisionsApiV1AdminSystemConfigRevisionsGetParams;
export type RestoreRevisionPayload = ConfigRevisionRestoreWrite;

export type BackupBootstrapClaimStatus = "pending" | "succeeded" | "failed" | "expired" | "revoked";
export type BackupRemoteHistoryState = "unreachable" | "empty" | "current" | "foreign" | "unknown";

export type BackupSyncConfigTestResult = BackupSyncConfigTestRead & {
  remote_history_state?: BackupRemoteHistoryState;
  remote_history_summary?: string | null;
  remote_repo_id?: string | null;
  local_repo_id?: string | null;
};

export type BackupBootstrapClaimCreate = {
  remote_host: string;
  remote_port?: number;
  remote_path?: string;
  remote_username?: string;
  site_slug?: string;
  credential_ref?: string;
  ttl_minutes?: number;
};

export type BackupBootstrapClaimRead = {
  id: string;
  status: BackupBootstrapClaimStatus;
  remote_host: string;
  remote_port: number;
  remote_path: string;
  remote_username: string;
  site_slug: string;
  credential_ref: string;
  public_key_fingerprint: string;
  expires_at: string;
  used_at?: string | null;
  completed_at?: string | null;
  revoked_at?: string | null;
  last_error?: string | null;
  setup_url?: string | null;
  setup_command?: string | null;
  created_at: string;
  updated_at: string;
};

export type BackupSystemResetRead = {
  config: unknown;
  remote_cleanup_command: string;
};

export function listConfigRevisions(
  params: ConfigRevisionListParams,
): Promise<PaginatedResponseConfigRevisionListItemRead> {
  return listConfigRevisionsApiV1AdminSystemConfigRevisionsGet(params).then(({ data }) => data);
}

export function getConfigRevisionDetail(revisionId: string): Promise<ConfigRevisionDetail> {
  return getConfigRevisionDetailApiV1AdminSystemConfigRevisionsRevisionIdGet(revisionId).then(
    ({ data }) => data,
  );
}

export function restoreConfigRevision(
  revisionId: string,
  payload: RestoreRevisionPayload = {},
): Promise<ConfigRevisionDetail> {
  return restoreConfigRevisionApiV1AdminSystemConfigRevisionsRevisionIdRestorePost(revisionId, {
    target: payload.target ?? "before",
    reason: payload.reason ?? null,
  }).then(({ data }) => data);
}

export function ensureBackupCredentials(payload: BackupCredentialEnsureWrite): Promise<BackupCredentialEnsureRead> {
  return ensureBackupCredentialsApiV1AdminSystemBackupSyncCredentialsEnsurePost({
    ...payload,
    force: payload.force ?? false,
  }).then(({ data }) => data);
}

export function exportBackupRecoveryKey(payload: BackupCredentialExportWrite): Promise<BackupCredentialExportRead> {
  return exportBackupRecoveryKeyApiV1AdminSystemBackupSyncRecoveryKeyExportPost({
    ...payload,
    rotate: payload.rotate ?? false,
  }).then(({ data }) => data);
}

export function acknowledgeBackupRecoveryKey(
  payload: BackupCredentialAcknowledgeWrite,
): Promise<BackupCredentialEnsureRead> {
  return acknowledgeBackupRecoveryKeyApiV1AdminSystemBackupSyncRecoveryKeyAcknowledgePost(payload).then(
    ({ data }) => data,
  );
}

export function testBackupSyncConfig(payload: BackupSyncConfigUpdate): Promise<BackupSyncConfigTestResult> {
  return testBackupSyncConfigApiV1AdminSystemBackupSyncConfigTestPost(payload).then(({ data }) => data);
}

export function probeBackupMachineConnection(
  payload: BackupSyncConfigUpdate,
): Promise<BackupSyncConfigTestResult> {
  return adminApiRequest<BackupSyncConfigTestResult>("/api/v1/admin/system/backup-sync/connection/probe", {
    method: "POST",
    body: payload,
  });
}

export function createBackupBootstrapClaim(
  payload: BackupBootstrapClaimCreate,
): Promise<BackupBootstrapClaimRead> {
  return adminApiRequest<BackupBootstrapClaimRead>("/api/v1/admin/system/backup-sync/bootstrap-claims", {
    method: "POST",
    body: payload,
  });
}

export function getBackupBootstrapClaim(claimId: string): Promise<BackupBootstrapClaimRead> {
  return adminApiRequest<BackupBootstrapClaimRead>(`/api/v1/admin/system/backup-sync/bootstrap-claims/${claimId}`);
}

export function revokeBackupBootstrapClaim(claimId: string): Promise<BackupBootstrapClaimRead> {
  return adminApiRequest<BackupBootstrapClaimRead>(
    `/api/v1/admin/system/backup-sync/bootstrap-claims/${claimId}/revoke`,
    { method: "POST" },
  );
}

export function overwriteRemoteBackupHistory(payload: BackupSyncConfigUpdate): Promise<BackupSyncConfigTestResult> {
  return adminApiRequest<BackupSyncConfigTestResult>("/api/v1/admin/system/backup-sync/remote-history/overwrite", {
    method: "POST",
    body: payload,
  });
}

export function resetBackupSyncSystem(): Promise<BackupSystemResetRead> {
  return adminApiRequest<BackupSystemResetRead>("/api/v1/admin/system/backup-sync/reset", {
    method: "POST",
  });
}
