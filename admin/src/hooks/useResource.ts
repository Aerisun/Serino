import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { PaginatedResponse } from "@/types/models";

interface ResourceConfig<T, C, U> {
  queryKey: string;
  listFn: (params?: any) => Promise<PaginatedResponse<T>>;
  getFn?: (id: string) => Promise<T>;
  createFn?: (data: C) => Promise<T>;
  updateFn?: (id: string, data: U) => Promise<T>;
  deleteFn?: (id: string) => Promise<void>;
}

export function useResourceList<T, C = any, U = any>(
  config: ResourceConfig<T, C, U>,
  params?: any
) {
  const queryClient = useQueryClient();

  const listQuery = useQuery({
    queryKey: [config.queryKey, params],
    queryFn: () => config.listFn(params),
  });

  const createMutation = useMutation({
    mutationFn: (data: C) => config.createFn!(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [config.queryKey] }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: U }) => config.updateFn!(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [config.queryKey] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => config.deleteFn!(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [config.queryKey] }),
  });

  return {
    items: listQuery.data?.items ?? [],
    total: listQuery.data?.total ?? 0,
    page: listQuery.data?.page ?? 1,
    pageSize: listQuery.data?.page_size ?? 20,
    isLoading: listQuery.isLoading,
    error: listQuery.error,
    refetch: listQuery.refetch,
    create: createMutation.mutateAsync,
    update: updateMutation.mutateAsync,
    remove: deleteMutation.mutateAsync,
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isDeleting: deleteMutation.isPending,
  };
}

export function useResourceDetail<T>(queryKey: string, id: string | undefined, getFn: (id: string) => Promise<T>) {
  return useQuery({
    queryKey: [queryKey, id],
    queryFn: () => getFn(id!),
    enabled: !!id,
  });
}
