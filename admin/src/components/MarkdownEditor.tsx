import { useState, useCallback, useRef } from "react";
import {
  Bold,
  Italic,
  Heading1,
  Heading2,
  Link,
  Image,
  Code,
  List,
  Eye,
  EyeOff,
  Upload,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { useUploadAssetEndpointApiV1AdminAssetsPost } from "@serino/api-client/admin";
import { useI18n } from "@/i18n";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { canCompressImage, compressImageFile } from "@/lib/image-upload";
import { toast } from "sonner";

interface MarkdownEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  minHeight?: string;
}

type InsertAction = { prefix: string; suffix: string; placeholder: string };
type ImageSelection = { start: number; end: number; altText: string };

const FIXED_IMAGE_CATEGORY = "markdown-image";

const ACTIONS: Record<string, InsertAction> = {
  bold: { prefix: "**", suffix: "**", placeholder: "bold text" },
  italic: { prefix: "*", suffix: "*", placeholder: "italic text" },
  h1: { prefix: "# ", suffix: "", placeholder: "Heading 1" },
  h2: { prefix: "## ", suffix: "", placeholder: "Heading 2" },
  link: { prefix: "[", suffix: "](url)", placeholder: "link text" },
  image: { prefix: "![", suffix: "](url)", placeholder: "alt text" },
  code: { prefix: "```\n", suffix: "\n```", placeholder: "code" },
  list: { prefix: "- ", suffix: "", placeholder: "list item" },
};

