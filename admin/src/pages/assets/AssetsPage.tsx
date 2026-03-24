import { useState, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useListAssetsApiV1AdminAssetsGet,
  useUploadAssetApiV1AdminAssetsPost,
  useDeleteAssetApiV1AdminAssetsAssetIdDelete,
  getListAssetsApiV1AdminAssetsGetQueryKey,
} from "@/api/generated/admin/admin";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/Button";
import { Upload, Trash2 } from "lucide-react";
import { formatDate, formatBytes } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import type { AssetAdminRead } from "@/api/generated/model";

export default function AssetsPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const fileRef = useRef<HTMLInputElement>(null);

  const { data: raw, isLoading } = useListAssetsApiV1AdminAssetsGet({ page });
  const data = raw?.data;

  const upload = useUploadAssetApiV1AdminAssetsPost({
    mutation: {
      onSuccess: () => { queryClient.invalidateQueries({ queryKey: getListAssetsApiV1AdminAssetsGetQueryKey() }); toast.success(t("common.operationSuccess")); },
      onError: (error: any) => { const msg = error?.response?.data?.detail || t("common.operationFailed"); toast.error(msg); },
    },
  });

  const del = useDeleteAssetApiV1AdminAssetsAssetIdDelete({
    mutation: {
      onSuccess: () => { queryClient.invalidateQueries({ queryKey: getListAssetsApiV1AdminAssetsGetQueryKey() }); toast.success(t("common.operationSuccess")); },
      onError: (error: any) => { const msg = error?.response?.data?.detail || t("common.operationFailed"); toast.error(msg); },
    },
  });

  const handleUpload = () => {
    const file = fileRef.current?.files?.[0];
    if (file) upload.mutate({ data: { file } });
  };

  return (
    <div>
      <PageHeader
        title={t("assets.title")}
        description={t("assets.description")}
        actions={
          <div className="flex gap-2 items-center">
            <input type="file" ref={fileRef} className="hidden" onChange={handleUpload} />
            <Button onClick={() => fileRef.current?.click()} disabled={upload.isPending}>
              <Upload className="h-4 w-4 mr-2" /> {upload.isPending ? t("common.uploading") : t("assets.upload")}
            </Button>
          </div>
        }
      />
      <div className="border rounded-lg">
        <DataTable<AssetAdminRead>
          columns={[
            { header: t("assets.fileName"), accessor: "file_name" },
            { header: t("assets.mimeType"), accessor: (row) => row.mime_type || "-" },
            { header: t("assets.fileSize"), accessor: (row) => formatBytes(row.byte_size ?? 0) },
            { header: t("assets.uploadedAt"), accessor: (row) => formatDate(row.created_at) },
            { header: "", accessor: (row) => (
              <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); if (confirm(t("assets.deleteConfirm"))) del.mutate({ assetId: row.id }); }}>
                <Trash2 className="h-4 w-4" />
              </Button>
            )},
          ]}
          data={data?.items ?? []}
          total={data?.total ?? 0}
          page={page}
          pageSize={data?.page_size ?? 20}
          onPageChange={setPage}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}
