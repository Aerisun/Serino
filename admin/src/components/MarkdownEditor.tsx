import { useState, useCallback } from "react";
import { Bold, Italic, Heading1, Heading2, Link, Image, Code, List, Eye, EyeOff } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { useI18n } from "@/i18n";

interface MarkdownEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  minHeight?: string;
}

type InsertAction = { prefix: string; suffix: string; placeholder: string };

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
  const [textareaRef, setTextareaRef] = useState<HTMLTextAreaElement | null>(null);

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
            onClick={() => insertMarkdown(action)}
            title={action}
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
