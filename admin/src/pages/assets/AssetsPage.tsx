import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listAssets, uploadAsset, deleteAsset } from "@/api/endpoints/assets";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/Button";
import { Upload, Trash2 } from "lucide-react";
import { formatDate, formatBytes } from "@/lib/utils";
import { useI18n } from "@/i18n";
import type { Asset } from "@/types/models";

export default function AssetsPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const fileRef = useRef<HTMLInputElement>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["assets", page],
    queryFn: () => listAssets({ page }),
  });

  const upload = useMutation({
    mutationFn: (file: File) => uploadAsset(file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets"] }),
  });

  const del = useMutation({
    mutationFn: (id: string) => deleteAsset(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets"] }),
  });

  const handleUpload = () => {
    const file = fileRef.current?.files?.[0];
    if (file) upload.mutate(file);
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
        <DataTable<Asset>
          columns={[
            { header: t("assets.fileName"), accessor: "file_name" },
            { header: t("assets.mimeType"), accessor: (row) => row.mime_type || "-" },
            { header: t("assets.fileSize"), accessor: (row) => formatBytes(row.byte_size) },
            { header: t("assets.uploadedAt"), accessor: (row) => formatDate(row.created_at) },
            { header: "", accessor: (row) => (
              <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); if (confirm(t("assets.deleteConfirm"))) del.mutate(row.id); }}>
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
