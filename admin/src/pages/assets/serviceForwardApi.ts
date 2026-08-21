import {
  createServiceForwardEndpointApiV1AdminServiceForwardsPost,
  deleteServiceForwardEndpointApiV1AdminServiceForwardsRouteIdDelete,
  listServiceForwardsEndpointApiV1AdminServiceForwardsGet,
  testServiceForwardEndpointApiV1AdminServiceForwardsRouteIdTestPost,
  updateServiceForwardEndpointApiV1AdminServiceForwardsRouteIdPut,
} from "@serino/api-client/admin";
import type {
  ServiceForwardRead,
  ServiceForwardWrite,
  ServiceForwardWriteSource,
} from "@serino/api-client/models";

export type {
  ServiceForwardRead,
  ServiceForwardWrite,
  ServiceForwardWriteSource as ServiceForwardSource,
};

export async function listServiceForwards() {
  const response = await listServiceForwardsEndpointApiV1AdminServiceForwardsGet();
  return response.data as ServiceForwardRead[];
}

export async function createServiceForward(payload: ServiceForwardWrite) {
  const response = await createServiceForwardEndpointApiV1AdminServiceForwardsPost(payload);
  return response.data as ServiceForwardRead;
}

export async function updateServiceForward(routeId: string, payload: ServiceForwardWrite) {
  const response = await updateServiceForwardEndpointApiV1AdminServiceForwardsRouteIdPut(
    routeId,
    payload,
  );
  return response.data as ServiceForwardRead;
}

export async function testServiceForward(routeId: string) {
  const response = await testServiceForwardEndpointApiV1AdminServiceForwardsRouteIdTestPost(routeId);
  return response.data as ServiceForwardRead;
}

export async function deleteServiceForward(routeId: string) {
  await deleteServiceForwardEndpointApiV1AdminServiceForwardsRouteIdDelete(routeId);
}
