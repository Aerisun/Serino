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

export function testBackupSyncConfig(payload: BackupSyncConfigUpdate): Promise<BackupSyncConfigTestRead> {
  return testBackupSyncConfigApiV1AdminSystemBackupSyncConfigTestPost(payload).then(({ data }) => data);
}
