import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

/**
 * Returns mutation options that invalidate the given query key on success.
 * Usage with Orval-generated hooks:
 *
 * ```ts
 * const invalidate = useInvalidateOnMutate(["/api/v1/admin/posts/"]);
 * const { mutateAsync } = useCreatePosts({ mutation: invalidate });
 * ```
 */
export function useInvalidateOnMutate(queryKey: readonly unknown[]) {
  const queryClient = useQueryClient();

  const onSuccess = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: [...queryKey] });
  }, [queryClient, queryKey]);

  return { onSuccess };
}
