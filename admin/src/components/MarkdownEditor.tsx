import { lazy, Suspense, useState, useCallback, useRef, useEffect, useMemo, useLayoutEffect } from "react";
import { createPortal } from "react-dom";
import {
  Bold,
  Italic,
  Underline,
  Heading1,
  Heading2,
  Link,
  Image,
  Images,
  Code,
  ChevronDown,
  List,
  Eye,
  EyeOff,
  Maximize2,
  PenLine,
  Upload,
  X,
  Expand,
  Minimize2,
} from "lucide-react";
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
import { NativeSelect } from "@/components/ui/NativeSelect";
import { Textarea } from "@/components/ui/Textarea";
import { cn } from "@/lib/utils";
import { canCompressImage, prepareImageUploadFile } from "@serino/utils/image-upload";
import { uploadManagedAsset } from "@/lib/managedAssetUpload";
import { extractApiErrorMessage } from "@/lib/api-error";
import { toast } from "sonner";

const MarkdownPreview = lazy(() => import("@/components/MarkdownPreview"));

interface MarkdownEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  minHeight?: string;
  mobileFullscreen?: boolean;
  imageLayout?: "inline" | "attachments";
  assetCategory: "post" | "diary" | "thought" | "excerpt" | "resume" | "friends";
}

type InsertAction = { prefix: string; suffix: string; placeholder: string };
type ImageSelection = { start: number; end: number; altText: string };
type MarkdownImageAttachment = {
  id: string;
  src: string;
  alt: string;
  raw: string;
  start: number;
  end: number;
};

const MOBILE_EDITOR_QUERY = "(max-width: 767px)";

const ACTIONS: Record<string, InsertAction> = {
  bold: { prefix: "**", suffix: "**", placeholder: "bold text" },
  italic: { prefix: "*", suffix: "*", placeholder: "italic text" },
  underline: { prefix: ":underline[", suffix: "]", placeholder: "underline text" },
  thumbnail: { prefix: ":::thumb\n", suffix: "\n:::", placeholder: "![image](url)" },
  h1: { prefix: "# ", suffix: "", placeholder: "Heading 1" },
  h2: { prefix: "## ", suffix: "", placeholder: "Heading 2" },
  link: { prefix: "[", suffix: "](url)", placeholder: "link text" },
  image: { prefix: "![", suffix: "](url)", placeholder: "alt text" },
  code: { prefix: "```\n", suffix: "\n```", placeholder: "code" },
  list: { prefix: "- ", suffix: "", placeholder: "list item" },
};

function getIsMobileEditorViewport() {
  if (typeof window === "undefined") {
    return false;
  }
  return window.matchMedia(MOBILE_EDITOR_QUERY).matches;
}

