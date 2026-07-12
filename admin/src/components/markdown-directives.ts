type DirectiveNode = {
  type?: string;
  name?: string;
  attributes?: Record<string, string | null | undefined>;
  data?: {
    hName?: string;
    hProperties?: Record<string, string>;
  };
  children?: unknown[];
};

const walkDirectiveNodes = (node: unknown, visit: (node: DirectiveNode) => void) => {
  if (!node || typeof node !== "object") return;

  if (Array.isArray(node)) {
    node.forEach((child) => walkDirectiveNodes(child, visit));
    return;
  }

  const current = node as DirectiveNode;
  visit(current);
  current.children?.forEach((child) => walkDirectiveNodes(child, visit));
};

const getAttribute = (value?: string | null) => (value ?? "").trim();

export const remarkAdminMarkdownDirectives = () => (tree: unknown) => {
  walkDirectiveNodes(tree, (node) => {
    const name = getAttribute(node.name);
    const tagName = node.type === "textDirective" ? "span" : "div";
    const data = node.data || (node.data = {});

    if (name === "underline") {
      data.hName = tagName;
      data.hProperties = { "data-md-kind": "underline" };
      return;
    }

    if (name === "thumb" || name === "thumbnail") {
      data.hName = tagName;
      data.hProperties = { "data-md-kind": "thumbnail" };
      return;
    }

    if (name === "carousel") {
      data.hName = tagName;
      data.hProperties = {
        "data-md-kind": "carousel",
      };
    }
  });
};
