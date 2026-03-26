import type { ReactNode } from "react";
import type { ContentAdminRead } from "@serino/api-client/models";

interface SortOption {
  value: string;
  labelKey: string;
}

interface ColumnDef {
  header: string;
  accessor: keyof ContentAdminRead | ((row: ContentAdminRead) => ReactNode);
  className?: string;
}

type UseListHook = (params: Record<string, unknown>) => {
  data?: { data?: { items?: unknown[]; total?: number; page_size?: number } };
  isLoading: boolean;
};

type UseBulkMutationHook = (options?: {
  mutation?: { onSuccess?: () => void };
}) => {
  mutateAsync: (args: {
    data: { ids: string[]; status?: string };
  }) => Promise<{ data: { affected: number } }>;
  isPending: boolean;
};

type GetQueryKeyFn = () => readonly unknown[];

export interface ContentListConfig {
  resourceKey: string;
  titleKey: string;
  descriptionKey: string;
  newButtonLabelKey: string;
  newPath: string;
  editPath: (id: string) => string;
  columns: ColumnDef[];
  useList: UseListHook;
  useBulkDelete: UseBulkMutationHook;
  useBulkStatus: UseBulkMutationHook;
  getQueryKey: GetQueryKeyFn;
  sortOptions?: SortOption[];
  statusTabs?: string[];
}

export const DEFAULT_SORT_OPTIONS: SortOption[] = [
  { value: "updated_at:desc", labelKey: "common.sortLastUpdatedDesc" },
  { value: "updated_at:asc", labelKey: "common.sortLastUpdatedAsc" },
  { value: "published_at:desc", labelKey: "common.sortRecordedAtDesc" },
  { value: "published_at:asc", labelKey: "common.sortRecordedAtAsc" },
];

export const DEFAULT_STATUS_TABS = [
  "draft",
  "public_publish",
  "private_archive",
];
