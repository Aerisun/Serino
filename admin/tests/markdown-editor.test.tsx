// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { MarkdownEditor } from "../src/components/MarkdownEditor";
import { LanguageProvider } from "../src/i18n";

function installMatchMedia() {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
}

function MarkdownEditorHarness() {
  const [value, setValue] = useState("");

  return (
    <LanguageProvider>
      <MarkdownEditor assetCategory="post" value={value} onChange={setValue} minHeight="200px" />
    </LanguageProvider>
  );
}

function AttachmentMarkdownEditorHarness() {
  const [value, setValue] = useState("正文开头\n\n![上传截图](/media/internal/assets/markdown-image/example.png)");

  return (
    <LanguageProvider>
      <MarkdownEditor
        assetCategory="thought"
        value={value}
        onChange={setValue}
        minHeight="200px"
        imageLayout="attachments"
      />
      <output data-testid="markdown-value">{value}</output>
    </LanguageProvider>
  );
}

function MarkdownAttachmentRoundTripHarness() {
  const [value, setValue] = useState(
    "正文\n\n```md\n![代码示例](/media/code.png)\n``` not-a-close\n![仍在代码块](/media/still-code.png)\n```\n\n![带标题的图片](/media/image_(1).png \"图片标题\")",
  );

  return (
    <LanguageProvider>
      <MarkdownEditor
        assetCategory="post"
        value={value}
        onChange={setValue}
        minHeight="200px"
        imageLayout="attachments"
      />
      <output data-testid="round-trip-markdown-value">{value}</output>
    </LanguageProvider>
  );
}

function InlineAttachmentPositionHarness() {
  const [value, setValue] = useState("前文 ![配图](/media/inline.png \"标题\") 后文");

  return (
    <LanguageProvider>
      <MarkdownEditor
        assetCategory="post"
        value={value}
        onChange={setValue}
        minHeight="200px"
        imageLayout="attachments"
      />
      <output data-testid="inline-position-markdown-value">{value}</output>
    </LanguageProvider>
  );
}

beforeEach(() => {
  installMatchMedia();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("MarkdownEditor desktop resize", () => {
  it("does not pin textarea height in manual resize mode", async () => {
    const user = userEvent.setup();
    render(<MarkdownEditorHarness />);

    await user.click(screen.getByTitle("收起"));

    const textarea = screen.getByRole("textbox");
    await user.type(textarea, "hello");

    expect(textarea.style.minHeight).toBe("200px");
    expect(textarea.style.height).toBe("");
  });

  it("keeps the expanded auto height when later input measures shorter content", async () => {
    const user = userEvent.setup();
    let measuredScrollHeight = 620;
    const scrollHeightDescriptor = Object.getOwnPropertyDescriptor(
      HTMLTextAreaElement.prototype,
      "scrollHeight",
    );

    Object.defineProperty(HTMLTextAreaElement.prototype, "scrollHeight", {
      configurable: true,
      get() {
        return measuredScrollHeight;
      },
    });

    try {
      render(<MarkdownEditorHarness />);

      const textarea = screen.getByRole("textbox");
      await waitFor(() => expect(textarea.style.height).toBe("620px"));

      measuredScrollHeight = 200;
      await user.type(textarea, "a");

      expect(textarea.style.height).toBe("620px");
    } finally {
      if (scrollHeightDescriptor) {
        Object.defineProperty(
          HTMLTextAreaElement.prototype,
          "scrollHeight",
          scrollHeightDescriptor,
        );
      }
    }
  });
});

describe("MarkdownEditor toolbar focus", () => {
  it("returns focus after bold insertion without scrolling the expanded editor", async () => {
    const user = userEvent.setup();
    render(<MarkdownEditorHarness />);

    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    textarea.focus();
    textarea.setSelectionRange(0, 0);
    const focus = vi.spyOn(textarea, "focus");

    await user.click(screen.getByTitle("bold"));

    await waitFor(() => {
      expect(focus).toHaveBeenCalledWith({ preventScroll: true });
    });
    expect(textarea.value).toBe("**bold text**");
    expect(textarea.selectionStart).toBe(11);
    expect(textarea.selectionEnd).toBe(11);
  });

  it("uses the same scroll-preserving focus behavior after image insertion", () => {
    const source = readFileSync(resolve(process.cwd(), "src/components/MarkdownEditor.tsx"), "utf8");

    expect(source).toMatch(/textarea\?\.focus\(\{ preventScroll: true \}\)/);
  });
});

describe("MarkdownEditor underline toolbar action", () => {
  it("wraps the selected text in the underline directive", async () => {
    const user = userEvent.setup();
    render(<MarkdownEditorHarness />);

    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    await user.type(textarea, "需要强调");
    textarea.setSelectionRange(0, 4);

    await user.click(screen.getByTitle("underline"));

    expect(textarea.value).toBe(":underline[需要强调]");
  });
});

describe("MarkdownEditor thumbnail toolbar action", () => {
  it("wraps a selected Markdown image without requiring directive syntax", async () => {
    const user = userEvent.setup();
    render(<MarkdownEditorHarness />);

    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "![窄图](/media/narrow.png)" } });
    textarea.setSelectionRange(0, textarea.value.length);

    await user.click(screen.getByTitle("缩略图"));

    expect(textarea.value).toBe(":::thumb\n![窄图](/media/narrow.png)\n:::");
  });
});

