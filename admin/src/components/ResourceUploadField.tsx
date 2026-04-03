import { useRef, useState, type ReactNode } from "react";
import {
  deleteAssetEndpointApiV1AdminAssetsAssetIdDelete,
  listAssetsEndpointApiV1AdminAssetsGet,
} from "@serino/api-client/admin";
import type { AssetAdminRead } from "@serino/api-client/models";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { canCompressImage, prepareImageUploadFile } from "@serino/utils";
import { uploadManagedAsset } from "@/lib/managedAssetUpload";
import { toast } from "sonner";
import { Upload } from "lucide-react";

interface ResourceUploadFieldProps {
  label: ReactNode;
  value: string;
  category: string;
  scope?: "system" | "user";
  accept?: string;
  placeholder?: string;
  note?: string;
  uniqueByCategory?: boolean;
  onChange: (value: string) => void;
  onUploadPersist?: (value: string) => Promise<void>;
}

export function ResourceUploadField({
  label,
  value,
  category,
  scope = "system",
  accept,
  placeholder,
  note,
  uniqueByCategory = false,
  onChange,
  onUploadPersist,
}: ResourceUploadFieldProps) {
  const [open, setOpen] = useState(false);
  const [uploadMode, setUploadMode] = useState<"compress" | "original">(
    "compress",
  );
  const [isCompressing, setIsCompressing] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isPersisting, setIsPersisting] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const visibility = "internal";
  const fixedNote = note || "系统资料类";
  const uploadLabel = accept?.includes("video") ? "上传资源" : "上传图片";

  const cleanupCategoryAssets = async (nextUrl: string) => {
    if (!uniqueByCategory) {
      return;
    }

    const response = await listAssetsEndpointApiV1AdminAssetsGet({
      page: 1,
      page_size: 100,
      q: category,
      scope,
    });
    const items = (response.data?.items ?? []) as AssetAdminRead[];
    const staleAssets = items.filter(
      (item) =>
        item.category === category &&
        item.scope === scope &&
        item.internal_url !== nextUrl &&
        item.public_url !== nextUrl,
    );

    if (!staleAssets.length) {
      return;
    }

    await Promise.all(
      staleAssets.map((item) =>
        deleteAssetEndpointApiV1AdminAssetsAssetIdDelete(item.id),
      ),
    );
  };

  const handleFileChange = () => {
    const file = fileRef.current?.files?.[0] ?? null;
    setSelectedFile(file);
  };

  const handleUpload = async () => {
    const file = selectedFile;
    if (!file) return;

    try {
      let fileToUpload = file;
      if (uploadMode === "compress") {
        if (!canCompressImage(file)) {
          toast.error("只有图片支持压缩上传");
          return;
        }
        setIsCompressing(true);
        fileToUpload = await prepareImageUploadFile(file, { mode: uploadMode });
      }
      setIsUploading(true);
      const asset = await uploadManagedAsset({
        file: fileToUpload,
        visibility,
        scope,
        category,
        note: fixedNote,
      });
      if (!asset.internal_url) {
        toast.error("资源上传失败");
        return;
      }
      try {
        await cleanupCategoryAssets(asset.internal_url);
      } catch {
        toast.error("新资源已上传，但旧资源清理失败");
      }
      onChange(asset.internal_url);
      let autoSaveFailed = false;
      if (onUploadPersist) {
        setIsPersisting(true);
        try {
          await onUploadPersist(asset.internal_url);
        } catch (error) {
          autoSaveFailed = true;
          const message = error instanceof Error ? error.message : "请稍后重试";
          toast.error(`资源已上传，但自动保存失败：${message}`);
        } finally {
          setIsPersisting(false);
        }
      }
      toast.success(
        autoSaveFailed
          ? "资源上传成功，请手动保存页面修改"
          : onUploadPersist
            ? "资源上传并自动保存成功"
            : "资源上传成功",
      );
      setOpen(false);
      setSelectedFile(null);
      if (fileRef.current) fileRef.current.value = "";
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "压缩失败，请改用原样上传或重试",
      );
    } finally {
      setIsCompressing(false);
      setIsUploading(false);
    }
  };

  return (
    <div className="space-y-2">
      {typeof label === "string" ? <Label>{label}</Label> : label}
      <div className="flex items-center gap-3">
        <Button
          type="button"
          variant="outline"
          className="shrink-0"
          onClick={() => setOpen(true)}
        >
          <Upload className="mr-2 h-4 w-4" />
          {uploadLabel}
        </Button>
        <Input
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      </div>

      <Dialog
        open={open}
        onOpenChange={(nextOpen) => {
          setOpen(nextOpen);
          if (!nextOpen) {
            setSelectedFile(null);
            if (fileRef.current) fileRef.current.value = "";
          }
        }}
      >
        <DialogContent className="max-w-xl rounded-2xl" hideCloseButton={false}>
          <DialogHeader className="text-left">
            <DialogTitle>{uploadLabel}</DialogTitle>
            <DialogDescription>
              {onUploadPersist
                ? "上传后会自动写入系统资料资源，并立即保存当前地址。"
                : "上传后会自动写入系统资料资源。"}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>上传模式</Label>
                <Select
                  value={uploadMode}
                  onValueChange={(nextValue) =>
                    setUploadMode(nextValue as "compress" | "original")
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="选择上传模式" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="compress">压缩后上传</SelectItem>
                    <SelectItem value="original">原样上传</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label>选择文件</Label>
                <input
                  ref={fileRef}
                  type="file"
                  accept={accept}
                  className="hidden"
                  onChange={handleFileChange}
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => fileRef.current?.click()}
                >
                  {selectedFile ? selectedFile.name : "选择文件"}
                </Button>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>可见性</Label>
                <Input
                  value="仅对内"
                  disabled
                  className="bg-muted text-muted-foreground"
                />
              </div>
              <div className="grid gap-2">
                <Label>分类</Label>
                <Input
                  value={category}
                  disabled
                  className="bg-muted text-muted-foreground"
                />
              </div>
            </div>

            <div className="grid gap-2">
              <Label>备注</Label>
              <Textarea
                value={fixedNote}
                disabled
                rows={3}
                className="bg-muted text-muted-foreground"
              />
            </div>

            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setOpen(false)}
              >
                取消
              </Button>
              <Button
                type="button"
                onClick={() => void handleUpload()}
                disabled={
                  isUploading || isCompressing || isPersisting || !selectedFile
                }
              >
                {isCompressing
                  ? "压缩中..."
                  : isUploading
                    ? "上传中..."
                    : isPersisting
                      ? "保存中..."
                      : "确认上传"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
