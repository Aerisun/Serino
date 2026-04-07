type SnippetSource = string | null | undefined;

export function stripMarkdownToPlainText(value: SnippetSource): string {
  if (!value) {
    return "";
  }

  return value
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/<[^>]+>/g, " ")
    .replace(/^\s{0,3}(?:#{1,6}|\d+[.)]|[-+*>])\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function getBodySnippet(value: SnippetSource, fallback = ""): string {
  return stripMarkdownToPlainText(value) || fallback;
}
