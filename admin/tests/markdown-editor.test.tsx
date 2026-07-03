// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";
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
      <MarkdownEditor value={value} onChange={setValue} minHeight="200px" />
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
