// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { LanguageProvider } from "../src/i18n";
import DiagnosticsPage from "../src/pages/system/DiagnosticsPage";
import {
  diagnosticPollingInterval,
  systemDiagnosticsQueryOptions,
} from "../src/pages/system/diagnosticsQueries";

const api = vi.hoisted(() => ({
  state: {
    execution_status: "completed",
    overall_status: "attention",
    trigger_kind: "scheduled",
    run_id: "run-1",
    is_running: false,
    is_stale: false,
    healthy_count: 2,
    warning_count: 1,
    failed_count: 1,
    skipped_count: 1,
    issue_count: 2,
    started_at: "2026-08-09T04:20:00+08:00",
    completed_at: "2026-08-09T04:20:12+08:00",
    last_error: null,
    items: [
      {
        key: "database",
        status: "healthy",
        summary: "数据库连接正常",
        action_target: "system",
        duration_ms: 8,
      },
      {
        key: "smtp",
        status: "failed",
        summary: "SMTP 连接或认证失败",
        detail: "认证被拒绝",
        action_target: "smtp",
        duration_ms: 40,
      },
      {
        key: "object_storage",
        status: "warning",
        summary: "对象存储可用，但有 2 个同步任务失败",
        action_target: "object_storage_sync",
        duration_ms: 30,
      },
      {
        key: "mcp",
        status: "skipped",
        summary: "MCP 服务未启用",
        action_target: "mcp",
        duration_ms: 1,
      },
    ],
  } as any,
  get: vi.fn(),
  run: vi.fn(),
}));

