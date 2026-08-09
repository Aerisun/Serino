import { useEffect, useState, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useHref, useSearchParams } from "react-router-dom";
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
import {
  Cloud,
  Copy,
  ExternalLink,
  FileText,
  Link as LinkIcon,
  MessageCircle,
  Pencil,
  Settings,
  Trash2,
  Upload,
  UserRound,
  Zap,
} from "lucide-react";
import { canCompressImage, prepareImageUploadFile } from "@serino/utils/image-upload";
import { cn, formatDate, formatBytes } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { uploadManagedAsset, type AssetScope } from "@/lib/managedAssetUpload";
import {
  getObjectStorageConfig,
  listObjectStorageSyncRecords,
  retryObjectStorageSyncRecord,
  type ObjectStorageSyncRecordRead,
} from "@/pages/more/objectStorageApi";
import { toast } from "sonner";
import type { AssetAdminRead } from "@serino/api-client/models";

type AssetViewMode = AssetScope | "oss_sync";

function assetViewModeFromQuery(value: string | null): AssetViewMode {
  return value === "article" || value === "visitor" || value === "system" || value === "oss_sync"
    ? value
    : "user";
}

const CATEGORY_OPTIONS: Record<AssetScope, readonly string[]> = {
  user: ["general"],
  article: ["post", "diary", "thought", "excerpt", "resume", "friends"],
  visitor: ["comment", "guestbook"],
  system: ["general", "hero-image", "hero-poster", "hero-video", "site-og", "site-icon", "resume-avatar"],
};

