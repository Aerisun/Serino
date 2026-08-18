// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "../src/i18n";
import {
  McpInstallGuide,
  buildMcpInstallCommands,
} from "../src/pages/integrations/McpInstallGuide";

const clipboardWrite = vi.fn();

function renderGuide(
  endpoint = "https://blog.example/api/mcp/",
  usageUrl = "https://blog.example/api/agent/usage",
) {
  return render(
    <LanguageProvider>
      <McpInstallGuide endpoint={endpoint} usageUrl={usageUrl} />
    </LanguageProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  clipboardWrite.mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: clipboardWrite },
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("McpInstallGuide", () => {
  it("builds both installers from the configured MCP domain", () => {
    expect(buildMcpInstallCommands("https://blog.example/api/mcp/")).toEqual({
      codex: "curl -fsSL https://blog.example/mcp/install/codex.sh | sh",
      claude: "curl -fsSL https://blog.example/mcp/install/claude.sh | sh",
      updateKey: "~/.local/bin/serino-mcp-key",
    });
  });

  it("keeps only two compact usage guide entries in the settings card", () => {
    renderGuide();

    const title = screen.getByText("使用说明");
    expect(title.parentElement?.getAttribute("class")).toBeNull();
    expect(screen.getByRole("button", { name: "REST API 接入" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Codex / Claude Code 接入" })).toBeTruthy();
    expect(screen.queryByText("手动配置 Endpoint 与 Bearer API Key")).toBeNull();
    expect(screen.queryByText("一条命令安装 MCP 与 Skills")).toBeNull();
    expect(screen.queryByText("https://blog.example/api/agent/usage")).toBeNull();
    expect(screen.queryByText("curl -fsSL", { exact: false })).toBeNull();
  });

  it("shows the agent handoff flow without raw REST fields", async () => {
    const user = userEvent.setup();
    renderGuide();

    await user.click(screen.getByRole("button", { name: /REST API 接入/ }));

    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "REST API 接入" })).toBeTruthy();
    expect(screen.queryByText("https://blog.example/api/mcp/")).toBeNull();
    expect(screen.queryByText("Authorization: Bearer <API Key>")).toBeNull();
    expect(screen.queryByText("MCP Endpoint")).toBeNull();
    expect(screen.queryByText("鉴权请求头")).toBeNull();
    expect(screen.queryByText("Usage URL")).toBeNull();

    expect(screen.getByText("创建并保存 API Key")).toBeTruthy();
    expect(
      screen.getByText(
        "在 MCP 权限配置中勾选 Agent 需要的权限，创建后保存完整密钥串。",
      ),
    ).toBeTruthy();
    expect(screen.getByText("把 Key 交给 Agent，让它去了解")).toBeTruthy();
    expect(screen.getByText("将密钥串发给 Agent，并让它访问", { exact: false })).toBeTruthy();
    const usageLink = screen.getByRole("link", {
      name: "https://blog.example/api/agent/usage",
    });
    expect(usageLink.getAttribute("href")).toBe(
      "https://blog.example/api/agent/usage",
    );
    expect(screen.getByText("读取使用说明与可用能力。", { exact: false })).toBeTruthy();
    expect(screen.getByText("开始管理网站")).toBeTruthy();
    expect(
      screen.getByText(
        "读取完成后，Agent 会按这把 Key 的权限工作。接下来直接告诉它你想完成什么。",
      ),
    ).toBeTruthy();
  });

  it("shows client installers, bundled skills, and the key update command in a dialog", async () => {
    const user = userEvent.setup();
    renderGuide();

    await user.click(screen.getByRole("button", { name: /Codex \/ Claude Code 接入/ }));

    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByText("运行安装命令")).toBeTruthy();
    expect(screen.queryByText("输入 API Key")).toBeNull();
    const credentialStep = screen.getByText("按照提示输入 Serino MCP API Key");
    expect(credentialStep.className).toContain("font-semibold");
    expect(
      screen.getByText(
        "之后无需其他操作：安装器会完成 MCP、Skills、配置与 Key 保存，并让 Codex 自动重连。Claude Code 用户安装后请重启客户端。",
      ),
    ).toBeTruthy();
    expect(screen.getByText("以后更换 MCP API Key")).toBeTruthy();
    expect(screen.getByText("运行以下命令输入新 Key；Codex 会自动重连。"))
      .toBeTruthy();

    const stepList = screen.getByText("运行安装命令").closest("ol");
    expect(stepList).not.toBeNull();
    const steps = stepList?.querySelectorAll(":scope > li");
    expect(steps).toHaveLength(2);
    expect(steps?.[0]?.textContent).toContain("运行安装命令");
    expect(steps?.[1]?.textContent).toContain("2按照提示输入 Serino MCP API Key");
    expect(steps?.[1]?.textContent).toContain("之后无需其他操作");
    expect(
      screen.getByText("curl -fsSL https://blog.example/mcp/install/codex.sh | sh"),
    ).toBeTruthy();
    expect(
      screen.getByText("curl -fsSL https://blog.example/mcp/install/claude.sh | sh"),
    ).toBeTruthy();
    expect(screen.queryByText("~/.local/bin/serino-mcp-activate")).toBeNull();
    expect(screen.getByText("~/.local/bin/serino-mcp-key")).toBeTruthy();
    expect(screen.queryByText("/mcp/install/key.sh", { exact: false })).toBeNull();
    expect(screen.queryByText("选择客户端运行一条命令，MCP 和 Skills 会一起安装。")).toBeNull();
    expect(screen.queryByText("选择你使用的客户端；MCP 与 Skills 会一起安装。")).toBeNull();
    expect(screen.queryByText("不联网、不重装。", { exact: false })).toBeNull();

    const codexCommand = screen.getByText(
      "curl -fsSL https://blog.example/mcp/install/codex.sh | sh",
    );
    expect(codexCommand.className).toContain("whitespace-pre-wrap");
    expect(codexCommand.className).not.toContain("overflow-x-auto");
  });

  it("copies the exact Codex install command", async () => {
    const user = userEvent.setup();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: clipboardWrite },
    });
    renderGuide();

    await user.click(screen.getByRole("button", { name: /Codex \/ Claude Code 接入/ }));
    await user.click(screen.getByRole("button", { name: "复制 Codex 安装命令" }));

    expect(clipboardWrite).toHaveBeenCalledWith(
      "curl -fsSL https://blog.example/mcp/install/codex.sh | sh",
    );
  });

});