vi.mock("@serino/api-client/admin", () => ({
  getSystemDiagnosticsStateApiV1AdminSystemDiagnosticsGet: (...args: unknown[]) =>
    api.get(...args),
  startSystemDiagnosticsRunApiV1AdminSystemDiagnosticsRunPost: (...args: unknown[]) =>
    api.run(...args),
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <MemoryRouter future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
      <QueryClientProvider client={queryClient}>
        <LanguageProvider>
          <DiagnosticsPage />
        </LanguageProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

function renderEnglishPage() {
  localStorage.setItem("aerisun-admin-lang", "en");
  return renderPage();
}

beforeEach(() => {
  localStorage.clear();
  api.get.mockResolvedValue({ data: api.state, status: 200, headers: new Headers() });
  api.run.mockResolvedValue({
    data: {
      ...api.state,
      execution_status: "queued",
      is_running: true,
    },
    status: 202,
    headers: new Headers(),
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("DiagnosticsPage", () => {
  it("shows the latest diagnostic time beside the title without the removed intro copy", async () => {
    renderPage();

    const title = await screen.findByRole("heading", { level: 1 });
    expect(title.textContent).toContain("系统诊断");
    expect(title.textContent).toContain("最新诊断：");
    await waitFor(() => expect(title.textContent).toContain("2026"));
    expect(screen.queryByText("检查一切正常")).toBeNull();
    expect(screen.queryByText("发现 2 个问题")).toBeNull();
    expect(
      screen.queryByText(
        "每天自动检查核心服务与已启用的集成；未启用的可选功能会跳过，不会被当作故障。",
      ),
    ).toBeNull();
    expect(screen.queryByText("检查明细")).toBeNull();
    expect(screen.queryByText("系统与集成状态")).toBeNull();
    expect(
      screen.queryByText("网络检查采用短超时并顺序执行，避免给系统和外部服务增加突发负担。"),
    ).toBeNull();
  });

  it("shows every result and links problems to the exact repair page", async () => {
    renderPage();

    const smtpCard = (await screen.findByText("SMTP 连接或认证失败")).closest("article");
    const ossCard = screen.getByText("对象存储可用，但有 2 个同步任务失败").closest("article");
    const mcpCard = screen.getByText("MCP 服务未启用").closest("article");

    expect(within(smtpCard as HTMLElement).getByRole("link", { name: "前往处理：邮箱配置" }).getAttribute("href")).toBe("/more/mail-config");
    expect(within(ossCard as HTMLElement).getByRole("link", { name: "前往处理：对象存储 OSS" }).getAttribute("href")).toBe("/assets?view=oss_sync");
    const mcpLink = within(mcpCard as HTMLElement).getByRole("link", { name: "查看配置：MCP 服务" });
    expect(mcpLink.getAttribute("href")).toBe("/integrations/mcp/settings");
    expect(mcpLink.className).toContain("absolute");
    expect(mcpLink.className).toContain("inset-0");
    expect(within(mcpCard as HTMLElement).getByText("未启用")).toBeTruthy();

    const cards = screen.getAllByRole("article");
    expect(cards[0].parentElement?.className).toContain("lg:grid-cols-3");
    expect(within(cards[0]).getByText("SMTP 连接或认证失败")).toBeTruthy();
    expect(within(cards[1]).getByText("对象存储可用，但有 2 个同步任务失败")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "需要处理" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "检查正常" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "未启用或已跳过" })).toBeNull();
  });

  it("keeps the previous result visible while a new check is running", async () => {
    api.get.mockResolvedValueOnce({
      data: { ...api.state, execution_status: "running", is_running: true },
      status: 200,
      headers: new Headers(),
    });

    renderPage();

    expect(await screen.findByText("SMTP 连接或认证失败")).toBeTruthy();
    expect(screen.getByRole("button", { name: "检查中…" })).toBeTruthy();
  });

  it("starts an immediate check and shows the running state", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("SMTP 连接或认证失败");
    await user.click(screen.getByRole("button", { name: "立即检查" }));

    expect(api.run).toHaveBeenCalledTimes(1);
    expect(await screen.findByRole("button", { name: "检查中…" })).toBeTruthy();
  });

  it("shows a clear error when an immediate check cannot be started", async () => {
    api.run.mockRejectedValueOnce(new Error("network unavailable"));
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("SMTP 连接或认证失败");
    await user.click(screen.getByRole("button", { name: "立即检查" }));

    expect(await screen.findByText("无法启动检查，请稍后重试。")).toBeTruthy();
  });

  it("distinguishes a load failure from a never-run result and can retry", async () => {
    api.get.mockRejectedValueOnce(new Error("temporarily unavailable"));
    const user = userEvent.setup();
    renderPage();

    expect((await screen.findByRole("alert")).textContent).toContain("暂时无法读取诊断结果");
    expect(screen.queryByText("尚未检查")).toBeNull();
    await user.click(screen.getByRole("button", { name: "重新加载" }));

    expect(await screen.findByText("SMTP 连接或认证失败")).toBeTruthy();
    expect(api.get).toHaveBeenCalledTimes(2);
  });

  it("does not claim all-clear while the first queued check has no completed result", async () => {
    api.get.mockResolvedValueOnce({
      data: {
        execution_status: "queued",
        overall_status: "unknown",
        trigger_kind: "manual",
        run_id: "first-run",
        is_running: true,
        is_stale: false,
        healthy_count: 0,
        warning_count: 0,
        failed_count: 0,
        skipped_count: 0,
        issue_count: 0,
        items: [],
      },
      status: 200,
      headers: new Headers(),
    });

    renderPage();

    expect(await screen.findByText("最新诊断：尚未检查")).toBeTruthy();
    expect(screen.getByRole("button", { name: "检查中…" })).toBeTruthy();
    expect(screen.queryByText("检查一切正常")).toBeNull();
  });

  it("links every configurable problem to its exact settings page and guides host-level fixes inline", async () => {
    api.get.mockResolvedValueOnce({
      data: {
        ...api.state,
        issue_count: 9,
        failed_count: 9,
        warning_count: 0,
        healthy_count: 0,
        skipped_count: 0,
        items: [
          ["database", "system", "数据库失败"],
          ["model_api", "model_api", "模型失败"],
          ["smtp", "smtp", "邮箱失败"],
          ["proxy", "proxy", "代理失败"],
          ["object_storage", "object_storage", "OSS 配置失败"],
          ["object_storage", "object_storage_sync", "OSS 同步失败"],
          ["backup", "backup_settings", "备份配置失败"],
          ["backup", "backup_runs", "备份任务失败"],
          ["mcp", "mcp", "MCP 失败"],
        ].map(([key, action_target, summary]) => ({
          key,
          action_target,
          summary,
          status: "failed",
        })),
      },
      status: 200,
      headers: new Headers(),
    });
    renderPage();

    await screen.findByText("数据库失败");
    const expectedRoutes: Record<string, string> = {
      "模型失败": "/more/api-config",
      "邮箱失败": "/more/mail-config",
      "代理失败": "/more/proxy-config",
      "OSS 配置失败": "/more/object-storage",
      "OSS 同步失败": "/assets?view=oss_sync",
      "备份配置失败": "/system/backups",
      "备份任务失败": "/system/backups?section=records&records=runs",
      "MCP 失败": "/integrations/mcp/settings",
    };
    for (const [summary, route] of Object.entries(expectedRoutes)) {
      const card = screen.getByText(summary).closest("article");
      expect(within(card as HTMLElement).getByRole("link").getAttribute("href")).toBe(route);
    }
    const databaseCard = screen.getByText("数据库失败").closest("article");
    expect(within(databaseCard as HTMLElement).queryByRole("link")).toBeNull();
    expect(within(databaseCard as HTMLElement).getByText(/部署环境/)).toBeTruthy();
  });

  it("polls active checks and refreshes dashboard summaries at a low frequency", () => {
    expect(diagnosticPollingInterval({ is_running: true })).toBe(3_000);
    expect(diagnosticPollingInterval({ is_running: true }, 1)).toBe(false);
    expect(diagnosticPollingInterval({ is_running: false })).toBe(false);
    expect(diagnosticPollingInterval({ is_running: false }, 0, 5 * 60_000)).toBe(5 * 60_000);
    expect(diagnosticPollingInterval({ is_running: false }, 1, 5 * 60_000)).toBe(false);
    expect(diagnosticPollingInterval(undefined)).toBe(false);

    const detailedOptions = systemDiagnosticsQueryOptions({
      includeItems: true,
      pollWhileRunning: true,
    });
    expect(detailedOptions.refetchOnMount).toBe("always");
    expect(detailedOptions.refetchIntervalInBackground).toBe(false);
  });

  it("renders structured diagnostic messages in the selected language", async () => {
    api.get.mockResolvedValueOnce({
      data: {
        ...api.state,
        issue_count: 1,
        failed_count: 0,
        warning_count: 1,
        healthy_count: 0,
        skipped_count: 0,
        items: [
          {
            key: "object_storage",
            status: "warning",
            summary: "对象存储可用，但有 2 个同步任务失败",
            summary_key: "diagnostics.result.objectStorageSyncFailures",
            summary_params: { count: 2 },
            action_target: "object_storage_sync",
          },
        ],
      },
      status: 200,
      headers: new Headers(),
    });

    renderEnglishPage();

    expect(
      await screen.findByText("2 object storage sync jobs exhausted their retries"),
    ).toBeTruthy();
    expect(screen.queryByText("对象存储可用，但有 2 个同步任务失败")).toBeNull();
  });
});
