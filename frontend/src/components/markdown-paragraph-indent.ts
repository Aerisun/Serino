import { Children, isValidElement, type ReactNode } from "react";

export type MarkdownIndentDirectiveKind = "indent" | "noindent";

type MarkdownIndentDirectiveProps = {
  children?: ReactNode;
  "data-md-kind"?: MarkdownIndentDirectiveKind;
};

export interface MarkdownParagraphIndentResolution {
  children: ReactNode;
  modifierClassName: string;
}

export function getMarkdownIndentDirectiveKind(
  value: unknown,
): MarkdownIndentDirectiveKind | undefined {
  return value === "indent" || value === "noindent" ? value : undefined;
}

export function resolveMarkdownParagraphIndent(
  children: ReactNode,
): MarkdownParagraphIndentResolution {
  const paragraphChildren = Children.toArray(children);
  const directive = paragraphChildren[0];
  if (!isValidElement<MarkdownIndentDirectiveProps>(directive)) {
    return { children, modifierClassName: "" };
  }

  const kind = getMarkdownIndentDirectiveKind(directive.props["data-md-kind"]);
  if (!kind || Children.count(directive.props.children) > 0) {
    return { children, modifierClassName: "" };
  }

  const content = paragraphChildren.slice(1);
  const separator = content[0];
  if (typeof separator !== "string" || !/^[\t ]+/.test(separator)) {
    return { children, modifierClassName: "" };
  }

  content[0] = separator.replace(/^[\t ]+/, "");
  if (content[0] === "") {
    content.shift();
  }

  const hasContent = content.some(
    (child) => typeof child !== "string" || child.trim() !== "",
  );
  if (!hasContent) {
    return { children, modifierClassName: "" };
  }

  return {
    children: content,
    modifierClassName:
      kind === "indent"
        ? "markdown-paragraph--force-indent"
        : "markdown-paragraph--force-no-indent",
  };
}

export function getMarkdownParagraphClassName(
  className: string | undefined,
  modifierClassName: string,
) {
  return ["markdown-paragraph", modifierClassName, className ?? ""]
    .filter(Boolean)
    .join(" ");
}
