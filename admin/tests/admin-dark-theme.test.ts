import fs from "node:fs";
import { describe, expect, it } from "vitest";

const css = fs.readFileSync(new URL("../src/index.css", import.meta.url), "utf-8");

function darkThemeToken(name: string) {
  const darkBlock = css.match(/^\s*\.dark\s*\{([\s\S]*?)^\s*\}/m)?.[1] ?? "";
  const tokenMatch = darkBlock.match(new RegExp(`${name}:\\s*([^;]+);`));
  return tokenMatch?.[1].trim();
}

describe("admin dark theme tokens", () => {
  it("uses a graphite dark palette with a muted sage accent", () => {
    expect(darkThemeToken("--background")).toBe("240 10% 7%");
    expect(darkThemeToken("--foreground")).toBe("240 11% 93%");
    expect(darkThemeToken("--primary")).toBe("158 28% 54%");
    expect(darkThemeToken("--primary-foreground")).toBe("160 20% 8%");
    expect(darkThemeToken("--ring")).toBe("158 34% 55%");
    expect(darkThemeToken("--admin-accent-rgb")).toBe("122 169 147");
    expect(darkThemeToken("--admin-glow-rgb")).toBe("155 188 172");
  });

  it("keeps dark surfaces layered and legible instead of transparent navy", () => {
    expect(darkThemeToken("--admin-surface-1")).toBe("28 29 34");
    expect(darkThemeToken("--admin-surface-2")).toBe("18 19 23");
    expect(darkThemeToken("--admin-surface-strong")).toBe("34 35 41");
    expect(darkThemeToken("--admin-surface-elevated")).toBe("42 44 51");
    expect(darkThemeToken("--admin-surface-alpha")).toBe("0.72");
    expect(darkThemeToken("--admin-surface-alpha-strong")).toBe("0.88");
    expect(darkThemeToken("--admin-surface-alpha-soft")).toBe("0.58");
  });

  it("keeps subtle rim highlights on dark glass surfaces", () => {
    expect(css).toContain(`.dark .admin-glass::before,
.dark .admin-glass-strong::before {
  opacity: 0.45;
}`);
  });
});