export default function AssetsPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState<AssetViewMode>(() =>
    assetViewModeFromQuery(searchParams.get("view")),
  );
  const [scope, setScope] = useState<AssetScope>("user");
  const [search, setSearch] = useState("");
  const [searchDebounced, setSearchDebounced] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editingAsset, setEditingAsset] = useState<AssetAdminRead | null>(null);
  const [visibility, setVisibility] = useState<"internal" | "public">("internal");
  const [uploadMode, setUploadMode] = useState<"compress" | "original">("compress");
  const [category, setCategory] = useState("general");
  const [publicSlug, setPublicSlug] = useState("");
  const [note, setNote] = useState("");
  const [editVisibility, setEditVisibility] = useState<"internal" | "public">("internal");
  const [editScope, setEditScope] = useState<AssetScope>("user");
  const [editCategory, setEditCategory] = useState("general");
  const [editPublicSlug, setEditPublicSlug] = useState("");
  const [editNote, setEditNote] = useState("");
  const [isCompressing, setIsCompressing] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isSyncView = viewMode === "oss_sync";
  const previewBaseHref = useHref("/assets/preview");

  useEffect(() => {
    return () => {
      if (searchTimer.current) clearTimeout(searchTimer.current);
    };
  }, []);

  useEffect(() => {
    const nextViewMode = assetViewModeFromQuery(searchParams.get("view"));
    setViewMode((current) => (current === nextViewMode ? current : nextViewMode));
  }, [searchParams]);

  const { data: raw, isLoading } = useListAssetsApiV1AdminAssetsGet(
    {
      page,
      q: searchDebounced || undefined,
      scope: isSyncView ? undefined : viewMode,
    },
    {
      query: {
        enabled: !isSyncView,
      },
    },
  );
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
  const retrySyncRecord = useMutation({
    mutationFn: ({
      recordType,
      recordId,
    }: {
      recordType: ObjectStorageSyncRecordRead["record_type"];
      recordId: string;
    }) => retryObjectStorageSyncRecord(recordType, recordId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["admin", "object-storage-sync-records"],
      });
      toast.success(t("assets.syncRetryQueued"));
    },
    onError: (error) => {
      toast.error(extractApiErrorMessage(error, t("assets.syncRetryFailed")));
    },
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

  const handleViewModeChange = (value: AssetViewMode) => {
    setViewMode(value);
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (value === "user") {
        next.delete("view");
      } else {
        next.set("view", value);
      }
      return next;
    }, { replace: true });
    if (value !== "oss_sync") {
      setScope(value);
      setCategory(CATEGORY_OPTIONS[value][0]);
    }
    setPage(1);
  };

  const scopeLabel = (value: AssetScope) => {
    switch (value) {
      case "article":
        return t("assets.scopeArticle");
      case "visitor":
        return t("assets.scopeVisitor");
      case "system":
        return t("assets.scopeSystem");
      default:
        return t("assets.scopeUser");
    }
  };

  const scopeTabs = [
    { value: "user" as const, label: t("assets.scopeUser"), icon: UserRound },
    { value: "article" as const, label: t("assets.scopeArticle"), icon: FileText },
    { value: "visitor" as const, label: t("assets.scopeVisitor"), icon: MessageCircle },
    { value: "system" as const, label: t("assets.scopeSystem"), icon: Settings },
  ];

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
    setEditPublicSlug(String(asset.public_slug ?? ""));
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
          public_slug: editPublicSlug.trim() || null,
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
        publicSlug: publicSlug.trim() || undefined,
      });
      await queryClient.invalidateQueries({ queryKey: getListAssetsApiV1AdminAssetsGetQueryKey() });
      toast.success(t("common.operationSuccess"));
      setUploadOpen(false);
      if (fileRef.current) fileRef.current.value = "";
      setSelectedFile(null);
      setNote("");
      setPublicSlug("");
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
      <div className="mb-4 space-y-3">
        <div className="overflow-x-auto pb-1">
          <div className="flex min-w-max items-center gap-2" aria-label={t("assets.scope")}>
            {scopeTabs.map(({ value, label, icon: Icon }) => (
              <Button
                key={value}
                type="button"
                variant={viewMode === value ? "default" : "outline"}
                aria-pressed={viewMode === value}
                onClick={() => handleViewModeChange(value)}
                className="h-10 rounded-full px-4"
              >
                <Icon className="mr-2 h-4 w-4" />
                {label}
              </Button>
            ))}
            <span className="mx-1 h-6 w-px bg-border/70" aria-hidden="true" />
            <Button
              type="button"
              variant={isSyncView ? "default" : "ghost"}
              aria-pressed={isSyncView}
              onClick={() => handleViewModeChange("oss_sync")}
              className="h-10 rounded-full px-4"
            >
              <Cloud className="mr-2 h-4 w-4" />
              {t("assets.scopeOssSync")}
            </Button>
          </div>
        </div>
        <div className="w-full max-w-md">
            <Input
              value={search}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder={t("assets.searchPlaceholder")}
            />
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
                  onChange={(event) => {
                    const nextScope = event.target.value as AssetScope;
                    setScope(nextScope);
                    setCategory(CATEGORY_OPTIONS[nextScope][0]);
                  }}
                >
                  {scopeTabs.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
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

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t("assets.category")}</Label>
                <Input
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  placeholder={t("assets.category")}
                  list="asset-upload-category-options"
                />
                <datalist id="asset-upload-category-options">
                  {CATEGORY_OPTIONS[scope].map((item) => <option key={item} value={item} />)}
                </datalist>
              </div>

              <div className="grid gap-2">
                <Label>{t("assets.publicSlug")}</Label>
                <Input
                  value={publicSlug}
                  onChange={(e) => setPublicSlug(e.target.value)}
                  placeholder={t("assets.publicSlugPlaceholder")}
                />
              </div>
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
                <div className="min-w-0 space-y-1">
                  <p
                    className="truncate text-sm font-medium text-foreground/80"
                    title={selectedFile?.name}
                  >
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
                onChange={(event) => setEditScope(event.target.value as AssetScope)}
              >
                {scopeTabs.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </NativeSelect>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t("assets.category")}</Label>
                <Input
                  value={editCategory}
                  onChange={(e) => setEditCategory(e.target.value)}
                  placeholder={t("assets.category")}
                  list="asset-edit-category-options"
                />
                <datalist id="asset-edit-category-options">
                  {CATEGORY_OPTIONS[editScope].map((item) => <option key={item} value={item} />)}
                </datalist>
              </div>

              <div className="grid gap-2">
                <Label>{t("assets.publicSlug")}</Label>
                <Input
                  value={editPublicSlug}
                  onChange={(e) => setEditPublicSlug(e.target.value)}
                  placeholder={t("assets.publicSlugPlaceholder")}
                />
              </div>
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
                      : row.record_type === "local_delete"
                        ? t("assets.syncTypeLocalDelete")
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
              {
                header: t("common.actions"),
                accessor: (row) =>
                  row.status === "failed" ? (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={
                        retrySyncRecord.isPending &&
                        retrySyncRecord.variables?.recordId === row.id
                      }
                      onClick={() =>
                        retrySyncRecord.mutate({
                          recordType: row.record_type,
                          recordId: row.id,
                        })
                      }
                    >
                      {t("assets.syncRetry")}
                    </Button>
                  ) : (
                    <span className="text-muted-foreground">-</span>
                  ),
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
                {row.last_error ? (
                  <div className="space-y-1 sm:col-span-2">
                    <div className="text-xs uppercase tracking-wide text-muted-foreground">
                      {t("assets.syncLastError")}
                    </div>
                    <div className="break-words rounded-md border border-red-500/15 bg-red-500/[0.05] px-3 py-2 text-red-700 dark:text-red-300">
                      {row.last_error}
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          />
        ) : (
        <DataTable<AssetAdminRead>
          tableClassName="min-w-[59rem] table-fixed"
          columns={[
            {
              header: t("assets.fileName"),
              className: "w-[12rem] min-w-[12rem]",
              accessor: (row) => (
                <div className="flex w-full min-w-0 max-w-full items-center gap-1.5">
                  <div
                    className="min-w-0 truncate font-medium text-foreground/92"
                    title={row.file_name}
                  >
                    {row.file_name}
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 shrink-0"
                    title={t("assets.openPreview")}
                    onClick={(e) => {
                      e.stopPropagation();
                      const targetUrl = row.visibility === "public"
                        ? row.internal_url
                        : `${previewBaseHref}/${encodeURIComponent(row.id)}`;
                      window.open(
                        targetUrl,
                        "_blank",
                        "noopener,noreferrer",
                      );
                    }}
                  >
                    <ExternalLink className="h-4 w-4" />
                  </Button>
                </div>
              ),
            },
            {
              header: t("assets.note"),
              className: "w-[10rem] min-w-[10rem]",
              accessor: (row) => (
                <div
                  className={cn(
                    "max-w-full line-clamp-2 break-words text-[13px] leading-5 text-muted-foreground",
                    !row.note && "text-center",
                  )}
                  title={row.note || undefined}
                >
                  {row.note || "-"}
                </div>
              ),
            },
            {
              header: t("assets.category"),
              className: "w-[8rem] min-w-[8rem] whitespace-nowrap px-2 text-center",
              accessor: (row) => (
                <div className="max-w-full truncate" title={row.category}>
                  {row.category}
                </div>
              ),
            },
            {
              header: t("assets.scope"),
              className: "w-[5.25rem] min-w-[5.25rem] whitespace-nowrap px-2",
              accessor: (row) => scopeLabel(row.scope as AssetScope),
            },
            {
              header: t("assets.visibility"),
              className: "w-[4.75rem] min-w-[4.75rem] whitespace-nowrap px-2",
              accessor: (row) => row.visibility === "public" ? t("assets.visibilityPublic") : t("assets.visibilityInternal"),
            },
            {
              header: t("assets.fileSize"),
              className: "w-[5.5rem] min-w-[5.5rem] whitespace-nowrap px-2",
              accessor: (row) => formatBytes(row.byte_size ?? 0),
            },
            {
              header: t("assets.links"),
              className: "w-[4.75rem] min-w-[4.75rem] whitespace-nowrap px-1 text-center",
              accessor: (row) => (
                <div className="flex w-full flex-nowrap items-center justify-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
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
                        className="h-8 w-8"
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
              header: t("common.actions"),
              className: "w-[4.75rem] min-w-[4.75rem] whitespace-nowrap px-1 text-center",
              accessor: (row) => (
                <div className="flex w-full flex-nowrap items-center justify-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
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
                    className="h-8 w-8 border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive"
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
            <div className="grid gap-3 px-4 py-3 text-sm sm:grid-cols-3">
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
                  {t("assets.publicSlug")}
                </div>
                <div className="break-all rounded-md bg-background/60 px-3 py-2 font-mono text-xs text-foreground/80">
                  {row.public_slug || "-"}
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
