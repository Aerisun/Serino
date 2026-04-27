import { useEffect, useState, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  useListAssetsEndpointApiV1AdminAssetsGet as useListAssetsApiV1AdminAssetsGet,
  useDeleteAssetEndpointApiV1AdminAssetsAssetIdDelete as useDeleteAssetApiV1AdminAssetsAssetIdDelete,
  useUpdateAssetEndpointApiV1AdminAssetsAssetIdPatch as useUpdateAssetApiV1AdminAssetsAssetIdPatch,
  getListAssetsEndpointApiV1AdminAssetsGetQueryKey as getListAssetsApiV1AdminAssetsGetQueryKey,
} from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Textarea } from "@/components/ui/Textarea";
import { NativeSelect } from "@/components/ui/NativeSelect";
import { Upload, Trash2, Copy, ExternalLink, Link as LinkIcon, Pencil, Zap } from "lucide-react";
import { canCompressImage, prepareImageUploadFile } from "@serino/utils/image-upload";
import { formatDate, formatBytes } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { uploadManagedAsset } from "@/lib/managedAssetUpload";
import {
  getObjectStorageConfig,
  listObjectStorageSyncRecords,
  type ObjectStorageSyncRecordRead,
} from "@/pages/more/objectStorageApi";
import { toast } from "sonner";
import type { AssetAdminRead } from "@serino/api-client/models";

