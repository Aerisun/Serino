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
};

const ADMONITION_NAMES = new Set(["tip", "warning", "note", "info", "danger", "success"]);

const getStringAttribute = (value?: string | null) => (value ?? "").trim();

const getTagName = (node: DirectiveNode) => (node.type === "textDirective" ? "span" : "div");

export const remarkAerisunDirectives: Plugin = () => {
  return (tree) => {
    visit(tree, (node) => {
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
      if (!name) {
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

        case "gallery":
          data.hName = tagName;
          data.hProperties = {
            ...baseProps,
            "data-md-kind": "gallery",
          };
          return;

        case "grid":
          data.hName = tagName;
          data.hProperties = {
            ...baseProps,
            "data-md-kind": "grid",
            "data-md-cols": getStringAttribute(attributes.cols),
            "data-md-gap": getStringAttribute(attributes.gap),
            "data-md-min": getStringAttribute(attributes.min),
            "data-md-type": getStringAttribute(attributes.type),
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
          return;
      }
    });
  };
};
