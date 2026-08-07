type DirectiveNode = {
  type?: string;
  name?: string;
  attributes?: Record<string, string | null | undefined>;
  data?: {
    hName?: string;
    hProperties?: Record<string, string>;
  };
  children?: unknown[];
  position?: {
    start?: { offset?: number };
    end?: { offset?: number };
  };
};

type DirectiveParent = {
  children?: unknown[];
};

const walkDirectiveNodes = (
  node: unknown,
  visit: (
    node: DirectiveNode,
    index: number | undefined,
    parent: DirectiveParent | undefined,
  ) => void,
  index?: number,
  parent?: DirectiveParent,
) => {
  if (!node || typeof node !== "object") return;

  if (Array.isArray(node)) {
    const arrayParent = { children: node };
    node.forEach((child, childIndex) =>
      walkDirectiveNodes(child, visit, childIndex, arrayParent));
    return;
  }

  const current = node as DirectiveNode;
  visit(current, index, parent);
  current.children?.forEach((child, childIndex) =>
    walkDirectiveNodes(child, visit, childIndex, current));
};

const getAttribute = (value?: string | null) => (value ?? "").trim();

export const remarkAdminMarkdownDirectives = () => (
  tree: unknown,
  file: { value?: unknown },
) => {
  const source = String(file.value ?? "");

  walkDirectiveNodes(tree, (node, index, parent) => {
    if (
      node.type !== "containerDirective"
      && node.type !== "leafDirective"
      && node.type !== "textDirective"
    ) {
      return;
    }

    const name = getAttribute(node.name);
    if (!name) {
      return;
    }

    const tagName = node.type === "textDirective" ? "span" : "div";
    const data = node.data || (node.data = {});

    if (node.type === "textDirective" && (name === "indent" || name === "noindent")) {
      data.hName = "span";
      data.hProperties = { "data-md-kind": name };
      return;
    }

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
      return;
    }

    const start = node.position?.start?.offset;
    const end = node.position?.end?.offset;
    if (
      typeof index === "number"
      && parent?.children
      && typeof start === "number"
      && typeof end === "number"
    ) {
      parent.children[index] = {
        type: "text",
        value: source.slice(start, end),
      };
    }
  });
};