function parsePixelHeight(value: string) {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function findUnescapedClosingBracket(value: string, start: number) {
  let depth = 0;

  for (let index = start; index < value.length; index += 1) {
    if (value[index] === "\\") {
      index += 1;
      continue;
    }
    if (value[index] === "[") {
      depth += 1;
    } else if (value[index] === "]") {
      if (depth === 0) return index;
      depth -= 1;
    }
  }

  return -1;
}

function findClosingImageParenthesis(value: string, start: number) {
  let depth = 1;

  for (let index = start; index < value.length; index += 1) {
    if (value[index] === "\\") {
      index += 1;
      continue;
    }
    if (value[index] === "(") {
      depth += 1;
    } else if (value[index] === ")") {
      depth -= 1;
      if (depth === 0) return index;
    }
  }

  return -1;
}

function getImageSource(imageBody: string) {
  const trimmed = imageBody.trim();
  if (!trimmed) return "";

  if (trimmed.startsWith("<")) {
    const closingIndex = trimmed.indexOf(">");
    return closingIndex > 0 ? trimmed.slice(1, closingIndex) : "";
  }

  let depth = 0;
  for (let index = 0; index < trimmed.length; index += 1) {
    const character = trimmed[index];
    if (character === "\\") {
      index += 1;
      continue;
    }
    if (character === "(") depth += 1;
    if (character === ")") depth -= 1;
    if (/\s/.test(character) && depth === 0) {
      return trimmed.slice(0, index);
    }
  }

  return trimmed;
}

function parseMarkdownImage(value: string, start: number) {
  if (!value.startsWith("![", start)) return null;

  const altEnd = findUnescapedClosingBracket(value, start + 2);
  if (altEnd < 0 || value[altEnd + 1] !== "(") return null;

  const imageEnd = findClosingImageParenthesis(value, altEnd + 2);
  if (imageEnd < 0) return null;

  const src = getImageSource(value.slice(altEnd + 2, imageEnd));
  if (!src) return null;

  return {
    alt: value.slice(start + 2, altEnd),
    end: imageEnd + 1,
    raw: value.slice(start, imageEnd + 1),
    src,
  };
}

function isClosingFenceLine(line: string, openingDelimiter: string) {
  const fenceMatch = line.match(/^ {0,3}(`{3,}|~{3,})/);
  if (
    !fenceMatch ||
    fenceMatch[1][0] !== openingDelimiter[0] ||
    fenceMatch[1].length < openingDelimiter.length
  ) {
    return false;
  }

  return /^[ \t]*(?:\r?\n)?$/.test(line.slice(fenceMatch[0].length));
}

function extractMarkdownImageAttachments(value: string) {
  const attachments: MarkdownImageAttachment[] = [];
  let text = "";
  let index = 0;
  let fencedCodeDelimiter: string | null = null;

  while (index < value.length) {
    const lineEnd = value.indexOf("\n", index);
    const nextLineIndex = lineEnd < 0 ? value.length : lineEnd + 1;
    const line = value.slice(index, nextLineIndex);
    const fenceMatch = line.match(/^ {0,3}(`{3,}|~{3,})/);

    if (fencedCodeDelimiter) {
      text += line;
      if (isClosingFenceLine(line, fencedCodeDelimiter)) {
        fencedCodeDelimiter = null;
      }
      index = nextLineIndex;
      continue;
    }

    if (fenceMatch) {
      fencedCodeDelimiter = fenceMatch[1];
      text += line;
      index = nextLineIndex;
      continue;
    }

    let lineIndex = 0;
    while (lineIndex < line.length) {
      if (line[lineIndex] === "\\") {
        text += line.slice(lineIndex, lineIndex + 2);
        lineIndex += 2;
        continue;
      }

      if (line[lineIndex] === "`") {
        const run = line.slice(lineIndex).match(/^`+/)?.[0] ?? "`";
        const closingIndex = line.indexOf(run, lineIndex + run.length);
        if (closingIndex >= 0) {
          text += line.slice(lineIndex, closingIndex + run.length);
          lineIndex = closingIndex + run.length;
          continue;
        }
      }

      const image = parseMarkdownImage(line, lineIndex);
      if (image) {
        attachments.push({
          id: `${index + lineIndex}-${attachments.length}`,
          src: image.src,
          alt: image.alt,
          raw: image.raw,
          start: index + lineIndex,
          end: index + lineIndex + image.raw.length,
        });
        lineIndex = image.end;
        continue;
      }

      text += line[lineIndex];
      lineIndex += 1;
    }
    index = nextLineIndex;
  }

  return { text, attachments };
}

function applyAttachmentModeTextEdit(
  source: string,
  previousText: string,
  nextText: string,
  attachments: MarkdownImageAttachment[],
) {
  let prefixLength = 0;
  while (
    prefixLength < previousText.length &&
    prefixLength < nextText.length &&
    previousText[prefixLength] === nextText[prefixLength]
  ) {
    prefixLength += 1;
  }

  let previousSuffixIndex = previousText.length;
  let nextSuffixIndex = nextText.length;
  while (
    previousSuffixIndex > prefixLength &&
    nextSuffixIndex > prefixLength &&
    previousText[previousSuffixIndex - 1] === nextText[nextSuffixIndex - 1]
  ) {
    previousSuffixIndex -= 1;
    nextSuffixIndex -= 1;
  }

  const insertedText = nextText.slice(prefixLength, nextSuffixIndex);
  const attachmentRanges = [...attachments].sort((left, right) => left.start - right.start);
  const parts: string[] = [];
  let sourceIndex = 0;
  let textIndex = 0;
  let inserted = false;

  const appendTextSegment = (segment: string) => {
    for (const character of segment) {
      if (!inserted && textIndex >= prefixLength) {
        parts.push(insertedText);
        inserted = true;
      }
      if (textIndex < prefixLength || textIndex >= previousSuffixIndex) {
        parts.push(character);
      }
      textIndex += character.length;
    }
  };

  for (const attachment of attachmentRanges) {
    appendTextSegment(source.slice(sourceIndex, attachment.start));
    if (!inserted && textIndex >= prefixLength) {
      parts.push(insertedText);
      inserted = true;
    }
    parts.push(source.slice(attachment.start, attachment.end));
    sourceIndex = attachment.end;
  }

  appendTextSegment(source.slice(sourceIndex));
  if (!inserted) parts.push(insertedText);
  return parts.join("");
}

function appendAttachmentMarkdown(source: string, markdown: string) {
  if (!source) return markdown;
  const separator = source.endsWith("\n\n") ? "" : source.endsWith("\n") ? "\n" : "\n\n";
  return `${source}${separator}${markdown}`;
}

export function MarkdownEditor({
  value,
  onChange,
  placeholder,
  minHeight = "300px",
  mobileFullscreen = false,
  imageLayout = "inline",
  assetCategory,
}: MarkdownEditorProps) {
  const { t } = useI18n();
  const [preview, setPreview] = useState(false);
  const [autoExpand, setAutoExpand] = useState(true);
  const [isMobileViewport, setIsMobileViewport] = useState(getIsMobileEditorViewport);
  const [mobileComposerOpen, setMobileComposerOpen] = useState(false);
  const [mobileToolbarOpen, setMobileToolbarOpen] = useState(false);
  const [imageUploadOpen, setImageUploadOpen] = useState(false);
  const [imageUploadMode, setImageUploadMode] = useState<"compress" | "original">("compress");
  const [imageUploading, setImageUploading] = useState(false);
  const [selectedImageFile, setSelectedImageFile] = useState<File | null>(null);
  const [imageNote, setImageNote] = useState("");
  const [editorHeight, setEditorHeight] = useState(minHeight);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const mobileComposerRootRef = useRef<HTMLDivElement | null>(null);
  const touchStartYRef = useRef(0);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const pendingImageSelectionRef = useRef<ImageSelection | null>(null);
  const pendingImageFileNameRef = useRef<string>("");
  const attachmentMode = imageLayout === "attachments";
  const { text: editorText, attachments } = useMemo(
    () =>
      attachmentMode
        ? extractMarkdownImageAttachments(value)
        : { text: value, attachments: [] as MarkdownImageAttachment[] },
    [attachmentMode, value],
  );
  const emitEditorValue = useCallback((nextText: string) => {
    onChange(
      attachmentMode
        ? applyAttachmentModeTextEdit(value, editorText, nextText, attachments)
        : nextText,
    );
  }, [attachmentMode, attachments, editorText, onChange, value]);
  const minHeightPx = useMemo(() => {
    const parsed = Number.parseFloat(minHeight);
    return Number.isFinite(parsed) ? parsed : 300;
  }, [minHeight]);
  const useMobileFullscreen = mobileFullscreen && isMobileViewport;
  const mobileCharacterCount = useMemo(
    () => Array.from(editorText.replace(/\s/g, "")).length,
    [editorText],
  );
  const mobileSnippet = useMemo(() => editorText.trim(), [editorText]);

  useEffect(() => {
    const mediaQuery = window.matchMedia(MOBILE_EDITOR_QUERY);
    const handleChange = () => {
      const matches = mediaQuery.matches;
      setIsMobileViewport(matches);
      if (!matches) {
        setMobileComposerOpen(false);
      }
    };

    handleChange();
    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  useEffect(() => {
    if (!useMobileFullscreen || !mobileComposerOpen) {
      return;
    }

    const scrollY = window.scrollY;
    const previousBodyOverflow = document.body.style.overflow;
    const previousBodyOverscrollBehavior = document.body.style.overscrollBehavior;
    const previousBodyPosition = document.body.style.position;
    const previousBodyTop = document.body.style.top;
    const previousBodyLeft = document.body.style.left;
    const previousBodyRight = document.body.style.right;
    const previousBodyWidth = document.body.style.width;
    const previousHtmlOverflow = document.documentElement.style.overflow;
    const previousHtmlOverscrollBehavior = document.documentElement.style.overscrollBehavior;

    document.body.style.overflow = "hidden";
    document.body.style.overscrollBehavior = "none";
    document.body.style.position = "fixed";
    document.body.style.top = `-${scrollY}px`;
    document.body.style.left = "0";
    document.body.style.right = "0";
    document.body.style.width = "100%";
    document.documentElement.style.overflow = "hidden";
    document.documentElement.style.overscrollBehavior = "none";

    const handleTouchStart = (event: TouchEvent) => {
      touchStartYRef.current = event.touches[0]?.clientY ?? 0;
    };

    const handleTouchMove = (event: TouchEvent) => {
      const root = mobileComposerRootRef.current;
      const target = event.target instanceof Element ? event.target : null;
      const isFloatingEditorDialog = Boolean(target.closest("[data-mobile-editor-floating]"));
      if (!root || !target || (!root.contains(target) && !isFloatingEditorDialog)) {
        event.preventDefault();
        return;
      }

      const scroller = target.closest("[data-mobile-editor-scroll]") as HTMLElement | null;
      if (!scroller) {
        event.preventDefault();
        return;
      }

      const currentY = event.touches[0]?.clientY ?? touchStartYRef.current;
      const deltaY = currentY - touchStartYRef.current;
      const canScroll = scroller.scrollHeight > scroller.clientHeight + 1;
      const atTop = scroller.scrollTop <= 0;
      const atBottom = scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 1;

      if (!canScroll || (atTop && deltaY > 0) || (atBottom && deltaY < 0)) {
        event.preventDefault();
      }
    };

    document.addEventListener("touchstart", handleTouchStart, { capture: true, passive: true });
    document.addEventListener("touchmove", handleTouchMove, { capture: true, passive: false });

    return () => {
      document.removeEventListener("touchstart", handleTouchStart, { capture: true });
      document.removeEventListener("touchmove", handleTouchMove, { capture: true });
      document.body.style.overflow = previousBodyOverflow;
      document.body.style.overscrollBehavior = previousBodyOverscrollBehavior;
      document.body.style.position = previousBodyPosition;
      document.body.style.top = previousBodyTop;
      document.body.style.left = previousBodyLeft;
      document.body.style.right = previousBodyRight;
      document.body.style.width = previousBodyWidth;
      document.documentElement.style.overflow = previousHtmlOverflow;
      document.documentElement.style.overscrollBehavior = previousHtmlOverscrollBehavior;
      window.scrollTo(0, scrollY);
    };
  }, [mobileComposerOpen, useMobileFullscreen]);

  useEffect(() => {
    if (!useMobileFullscreen || !mobileComposerOpen || preview) {
      return;
    }

    const frame = requestAnimationFrame(() => textareaRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [mobileComposerOpen, preview, useMobileFullscreen]);

  useLayoutEffect(() => {
    if (useMobileFullscreen && mobileComposerOpen) {
      return;
    }
    if (!autoExpand) {
      setEditorHeight(minHeight);
      return;
    }
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }
    const measuredHeight = Math.max(textarea.scrollHeight, minHeightPx);
    setEditorHeight((currentHeight) => {
      const nextHeight = Math.max(measuredHeight, parsePixelHeight(currentHeight));
      return `${nextHeight}px`;
    });
  }, [autoExpand, minHeight, minHeightPx, mobileComposerOpen, useMobileFullscreen, value]);

  const insertMarkdown = useCallback((action: string) => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const { prefix, suffix, placeholder: ph } = ACTIONS[action];
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = editorText.slice(start, end) || ph;
    const newValue = editorText.slice(0, start) + prefix + selected + suffix + editorText.slice(end);
    emitEditorValue(newValue);
    requestAnimationFrame(() => {
      textarea.focus({ preventScroll: true });
      const newCursorPos = start + prefix.length + selected.length;
      textarea.setSelectionRange(newCursorPos, newCursorPos);
    });
  }, [editorText, emitEditorValue]);

  const insertImageMarkdown = useCallback((imageUrl: string) => {
    const textarea = textareaRef.current;
    const selection = pendingImageSelectionRef.current;
    const start = selection?.start ?? textarea?.selectionStart ?? editorText.length;
    const end = selection?.end ?? textarea?.selectionEnd ?? start;
    const altText =
      selection?.altText ||
      pendingImageFileNameRef.current.replace(/\.[^.]+$/, "").trim() ||
      "image";
    const nextText = editorText.slice(0, start) + editorText.slice(end);
    const markdown = `![${altText}](${imageUrl})`;
    const nextValue = attachmentMode
      ? appendAttachmentMarkdown(
          applyAttachmentModeTextEdit(value, editorText, nextText, attachments),
          markdown,
        )
      : editorText.slice(0, start) + markdown + editorText.slice(end);
    onChange(nextValue);

    requestAnimationFrame(() => {
      textarea?.focus({ preventScroll: true });
      const nextCursor = attachmentMode ? start : start + markdown.length;
      textarea?.setSelectionRange(nextCursor, nextCursor);
    });

    pendingImageSelectionRef.current = null;
    pendingImageFileNameRef.current = "";
  }, [attachmentMode, attachments, editorText, onChange, value]);

  const openImageUploadDialog = useCallback(() => {
    const textarea = textareaRef.current;
    const start = textarea?.selectionStart ?? editorText.length;
    const end = textarea?.selectionEnd ?? start;
    pendingImageSelectionRef.current = {
      start,
      end,
      altText: editorText.slice(start, end).trim(),
    };
    setImageUploadMode("compress");
    setImageNote("");
    setSelectedImageFile(null);
    setImageUploadOpen(true);
  }, [editorText]);

  const removeImageAttachment = useCallback((attachmentId: string) => {
    const attachment = attachments.find((item) => item.id === attachmentId);
    if (attachment) {
      onChange(value.slice(0, attachment.start) + value.slice(attachment.end));
    }
  }, [attachments, onChange, value]);

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
        fileToUpload = await prepareImageUploadFile(file, { mode: imageUploadMode });
      }

      pendingImageFileNameRef.current = file.name;
      const asset = await uploadManagedAsset({
        file: fileToUpload,
        visibility: "internal",
        scope: "article",
        category: assetCategory,
        note: imageNote.trim() || undefined,
      });
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
      toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
    } finally {
      setImageUploading(false);
    }
  }, [assetCategory, imageNote, imageUploadMode, insertImageMarkdown, selectedImageFile, t]);

  const toolbarButtons = [
    { action: "bold", icon: Bold },
    { action: "italic", icon: Italic },
    { action: "underline", icon: Underline },
    { action: "h1", icon: Heading1 },
    { action: "h2", icon: Heading2 },
    { action: "link", icon: Link },
    { action: "image", icon: Image },
    { action: "thumbnail", icon: Images, label: "缩略图" },
    { action: "code", icon: Code },
    { action: "list", icon: List },
  ];

  const openMobileComposer = useCallback(() => {
    setPreview(false);
    setMobileToolbarOpen(false);
    setMobileComposerOpen(true);
  }, []);

  const closeMobileComposer = useCallback(() => {
    textareaRef.current?.blur();
    setMobileToolbarOpen(false);
    setMobileComposerOpen(false);
  }, []);

  const toggleMobilePreview = useCallback(() => {
    setPreview((current) => {
      const nextPreview = !current;
      if (nextPreview) {
        setMobileToolbarOpen(false);
      }
      return nextPreview;
    });
  }, []);

  const attachmentGrid = attachmentMode && attachments.length > 0 ? (
    <div className="mx-auto grid w-full shrink-0 max-w-[22rem] grid-cols-3 gap-2 p-4 pb-0">
      {attachments.map((attachment) => (
        <div
          key={attachment.id}
          className="relative aspect-square overflow-hidden rounded-xl border border-border/70 bg-muted/40"
        >
          <img
            src={attachment.src}
            alt={attachment.alt}
            loading="lazy"
            className="h-full w-full object-cover"
          />
          <button
            type="button"
            onClick={() => removeImageAttachment(attachment.id)}
            aria-label={`删除图片：${attachment.alt}`}
            className="absolute right-1.5 top-1.5 inline-flex h-7 w-7 items-center justify-center rounded-full border border-white/25 bg-black/55 text-white transition hover:bg-black/75"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  ) : null;

  const renderToolbar = (fullScreen = false) => (
    <div
      className={cn(
        "flex items-center gap-1 border-b bg-muted/50",
        fullScreen
          ? "shrink-0 gap-0.5 overflow-x-auto px-3 py-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          : "px-2 py-1",
      )}
    >
      {toolbarButtons.map(({ action, icon: Icon, label }) => (
        <button
          key={action}
          type="button"
          className={cn(
            "shrink-0 rounded transition-colors hover:bg-accent",
            fullScreen
              ? "flex h-11 w-10 items-center justify-center rounded-full bg-background/65 text-foreground shadow-sm"
              : "p-1.5",
          )}
          onClick={() => {
            if (action === "image") {
              openImageUploadDialog();
              return;
            }
            insertMarkdown(action);
          }}
          title={action === "image" ? "上传图片" : label ?? action}
          aria-label={action === "image" ? "上传图片" : label ?? action}
        >
          <Icon className="h-4 w-4" />
        </button>
      ))}
      {!fullScreen && (
        <div className="ml-auto">
          <button
            type="button"
            className="p-1.5 rounded hover:bg-accent transition-colors flex items-center gap-1 text-xs"
            onClick={() => setAutoExpand((current) => !current)}
            title={autoExpand ? t("common.collapse") : t("common.expand")}
          >
            {autoExpand ? <Minimize2 className="h-4 w-4" /> : <Expand className="h-4 w-4" />}
          </button>
        </div>
      )}
      {!fullScreen && (
        <div>
          <button
            type="button"
            className="p-1.5 rounded hover:bg-accent transition-colors flex items-center gap-1 text-xs"
            onClick={() => setPreview(!preview)}
          >
            {preview ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            {preview ? t("editor.edit") : t("editor.preview")}
          </button>
        </div>
      )}
    </div>
  );

  const renderEditorBody = (fullScreen = false) => (
    preview ? (
      <div
        data-mobile-editor-scroll={fullScreen ? "true" : undefined}
        className={cn(
          fullScreen
            ? "h-full overflow-y-auto overscroll-none px-5 py-5"
            : `p-4 ${autoExpand ? "overflow-visible" : "overflow-auto"}`,
        )}
        style={
          fullScreen
            ? undefined
            : autoExpand
              ? { minHeight }
              : { minHeight, maxHeight: minHeight }
        }
      >
        {attachmentGrid}
        <Suspense fallback={<div className="text-sm text-muted-foreground">{t("common.loading")}</div>}>
          <MarkdownPreview content={attachmentMode ? editorText : value} />
        </Suspense>
      </div>
    ) : fullScreen ? (
      <div className="flex h-full min-h-0 flex-col">
        {attachmentGrid}
        <textarea
          ref={textareaRef}
          data-mobile-editor-scroll="true"
          className="min-h-0 flex-1 resize-none overflow-y-auto overscroll-none bg-transparent px-5 py-5 font-serif text-[17px] leading-8 caret-primary outline-none selection:bg-primary/10 placeholder:text-muted-foreground/60"
          style={{ minHeight: 0 }}
          value={editorText}
          onChange={(event) => emitEditorValue(event.target.value)}
          placeholder={placeholder ?? t("editor.mobilePlaceholder")}
        />
      </div>
    ) : (
      <>
        {attachmentGrid}
        <textarea
          ref={textareaRef}
          data-mobile-editor-scroll={undefined}
          className={cn(
            "w-full bg-transparent outline-none",
            `p-4 font-mono text-sm ${autoExpand ? "resize-none overflow-hidden" : "resize-y overflow-auto"}`,
          )}
          style={
            autoExpand
              ? { minHeight, height: editorHeight }
              : { minHeight }
          }
          value={editorText}
          onChange={(event) => emitEditorValue(event.target.value)}
          placeholder={placeholder}
        />
      </>
    )
  );

  const imageUploadDialog = (
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
      <DialogContent
        data-mobile-editor-floating="true"
        onOpenAutoFocus={(event) => event.preventDefault()}
        className="flex max-h-[82dvh] w-[calc(100vw-2rem)] max-w-[22rem] flex-col gap-3 overflow-hidden rounded-2xl p-4 sm:max-h-[min(calc(100dvh-3rem),44rem)] sm:w-full sm:max-w-xl sm:gap-4 sm:p-6"
        hideCloseButton={false}
      >
        <DialogHeader className="pr-8 text-left">
          <DialogTitle className="text-base sm:text-lg">上传图片</DialogTitle>
          <DialogDescription className="text-xs sm:text-sm">上传后会自动写入用户资源。</DialogDescription>
        </DialogHeader>

        <div
          data-mobile-editor-scroll="true"
          className="min-h-0 flex-1 touch-pan-y overflow-y-auto overscroll-contain pr-1 [-webkit-overflow-scrolling:touch]"
        >
          <div className="grid gap-3 sm:gap-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>上传模式</Label>
                <NativeSelect
                  value={imageUploadMode}
                  className="markdown-image-upload-field min-h-10 sm:min-h-[2.75rem]"
                  onChange={(event) =>
                    setImageUploadMode(event.target.value as "compress" | "original")
                  }
                >
                  <option value="compress">{t("assets.uploadModeCompress")}</option>
                  <option value="original">{t("assets.uploadModeOriginal")}</option>
                </NativeSelect>
              </div>

              <div className="grid min-w-0 gap-2">
                <Label>选择文件</Label>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleImageFileChange}
                />
                <Button
                  type="button"
                  variant="outline"
                  className="h-10 min-h-10 w-full min-w-0 max-w-full justify-start overflow-hidden sm:h-10 sm:min-h-[2.75rem]"
                  onClick={() => fileRef.current?.click()}
                >
                  <Upload className="mr-2 h-4 w-4 shrink-0" />
                  <span className="min-w-0 flex-1 truncate" title={selectedImageFile?.name}>
                    {selectedImageFile ? selectedImageFile.name : "选择文件"}
                  </span>
                </Button>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t("assets.visibility")}</Label>
                <Input
                  value={t("assets.visibilityInternal")}
                  disabled
                  className="min-h-10 bg-muted text-muted-foreground sm:min-h-[2.75rem]"
                />
              </div>
              <div className="grid gap-2">
                <Label>{t("assets.scope")}</Label>
                <Input
                  value={t("assets.scopeUser")}
                  disabled
                  className="min-h-10 bg-muted text-muted-foreground sm:min-h-[2.75rem]"
                />
              </div>
            </div>

            <div className="grid gap-2">
              <Label>{t("assets.category")}</Label>
              <Input
                value={assetCategory}
                disabled
                className="min-h-10 bg-muted text-muted-foreground sm:min-h-[2.75rem]"
              />
            </div>

            <div className="grid gap-2">
              <Label>{t("assets.note")}</Label>
              <Textarea
                value={imageNote}
                onChange={(e) => setImageNote(e.target.value)}
                rows={2}
                className="markdown-image-upload-field min-h-20"
                placeholder={t("assets.note")}
              />
              <p className="text-xs text-muted-foreground">{t("assets.noteHint")}</p>
            </div>
          </div>
        </div>

        <div className="flex shrink-0 justify-end gap-2 border-t border-border/60 pt-3 sm:border-t-0 sm:pt-0">
          <Button
            type="button"
            variant="ghost"
            className="h-10 min-h-10 px-3 sm:min-h-[2.75rem] sm:px-4"
            onClick={() => setImageUploadOpen(false)}
          >
            {t("common.cancel")}
          </Button>
          <Button
            type="button"
            className="h-10 min-h-10 px-3 sm:min-h-[2.75rem] sm:px-4"
            onClick={() => void handleImageUpload()}
            disabled={imageUploading || !selectedImageFile}
          >
            {imageUploading ? t("assets.compressing") : t("common.confirm")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );

  const mobileComposer = mobileComposerOpen && useMobileFullscreen && typeof document !== "undefined"
    ? createPortal(
        <div
          ref={mobileComposerRootRef}
          className="fixed inset-x-0 z-40 overflow-hidden overscroll-none bg-background md:hidden"
          style={{ top: "-72px", bottom: "-72px" }}
        >
          <div
            className="absolute inset-x-0 flex flex-col overflow-hidden overscroll-none bg-background text-foreground"
            style={{ top: "72px", bottom: "72px" }}
          >
            <div className="shrink-0 border-b border-border/70 bg-background px-4 pb-2 pt-[calc(env(safe-area-inset-top)+0.5rem)]">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-xs text-muted-foreground">
                    {t("editor.mobileCharacterCount", { count: mobileCharacterCount })}
                  </div>
                </div>
	                <div className="flex shrink-0 items-center gap-1.5">
	                  <Button
	                    type="button"
	                    variant="ghost"
	                    size="icon"
	                    className="h-9 min-h-9 w-9 rounded-full"
                    onClick={() => setMobileToolbarOpen((current) => !current)}
                    title={
                      mobileToolbarOpen
                        ? t("editor.mobileToolbarClose")
                        : t("editor.mobileToolbarOpen")
                    }
                    aria-label={
                      mobileToolbarOpen
                        ? t("editor.mobileToolbarClose")
                        : t("editor.mobileToolbarOpen")
                    }
                    aria-expanded={mobileToolbarOpen}
                  >
                    <ChevronDown
                      className={cn(
                        "h-4 w-4 transition-transform duration-200",
                        mobileToolbarOpen && "rotate-180",
                      )}
                    />
	                  </Button>
	                  <Button
	                    type="button"
	                    variant="ghost"
	                    size="sm"
	                    className="h-9 min-h-9 rounded-full px-3"
                    onClick={toggleMobilePreview}
                  >
                    {preview ? <EyeOff className="mr-1.5 h-4 w-4" /> : <Eye className="mr-1.5 h-4 w-4" />}
                    {preview ? t("editor.mobileEdit") : t("editor.mobilePreview")}
	                  </Button>
	                  <Button
	                    type="button"
	                    size="sm"
	                    className="h-9 min-h-9 rounded-full px-4"
                    onClick={closeMobileComposer}
                  >
                    {t("common.done")}
                  </Button>
                </div>
              </div>
            </div>
            {!preview && mobileToolbarOpen && renderToolbar(true)}
            <div className="min-h-0 flex-1 overflow-hidden pb-[env(safe-area-inset-bottom)]">
              {renderEditorBody(true)}
            </div>
          </div>
        </div>,
        document.body,
      )
    : null;

  if (useMobileFullscreen) {
    return (
      <>
        <button
          type="button"
          className="admin-glass w-full rounded-[var(--admin-radius-lg)] px-4 py-5 text-left shadow-[var(--admin-shadow-sm)] transition-colors hover:bg-[rgb(var(--admin-surface-1)/0.78)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          onClick={openMobileComposer}
          aria-expanded={mobileComposerOpen}
          aria-label={t("editor.mobileOpen")}
        >
          <span className="flex items-center justify-between gap-3">
            <span className="inline-flex min-w-0 items-center gap-2 text-sm font-semibold">
              <PenLine className="h-4 w-4 shrink-0" />
              <span className="truncate">{t("editor.mobileTitle")}</span>
            </span>
            <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground">
              <Maximize2 className="h-3.5 w-3.5" />
              {t("editor.mobileOpen")}
            </span>
          </span>
          <span
            className="mt-4 block max-h-32 touch-pan-y overflow-y-auto overscroll-y-auto whitespace-pre-wrap pr-1 text-sm leading-6 text-foreground/80 [-webkit-overflow-scrolling:touch] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            onClick={(event) => {
              if (mobileSnippet) {
                event.stopPropagation();
              }
            }}
          >
            {mobileSnippet || t("editor.mobileEmpty")}
          </span>
          <span className="mt-4 block text-xs text-muted-foreground">
            {t("editor.mobileCharacterCount", { count: mobileCharacterCount })}
          </span>
        </button>
        {mobileComposer}
        {imageUploadDialog}
      </>
    );
  }

  return (
    <>
      <div className="overflow-hidden rounded-lg border">
        {renderToolbar(false)}
        {renderEditorBody(false)}
      </div>
      {imageUploadDialog}
    </>
  );
}
