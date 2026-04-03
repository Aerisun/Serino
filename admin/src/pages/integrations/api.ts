import {
  getMcpConfigApiV1AdminIntegrationsMcpConfigGet,
  updateMcpConfigApiV1AdminIntegrationsMcpConfigPut,
} from "@serino/api-client/admin";
import type {
  GetMcpConfigApiV1AdminIntegrationsMcpConfigGetParams,
  McpAdminConfigRead,
  McpAdminConfigUpdate,
  McpCapabilityConfigRead,
  McpPresetRead,
  UpdateMcpConfigApiV1AdminIntegrationsMcpConfigPutParams,
} from "@serino/api-client/models";

export type { McpAdminConfigRead, McpAdminConfigUpdate, McpCapabilityConfigRead, McpPresetRead };

function buildGetMcpConfigParams(apiKeyId?: string): GetMcpConfigApiV1AdminIntegrationsMcpConfigGetParams | undefined {
  return apiKeyId ? { api_key_id: apiKeyId } : undefined;
}

function buildUpdateMcpConfigParams(
  apiKeyId?: string,
): UpdateMcpConfigApiV1AdminIntegrationsMcpConfigPutParams | undefined {
  return apiKeyId ? { api_key_id: apiKeyId } : undefined;
}

export function getMcpConfig(apiKeyId?: string): Promise<McpAdminConfigRead> {
  return getMcpConfigApiV1AdminIntegrationsMcpConfigGet(buildGetMcpConfigParams(apiKeyId)).then(
    ({ data }) => data,
  );
}

export function updateMcpConfig(data: McpAdminConfigUpdate, apiKeyId?: string): Promise<McpAdminConfigRead> {
  return updateMcpConfigApiV1AdminIntegrationsMcpConfigPut(
    data,
    buildUpdateMcpConfigParams(apiKeyId),
  ).then(({ data: next }) => next);
}