export function MarkdownEditor({ value, onChange, placeholder, minHeight = "300px" }: MarkdownEditorProps) {
  const { t } = useI18n();
  const [preview, setPreview] = useState(false);
  const [imageUploadOpen, setImageUploadOpen] = useState(false);
  const [imageUploadMode, setImageUploadMode] = useState<"compress" | "original">("compress");
  const [imageUploading, setImageUploading] = useState(false);
  const [selectedImageFile, setSelectedImageFile] = useState<File | null>(null);
  const [imageNote, setImageNote] = useState("");
  const [textareaRef, setTextareaRef] = useState<HTMLTextAreaElement | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const pendingImageSelectionRef = useRef<ImageSelection | null>(null);
  const pendingImageFileNameRef = useRef<string>("");

  const uploadAsset = useUploadAssetEndpointApiV1AdminAssetsPost();

  const insertMarkdown = useCallback((action: string) => {
    if (!textareaRef) return;
    const { prefix, suffix, placeholder: ph } = ACTIONS[action];
    const start = textareaRef.selectionStart;
    const end = textareaRef.selectionEnd;
    const selected = value.slice(start, end) || ph;
    const newValue = value.slice(0, start) + prefix + selected + suffix + value.slice(end);
    onChange(newValue);
    requestAnimationFrame(() => {
      textareaRef.focus();
      const newCursorPos = start + prefix.length + selected.length;
      textareaRef.setSelectionRange(newCursorPos, newCursorPos);
    });
  }, [textareaRef, value, onChange]);

  const insertImageMarkdown = useCallback((imageUrl: string) => {
    const selection = pendingImageSelectionRef.current;
    const start = selection?.start ?? textareaRef?.selectionStart ?? value.length;
    const end = selection?.end ?? textareaRef?.selectionEnd ?? start;
    const altText =
      selection?.altText ||
      pendingImageFileNameRef.current.replace(/\.[^.]+$/, "").trim() ||
      "image";
    const markdown = `![${altText}](${imageUrl})`;
    const nextValue = value.slice(0, start) + markdown + value.slice(end);
    onChange(nextValue);

    requestAnimationFrame(() => {
      textareaRef?.focus();
      const nextCursor = start + markdown.length;
      textareaRef?.setSelectionRange(nextCursor, nextCursor);
    });

    pendingImageSelectionRef.current = null;
    pendingImageFileNameRef.current = "";
  }, [textareaRef, value, onChange]);

  const openImageUploadDialog = useCallback(() => {
    const start = textareaRef?.selectionStart ?? value.length;
    const end = textareaRef?.selectionEnd ?? start;
    pendingImageSelectionRef.current = {
      start,
      end,
      altText: value.slice(start, end).trim(),
    };
    setImageUploadMode("compress");
    setImageNote("");
    setSelectedImageFile(null);
    setImageUploadOpen(true);
  }, [textareaRef, value]);

  const handleImageFileChange = useCallback(() => {
    const file = fileRef.current?.files?.[0] ?? null;
    setSelectedImageFile(file);
  }, []);

  const handleImageUpload = useCallback(async () => {
    const file = selectedImageFile;
    if (!file) {
      toast.error(t("common.uploadFile"));
      return;
    }

    try {
      let fileToUpload = file;
      if (imageUploadMode === "compress") {
        if (!canCompressImage(file)) {
          toast.error(t("assets.compressOnlyImages"));
          return;
        }
        setImageUploading(true);
        fileToUpload = await compressImageFile(file);
      }

      pendingImageFileNameRef.current = file.name;
      const response = await uploadAsset.mutateAsync({
        data: {
          file: fileToUpload,
          visibility: "internal",
          scope: "user",
          category: FIXED_IMAGE_CATEGORY,
          note: imageNote.trim() || undefined,
        } as any,
      });

      const asset = response.data as { internal_url?: string };
      if (!asset.internal_url) {
        toast.error("资源上传失败");
        return;
      }

      insertImageMarkdown(asset.internal_url);
      toast.success("图片上传成功");
      setImageUploadOpen(false);
      setSelectedImageFile(null);
      setImageNote("");
      if (fileRef.current) fileRef.current.value = "";
    } catch (error: any) {
      const message = error?.response?.data?.detail || t("common.operationFailed");
      toast.error(message);
    } finally {
      setImageUploading(false);
    }
  }, [imageNote, imageUploadMode, insertImageMarkdown, selectedImageFile, t, uploadAsset]);

  const toolbarButtons = [
    { action: "bold", icon: Bold },
    { action: "italic", icon: Italic },
    { action: "h1", icon: Heading1 },
    { action: "h2", icon: Heading2 },
    { action: "link", icon: Link },
    { action: "image", icon: Image },
    { action: "code", icon: Code },
    { action: "list", icon: List },
  ];

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="flex items-center gap-1 border-b px-2 py-1 bg-muted/50">
        {toolbarButtons.map(({ action, icon: Icon }) => (
          <button
            key={action}
            type="button"
            className="p-1.5 rounded hover:bg-accent transition-colors"
            onClick={() => {
              if (action === "image") {
                openImageUploadDialog();
                return;
              }
              insertMarkdown(action);
            }}
            title={action === "image" ? "上传图片" : action}
          >
            <Icon className="h-4 w-4" />
          </button>
        ))}
        <div className="ml-auto">
          <button
            type="button"
            className="p-1.5 rounded hover:bg-accent transition-colors flex items-center gap-1 text-xs"
            onClick={() => setPreview(!preview)}
          >
            {preview ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            {preview ? t("editor.edit") : t("editor.preview")}
          </button>
        </div>
      </div>
      <Dialog
        open={imageUploadOpen}
        onOpenChange={(nextOpen) => {
          setImageUploadOpen(nextOpen);
          if (!nextOpen) {
            setImageUploading(false);
            setSelectedImageFile(null);
            setImageNote("");
            pendingImageSelectionRef.current = null;
            pendingImageFileNameRef.current = "";
            if (fileRef.current) fileRef.current.value = "";
          }
        }}
      >
        <DialogContent className="max-w-xl rounded-2xl" hideCloseButton={false}>
          <DialogHeader className="text-left">
            <DialogTitle>上传图片</DialogTitle>
            <DialogDescription>上传后会自动写入用户资源。</DialogDescription>
          </DialogHeader>

          <div className="grid gap-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>上传模式</Label>
                <Select
                  value={imageUploadMode}
                  onValueChange={(nextValue) => setImageUploadMode(nextValue as "compress" | "original")}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="选择上传模式" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="compress">{t("assets.uploadModeCompress")}</SelectItem>
                    <SelectItem value="original">{t("assets.uploadModeOriginal")}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label>选择文件</Label>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleImageFileChange}
                />
                <Button type="button" variant="outline" onClick={() => fileRef.current?.click()}>
                  <Upload className="mr-2 h-4 w-4" />
                  {selectedImageFile ? selectedImageFile.name : "选择文件"}
                </Button>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t("assets.visibility")}</Label>
                <Input value={t("assets.visibilityInternal")} disabled className="bg-muted text-muted-foreground" />
              </div>
              <div className="grid gap-2">
                <Label>{t("assets.scope")}</Label>
                <Input value={t("assets.scopeUser")} disabled className="bg-muted text-muted-foreground" />
              </div>
            </div>

            <div className="grid gap-2">
              <Label>{t("assets.category")}</Label>
              <Input value={FIXED_IMAGE_CATEGORY} disabled className="bg-muted text-muted-foreground" />
            </div>

            <div className="grid gap-2">
              <Label>{t("assets.note")}</Label>
              <Textarea
                value={imageNote}
                onChange={(e) => setImageNote(e.target.value)}
                rows={3}
                placeholder={t("assets.note")}
              />
              <p className="text-xs text-muted-foreground">{t("assets.noteHint")}</p>
            </div>

            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setImageUploadOpen(false)}>
                {t("common.cancel")}
              </Button>
              <Button
                type="button"
                onClick={() => void handleImageUpload()}
                disabled={imageUploading || uploadAsset.isPending || !selectedImageFile}
              >
                {imageUploading ? t("assets.compressing") : uploadAsset.isPending ? t("common.uploading") : t("common.confirm")}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
      {preview ? (
        <div
          className="prose prose-sm dark:prose-invert max-w-none p-4 overflow-auto"
          style={{ minHeight }}
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
            {value}
          </ReactMarkdown>
        </div>
      ) : (
        <textarea
          ref={setTextareaRef}
          className="w-full p-4 font-mono text-sm bg-transparent resize-y outline-none"
          style={{ minHeight }}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
        />
      )}
    </div>
  );
}

