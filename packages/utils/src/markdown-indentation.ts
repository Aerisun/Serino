export interface MarkdownDocumentIndentResolution {
  content: string;
  indentParagraphs?: boolean;
}

export function resolveMarkdownDocumentIndent(
  content: string,
): MarkdownDocumentIndentResolution {
  let lineStart = 0;

  while (lineStart <= content.length) {
    const newlineIndex = content.indexOf("\n", lineStart);
    const lineEnd = newlineIndex === -1 ? content.length : newlineIndex;
    const line = content.slice(lineStart, lineEnd).trim();

    if (line === "@indent" || line === "@noindent") {
      const contentStart = newlineIndex === -1 ? lineEnd : newlineIndex + 1;
      return {
        content: content.slice(0, lineStart) + content.slice(contentStart),
        indentParagraphs: line === "@indent",
      };
    }

    if (line !== "" || newlineIndex === -1) {
      break;
    }

    lineStart = newlineIndex + 1;
  }

  return { content };
}
