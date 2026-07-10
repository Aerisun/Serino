import { describe, expect, it } from "vitest";
import {
  extractMarkdownImageAttachments,
  stripMarkdownImages,
} from "../../frontend/src/lib/markdown-images";

describe("frontend markdown image attachments", () => {
  it("does not extract images that remain inside a fenced code block", () => {
    const content = [
      "```md",
      "![代码示例](/media/code.png)",
      "``` not-a-close",
      "![仍在代码块](/media/still-code.png)",
      "```",
      "",
      "![正文图片](/media/image_(1).png \"图片标题\")",
    ].join("\n");

    const { images, text } = extractMarkdownImageAttachments(content);

    expect(images).toEqual([
      expect.objectContaining({
        alt: "正文图片",
        src: "/media/image_(1).png",
      }),
    ]);
    expect(text).toContain("![代码示例](/media/code.png)");
    expect(text).toContain("![仍在代码块](/media/still-code.png)");
  });

  it("removes only real image attachments from excerpt card text", () => {
    const content = "前文 ![配图](/media/inline_(1).png) 后文";

    expect(stripMarkdownImages(content)).toBe("前文 后文");
  });
});
