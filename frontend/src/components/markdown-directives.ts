import type { Plugin } from "unified";
import { visit } from "unist-util-visit";

type DirectiveNode = {
  type: "containerDirective" | "leafDirective" | "textDirective";
  name?: string;
  attributes?: Record<string, string | null | undefined>;
  data?: {
    hName?: string;
    hProperties?: Record<string, string | number>;
  };
  position?: {
    start?: { offset?: number };
    end?: { offset?: number };
  };
};

type DirectiveParent = {
  children?: unknown[];
};

const ADMONITION_NAMES = new Set(["tip", "warning", "note", "info", "danger", "success"]);
const INDENT_DIRECTIVE_NAMES = new Set(["indent", "noindent"]);

const getStringAttribute = (value?: string | null) => (value ?? "").trim();

const getTagName = (node: DirectiveNode) => (node.type === "textDirective" ? "span" : "div");

const applyIndentDirective = (directiveNode: DirectiveNode, name: string) => {
  if (directiveNode.type !== "textDirective" || !INDENT_DIRECTIVE_NAMES.has(name)) {
    return false;
  }

  const data = directiveNode.data || (directiveNode.data = {});
  data.hName = "span";
  data.hProperties = {
    "data-md-kind": name,
  };
  return true;
};

const restoreDirectiveSource = (
  directiveNode: DirectiveNode,
  source: string,
  index: number | undefined,
  parent: DirectiveParent | undefined,
) => {
  const start = directiveNode.position?.start?.offset;
  const end = directiveNode.position?.end?.offset;
  if (
    typeof index !== "number"
    || !parent?.children
    || typeof start !== "number"
    || typeof end !== "number"
  ) {
    return;
  }

  parent.children[index] = {
    type: "text",
    value: source.slice(start, end),
  };
};

const visitMarkdownDirectives = (
  tree: unknown,
  handleDirective: (
    directiveNode: DirectiveNode,
    name: string,
    index: number | undefined,
    parent: DirectiveParent | undefined,
  ) => void,
) => {
  visit(tree, (node, index, parent) => {
    if (
      !node
      || typeof node !== "object"
      || !("type" in node)
      || (node.type !== "containerDirective" && node.type !== "leafDirective" && node.type !== "textDirective")
    ) {
      return;
    }

    const directiveNode = node as DirectiveNode;
    const name = getStringAttribute(directiveNode.name);
    if (name) {
      handleDirective(directiveNode, name, index, parent as DirectiveParent | undefined);
    }
  });
};

export const remarkAerisunIndentDirectives: Plugin = () => {
  return (tree, file) => {
    const source = String(file.value ?? "");

    visitMarkdownDirectives(tree, (directiveNode, name, index, parent) => {
      if (applyIndentDirective(directiveNode, name)) {
        return;
      }

      restoreDirectiveSource(directiveNode, source, index, parent);
    });
  };
};

export const remarkAerisunDirectives: Plugin = () => {
  return (tree, file) => {
    const source = String(file.value ?? "");

    visitMarkdownDirectives(tree, (directiveNode, name, index, parent) => {
      if (applyIndentDirective(directiveNode, name)) {
        return;
      }

      const tagName = getTagName(directiveNode);
      const data = directiveNode.data || (directiveNode.data = {});
      const attributes = directiveNode.attributes || {};
      const baseProps: Record<string, string | number> = {};

      if (ADMONITION_NAMES.has(name)) {
        data.hName = tagName;
        data.hProperties = {
          ...baseProps,
          "data-md-kind": "admonition",
          "data-md-type": name,
          "data-md-title": getStringAttribute(attributes.title),
        };
        return;
      }

      switch (name) {
        case "copy":
          data.hName = tagName;
          data.hProperties = {
            ...baseProps,
            "data-md-kind": "copy",
            "data-md-title": getStringAttribute(attributes.title),
            "data-md-label": getStringAttribute(attributes.label),
            "data-md-value":
              getStringAttribute(attributes.value)
              || getStringAttribute(attributes.copy)
              || getStringAttribute(attributes.text),
          };
          return;

        case "details":
          data.hName = tagName;
          data.hProperties = {
            ...baseProps,
            "data-md-kind": "details",
            "data-md-summary": getStringAttribute(attributes.summary) || getStringAttribute(attributes.title),
          };
          return;

        case "underline":
          data.hName = tagName;
          data.hProperties = {
            ...baseProps,
            "data-md-kind": "underline",
          };
          return;

        case "thumb":
        case "thumbnail":
          data.hName = tagName;
          data.hProperties = {
            ...baseProps,
            "data-md-kind": "thumbnail",
          };
          return;

        case "carousel":
          data.hName = tagName;
          data.hProperties = {
            ...baseProps,
            "data-md-kind": "carousel",
          };
          return;

        case "tabs":
          data.hName = tagName;
          data.hProperties = {
            ...baseProps,
            "data-md-kind": "tabs",
          };
          return;

        case "tab":
          data.hName = tagName;
          data.hProperties = {
            ...baseProps,
            "data-md-kind": "tab",
            "data-md-title": getStringAttribute(attributes.title) || getStringAttribute(attributes.label),
          };
          return;

        case "steps":
          data.hName = tagName;
          data.hProperties = {
            ...baseProps,
            "data-md-kind": "steps",
          };
          return;

        default:
          restoreDirectiveSource(directiveNode, source, index, parent);
          return;
      }
    });
  };
};
