import { useState, useCallback } from "react";
import { Bold, Italic, Heading1, Heading2, Link, Image, Code, List, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/Button";
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
          dangerouslySetInnerHTML={{ __html: simpleMarkdownToHtml(value) }}
        />
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

/** Minimal markdown-to-HTML for preview (no external dependency). */
function simpleMarkdownToHtml(md: string): string {
  let html = md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Code blocks
  html = html.replace(/```([\s\S]*?)```/g, "<pre><code>$1</code></pre>");
  // Inline code
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  // Headers
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");
  // Bold and italic
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  // Images (before links so ![alt](url) isn't matched as a link)
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img alt="$1" src="$2" />');
  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
  // List items
  html = html.replace(/^- (.+)$/gm, "<li>$1</li>");
  // Blockquotes
  html = html.replace(/^&gt; (.+)$/gm, "<blockquote>$1</blockquote>");
  // Line breaks
  html = html.replace(/\n\n/g, "<br/><br/>");

  return html;
}