export default function AssetsPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState<"user" | "system" | "oss_sync">("user");
  const [scope, setScope] = useState<"user" | "system">("user");
  const [search, setSearch] = useState("");
  const [searchDebounced, setSearchDebounced] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editingAsset, setEditingAsset] = useState<AssetAdminRead | null>(null);
  const [visibility, setVisibility] = useState<"internal" | "public">("internal");
  const [uploadMode, setUploadMode] = useState<"compress" | "original">("compress");
  const [category, setCategory] = useState("general");
  const [note, setNote] = useState("");
  const [editVisibility, setEditVisibility] = useState<"internal" | "public">("internal");
  const [editScope, setEditScope] = useState<"user" | "system">("user");
  const [editCategory, setEditCategory] = useState("general");
  const [editNote, setEditNote] = useState("");
  const [isCompressing, setIsCompressing] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isSyncView = viewMode === "oss_sync";

  useEffect(() => {
    return () => {
      if (searchTimer.current) clearTimeout(searchTimer.current);
    };
  }, []);

  const { data: raw, isLoading } = useListAssetsApiV1AdminAssetsGet({
    page,
    q: searchDebounced || undefined,
    scope: isSyncView ? undefined : viewMode,
  });
  const data = raw?.data && "items" in raw.data ? raw.data : undefined;
  const { data: objectStorageConfig } = useQuery({
    queryKey: ["admin", "object-storage-config"],
    queryFn: getObjectStorageConfig,
    refetchOnWindowFocus: false,
  });
  const { data: syncRecords, isLoading: isSyncRecordsLoading } = useQuery({
    queryKey: ["admin", "object-storage-sync-records", page, searchDebounced],
    queryFn: () => listObjectStorageSyncRecords({ page, q: searchDebounced }),
    enabled: isSyncView,
    refetchOnWindowFocus: false,
  });

  const del = useDeleteAssetApiV1AdminAssetsAssetIdDelete({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListAssetsApiV1AdminAssetsGetQueryKey() });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const update = useUpdateAssetApiV1AdminAssetsAssetIdPatch({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListAssetsApiV1AdminAssetsGetQueryKey() });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const copyText = async (value: string, successKey: string) => {
    await navigator.clipboard.writeText(value);
    toast.success(t(successKey));
  };

  const openPreview = (asset: AssetAdminRead) => {
    window.open(asset.public_url ?? asset.internal_url, "_blank", "noopener,noreferrer");
  };

  const handleFileChange = () => {
    const file = fileRef.current?.files?.[0] ?? null;
    setSelectedFile(file);
  };

  const handleSearch = (value: string) => {
    setSearch(value);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setSearchDebounced(value.trim());
      setPage(1);
    }, 300);
  };

  const handleViewModeChange = (value: "user" | "system" | "oss_sync") => {
    setViewMode(value);
    if (value !== "oss_sync") {
      setScope(value);
    }
    setPage(1);
  };

  const formatSyncStatus = (status: string) => {
    switch (status) {
      case "queued":
        return t("assets.syncStatusQueued");
      case "running":
        return t("assets.syncStatusRunning");
      case "retrying":
        return t("assets.syncStatusRetrying");
      case "completed":
        return t("assets.syncStatusCompleted");
      case "failed":
        return t("assets.syncStatusFailed");
      default:
        return status;
    }
  };

  const openEditDialog = (asset: AssetAdminRead) => {
    setEditingAsset(asset);
    setEditVisibility(asset.visibility);
    setEditScope(asset.scope);
    setEditCategory(asset.category);
    setEditNote(asset.note ?? "");
    setEditOpen(true);
  };

  const handleUpdate = async () => {
    if (!editingAsset) return;

    try {
      await update.mutateAsync({
        assetId: editingAsset.id,
        data: {
          visibility: editVisibility,
          scope: editScope,
          category: editCategory,
          note: editNote.trim() || null,
        },
      });
      setEditOpen(false);
      setEditingAsset(null);
    } catch {
      // ignore
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      toast.error(t("common.uploadFile"));
      return;
    }

    try {
      let fileToUpload = selectedFile;
      if (uploadMode === "compress") {
        if (!canCompressImage(selectedFile)) {
          toast.error(t("assets.compressOnlyImages"));
          return;
        }
        setIsCompressing(true);
        fileToUpload = await prepareImageUploadFile(selectedFile, { mode: uploadMode });
      }
      setIsUploading(true);
      await uploadManagedAsset({
        file: fileToUpload,
        visibility,
        scope,
        category,
        note: note.trim() || undefined,
      });
      await queryClient.invalidateQueries({ queryKey: getListAssetsApiV1AdminAssetsGetQueryKey() });
      toast.success(t("common.operationSuccess"));
      setUploadOpen(false);
      if (fileRef.current) fileRef.current.value = "";
      setSelectedFile(null);
      setNote("");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : extractApiErrorMessage(error, t("common.operationFailed")),
      );
    } finally {
      setIsCompressing(false);
      setIsUploading(false);
    }
  };

  return (
    <div>
      <PageHeader
        title={t("assets.title")}
        description={t("assets.description")}
        actions={
          <div className="flex items-center gap-2">
            {objectStorageConfig?.enabled && objectStorageConfig.last_health_ok ? (
              <div className="inline-flex h-10 items-center gap-2 rounded-full border border-amber-500/20 bg-amber-500/10 px-3 text-sm font-medium text-amber-700 dark:text-amber-300">
                <Zap className="h-4 w-4" />
                {t("assets.ossAccelerationEnabled")}
              </div>
            ) : null}
            <Button onClick={() => setUploadOpen(true)}>
              <Upload className="mr-2 h-4 w-4" /> {t("assets.upload")}
            </Button>
          </div>
        }
      />
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 w-full">
          <div className="w-[180px]">
            <NativeSelect
              value={viewMode}
              onChange={(event) =>
                handleViewModeChange(event.target.value as "user" | "system" | "oss_sync")
              }
            >
              <option value="user">{t("assets.scopeUser")}</option>
              <option value="system">{t("assets.scopeSystem")}</option>
              <option value="oss_sync">{t("assets.scopeOssSync")}</option>
            </NativeSelect>
          </div>
          <div className="w-full max-w-md">
            <Input
              value={search}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder={t("assets.searchPlaceholder")}
            />
          </div>
        </div>
      </div>
      <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
        <DialogContent className="max-w-xl rounded-2xl" hideCloseButton={false}>
          <DialogHeader className="text-left">
            <DialogTitle>{t("assets.upload")}</DialogTitle>
            <DialogDescription>{t("assets.description")}</DialogDescription>
          </DialogHeader>

          <div className="grid gap-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t("assets.visibility")}</Label>
                <NativeSelect
                  value={visibility}
                  onChange={(event) =>
                    setVisibility(event.target.value as "internal" | "public")
                  }
                >
                  <option value="internal">{t("assets.visibilityInternal")}</option>
                  <option value="public">{t("assets.visibilityPublic")}</option>
                </NativeSelect>
              </div>

              <div className="grid gap-2">
                <Label>{t("assets.scope")}</Label>
                <NativeSelect
                  value={scope}
                  onChange={(event) => setScope(event.target.value as "user" | "system")}
                >
                  <option value="user">{t("assets.scopeUser")}</option>
                  <option value="system">{t("assets.scopeSystem")}</option>
                </NativeSelect>
              </div>

              <div className="grid gap-2 sm:col-span-2">
                <Label>是否压缩</Label>
                <NativeSelect
                  value={uploadMode}
                  onChange={(event) =>
                    setUploadMode(event.target.value as "compress" | "original")
                  }
                >
                  <option value="compress">{t("assets.uploadModeCompress")}</option>
                  <option value="original">{t("assets.uploadModeOriginal")}</option>
                </NativeSelect>
              </div>
            </div>

            <div className="grid gap-2">
              <Label>{t("assets.category")}</Label>
              <Input
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder={t("assets.category")}
              />
            </div>

            <div className="grid gap-2">
              <Label>{t("assets.note")}</Label>
              <Textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder={t("assets.note")}
                rows={4}
                maxLength={500}
              />
              <p className="text-xs text-muted-foreground">{t("assets.noteHint")}</p>
            </div>

            <Card className="border-dashed border-border/70 bg-background/50">
              <div className="grid gap-4 p-5 sm:grid-cols-2 sm:items-center">
                <div className="space-y-1 sm:min-w-0">
                  <p className="text-sm font-medium text-foreground/80">
                    {selectedFile ? selectedFile.name : "点击选择文件"}
                  </p>
                  <p className="text-xs text-foreground/40">
                    {selectedFile
                      ? formatBytes(selectedFile.size)
                      : "选择文件后再点击上传"}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-2 sm:justify-self-end sm:w-full sm:max-w-[280px]">
                  <Button
                    variant="outline"
                    onClick={() => fileRef.current?.click()}
                    disabled={isUploading || isCompressing}
                    className="h-10 w-full"
                  >
                    {t("common.uploadFile")}
                  </Button>
                  <Button
                    onClick={() => void handleUpload()}
                    disabled={!selectedFile || isUploading || isCompressing}
                    className="h-10 w-full"
                  >
                    <Upload className="mr-2 h-4 w-4" />
                    {isCompressing
                      ? t("assets.compressing")
                      : isUploading
                        ? t("common.uploading")
                        : t("assets.upload")}
                  </Button>
                </div>
              </div>
              <input type="file" ref={fileRef} className="hidden" onChange={handleFileChange} />
            </Card>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={editOpen} onOpenChange={(open) => {
        setEditOpen(open);
        if (!open) {
          setEditingAsset(null);
        }
      }}>
        <DialogContent className="max-w-xl rounded-2xl" hideCloseButton={false}>
          <DialogHeader className="text-left">
            <DialogTitle>{t("assets.editTitle")}</DialogTitle>
            <DialogDescription>{editingAsset?.file_name}</DialogDescription>
          </DialogHeader>

          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label>{t("assets.visibility")}</Label>
              <NativeSelect
                value={editVisibility}
                onChange={(event) =>
                  setEditVisibility(event.target.value as "internal" | "public")
                }
              >
                <option value="internal">{t("assets.visibilityInternal")}</option>
                <option value="public">{t("assets.visibilityPublic")}</option>
              </NativeSelect>
            </div>

            <div className="grid gap-2">
              <Label>{t("assets.scope")}</Label>
              <NativeSelect
                value={editScope}
                onChange={(event) => setEditScope(event.target.value as "user" | "system")}
              >
                <option value="user">{t("assets.scopeUser")}</option>
                <option value="system">{t("assets.scopeSystem")}</option>
              </NativeSelect>
            </div>

            <div className="grid gap-2">
              <Label>{t("assets.category")}</Label>
              <Input
                value={editCategory}
                onChange={(e) => setEditCategory(e.target.value)}
                placeholder={t("assets.category")}
              />
            </div>

            <div className="grid gap-2">
              <Label>{t("assets.note")}</Label>
              <Textarea
                value={editNote}
                onChange={(e) => setEditNote(e.target.value)}
                placeholder={t("assets.note")}
                rows={4}
                maxLength={500}
              />
              <p className="text-xs text-muted-foreground">{t("assets.noteHint")}</p>
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setEditOpen(false)}>
                {t("common.cancel")}
              </Button>
              <Button onClick={() => void handleUpdate()} disabled={!editingAsset || update.isPending}>
                {update.isPending ? t("common.saving") : t("common.save")}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
      <div className="border rounded-lg">
        {isSyncView ? (
          <DataTable<ObjectStorageSyncRecordRead>
            columns={[
              {
                header: t("assets.syncType"),
                accessor: (row) =>
                  row.record_type === "mirror"
                    ? t("assets.syncTypeMirror")
                    : row.record_type === "remote_upload"
                      ? t("assets.syncTypeRemoteUpload")
                      : t("assets.syncTypeRemoteDelete"),
              },
              {
                header: t("assets.fileName"),
                accessor: (row) => row.asset_file_name || row.object_key,
              },
              {
                header: t("assets.resourceKey"),
                accessor: (row) => (
                  <div className="max-w-[320px] break-all text-xs text-foreground/80">
                    {row.asset_resource_key || row.object_key}
                  </div>
                ),
              },
              {
                header: t("assets.syncStatus"),
                accessor: (row) => formatSyncStatus(row.status),
              },
              {
                header: t("assets.syncRetries"),
                accessor: (row) => row.retry_count,
              },
            ]}
            data={syncRecords?.items ?? []}
            total={syncRecords?.total ?? 0}
            page={page}
            pageSize={syncRecords?.page_size ?? 20}
            onPageChange={setPage}
            isLoading={isSyncRecordsLoading}
            renderExpandedRow={(row) => (
              <div className="grid gap-3 px-4 py-3 text-sm sm:grid-cols-2">
                <div className="space-y-1">
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">
                    {t("assets.uploadedAt")}
                  </div>
                  <div className="rounded-md bg-background/60 px-3 py-2 text-foreground/80">
                    {formatDate(row.created_at)}
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">
                    {t("assets.updatedAt")}
                  </div>
                  <div className="rounded-md bg-background/60 px-3 py-2 text-foreground/80">
                    {formatDate(row.updated_at)}
                  </div>
                </div>
              </div>
            )}
          />
        ) : (
        <DataTable<AssetAdminRead>
          columns={[
            {
              header: t("assets.fileName"),
              accessor: (row) => (
                <div className="flex items-center gap-2">
                  <div className="font-medium text-foreground/92">{row.file_name}</div>
                  <Button
                    variant="ghost"
                    size="icon"
                    title={t("assets.open")}
                    onClick={(e) => {
                      e.stopPropagation();
                      openPreview(row);
                    }}
                  >
                    <ExternalLink className="h-4 w-4" />
                  </Button>
                </div>
              ),
            },
            {
              header: t("assets.note"),
              accessor: (row) => (
                <div className="max-w-[280px] whitespace-pre-wrap break-words text-sm text-muted-foreground">
                  {row.note || "-"}
                </div>
              ),
            },
            { header: t("assets.category"), accessor: (row) => row.category },
            { header: t("assets.scope"), accessor: (row) => row.scope === "system" ? t("assets.scopeSystem") : t("assets.scopeUser") },
            { header: t("assets.visibility"), accessor: (row) => row.visibility === "public" ? t("assets.visibilityPublic") : t("assets.visibilityInternal") },
            { header: t("assets.fileSize"), accessor: (row) => formatBytes(row.byte_size ?? 0) },
            {
              header: t("assets.links"),
              accessor: (row) => (
                <div className="flex w-full items-center gap-1 flex-wrap">
                  <Button
                    variant="ghost"
                    size="icon"
                    title={t("assets.copyInternal")}
                    onClick={(e) => { e.stopPropagation(); void copyText(row.internal_url, "assets.copyInternalSuccess"); }}
                  >
                    <LinkIcon className="h-4 w-4" />
                  </Button>
                  {row.visibility === "public" && row.public_url ? (
                    <>
                      <Button
                        variant="ghost"
                        size="icon"
                        title={t("assets.copyPublic")}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (row.public_url) {
                            void copyText(row.public_url, "assets.copyPublicSuccess");
                          }
                        }}
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    </>
                  ) : null}
                </div>
              )
            },
            {
              header: "",
              accessor: (row) => (
                <div className="flex w-full items-center justify-end gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    title={t("common.edit")}
                    onClick={(e) => {
                      e.stopPropagation();
                      openEditDialog(row);
                    }}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    title={t("assets.deleteConfirm")}
                    className="border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive"
                    onClick={(e) => { e.stopPropagation(); if (confirm(t("assets.deleteConfirm"))) del.mutate({ assetId: row.id }); }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              )
            },
          ]}
          data={data?.items ?? []}
          total={data?.total ?? 0}
          page={page}
          pageSize={data?.page_size ?? 20}
          onPageChange={setPage}
          isLoading={isLoading}
          renderExpandedRow={(row) => (
            <div className="grid gap-3 px-4 py-3 text-sm sm:grid-cols-2">
              <div className="space-y-1">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">
                  {t("assets.resourceKey")}
                </div>
                <div className="break-all rounded-md bg-background/60 px-3 py-2 font-mono text-xs text-foreground/80">
                  {row.resource_key}
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">
                  {t("assets.uploadedAt")}
                </div>
                <div className="rounded-md bg-background/60 px-3 py-2 text-foreground/80">
                  {formatDate(row.created_at)}
                </div>
              </div>
            </div>
          )}
        />
        )}
      </div>
    </div>
  );
}