describe("MarkdownEditor attachment layout", () => {
  it("extracts Markdown images from the textarea and removes them from the saved body", async () => {
    const user = userEvent.setup();
    render(<AttachmentMarkdownEditorHarness />);

    const textarea = screen.getByRole("textbox");
    expect((textarea as HTMLTextAreaElement).value).toContain("正文开头");
    expect((textarea as HTMLTextAreaElement).value).not.toContain("![上传截图]");
    expect(screen.getByRole("img", { name: "上传截图" }).getAttribute("src")).toBe(
      "/media/internal/assets/markdown-image/example.png",
    );

    await user.click(screen.getByRole("button", { name: "删除图片：上传截图" }));

    expect(screen.getByTestId("markdown-value").textContent).toContain("正文开头");
    expect(screen.getByTestId("markdown-value").textContent).not.toContain("markdown-image/example.png");
  });

  it("preserves code examples and exact attachment Markdown when the body changes", async () => {
    const user = userEvent.setup();
    render(<MarkdownAttachmentRoundTripHarness />);

    const textarea = screen.getByRole("textbox");
    expect((textarea as HTMLTextAreaElement).value).toContain("![代码示例](/media/code.png)");
    expect(screen.queryByRole("img", { name: "代码示例" })).toBeNull();
    expect((textarea as HTMLTextAreaElement).value).toContain("![仍在代码块](/media/still-code.png)");
    expect(screen.queryByRole("img", { name: "仍在代码块" })).toBeNull();
    expect(screen.getByRole("img", { name: "带标题的图片" }).getAttribute("src")).toBe(
      "/media/image_(1).png",
    );

    await user.type(textarea, "。");

    const saved = screen.getByTestId("round-trip-markdown-value").textContent ?? "";
    expect(saved).toContain("![代码示例](/media/code.png)");
    expect(saved).toContain("![仍在代码块](/media/still-code.png)");
    expect(saved).toContain('![带标题的图片](/media/image_(1).png "图片标题")');
  });

  it("keeps an existing attachment at its original document position when text changes", async () => {
    render(<InlineAttachmentPositionHarness />);

    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "前文 新增 后文" } });

    expect(screen.getByTestId("inline-position-markdown-value").textContent).toBe(
      "前文 新增![配图](/media/inline.png \"标题\") 后文",
    );
  });
});

describe("MarkdownEditor image upload dialog", () => {
  it("keeps a long selected filename inside the upload dialog", async () => {
    const user = userEvent.setup();
    render(<MarkdownEditorHarness />);

    await user.click(screen.getByTitle("上传图片"));

    const dialog = screen.getByRole("dialog");
    const fileInput = dialog.querySelector<HTMLInputElement>('input[type="file"]');
    if (!fileInput) throw new Error("Expected the image upload dialog to include a file input");

    const fileName = "a-very-long-upload-filename-that-must-not-widen-the-dialog.png";
    await user.upload(fileInput, new File(["image"], fileName, { type: "image/png" }));

    const fileNameElement = within(dialog).getByText(fileName);
    expect(fileNameElement.getAttribute("title")).toBe(fileName);
    expect(fileNameElement.className).toContain("truncate");
    expect(fileNameElement.parentElement?.className).toContain("min-w-0");
    expect(fileNameElement.parentElement?.parentElement?.className).toContain("min-w-0");
  });
});
