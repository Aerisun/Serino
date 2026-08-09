// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "../src/i18n";
import { AgentModelConfigSection } from "../src/pages/automation/AgentModelConfigSection";

const api = vi.hoisted(() => ({
  getConfig: vi.fn(),
  updateConfig: vi.fn(),
  getAccount: vi.fn(),
  startLogin: vi.fn(),
  loginStatus: vi.fn(),
  logout: vi.fn(),
  getModels: vi.fn(),
  diagnose: vi.fn(),
  getProxy: vi.fn(),
}));
const notifications = vi.hoisted(() => ({
  success: vi.fn(),
  warning: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
}));

function modelConfig() {
  return {
    schema_version: 2,
    primary_source: "chatgpt_oauth",
    chatgpt_oauth: {
      enabled: true,
      model: "gpt-5.2-codex",
      timeout_seconds: 60,
      connected: false,
      account_email: null,
      plan_type: null,
      is_ready: false,
    },
    openai_compatible: {
      enabled: true,
      provider: "openai_compatible",
      base_url: "https://api.example.test/v1",
      model: "fallback-model",
      api_key_configured: true,
      temperature: 0.2,
      timeout_seconds: 20,
      advisory_prompt: "",
      is_ready: true,
    },
    is_ready: true,
  };
}

vi.mock("sonner", () => ({ toast: notifications }));

vi.mock("../src/pages/automation/api", () => ({
  getAgentModelConfig: (...args: unknown[]) => api.getConfig(...args),
  updateAgentModelConfig: (...args: unknown[]) => api.updateConfig(...args),
  getChatGPTAccount: (...args: unknown[]) => api.getAccount(...args),
  startChatGPTLogin: (...args: unknown[]) => api.startLogin(...args),
  getChatGPTLoginStatus: (...args: unknown[]) => api.loginStatus(...args),
  logoutChatGPTAccount: (...args: unknown[]) => api.logout(...args),
  getChatGPTModels: (...args: unknown[]) => api.getModels(...args),
  diagnoseAgentModelConfig: (...args: unknown[]) => api.diagnose(...args),
  getOutboundProxyConfig: (...args: unknown[]) => api.getProxy(...args),
}));

function renderSection() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <LanguageProvider>
        <AgentModelConfigSection />
      </LanguageProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  api.getConfig.mockResolvedValue(modelConfig());
  api.updateConfig.mockResolvedValue(modelConfig());
  api.getAccount.mockResolvedValue({
    connected: true,
    email: "owner@example.com",
    plan_type: "plus",
    error: null,
  });
  api.getModels.mockResolvedValue([
    { model: "gpt-5.2-codex", display_name: "GPT-5.2 Codex", is_default: true },
  ]);
  api.getProxy.mockResolvedValue({
    proxy_port: 7890,
    webhook_enabled: false,
    oauth_enabled: true,
  });
  api.diagnose.mockResolvedValue({
    status: "warning",
    primary_source: "chatgpt_oauth",
    active_source: "chatgpt_oauth",
    summary: "一个模型来源不可用，已保留可用来源用于自动容灾。",
    items: [
      {
        source: "chatgpt_oauth",
        status: "healthy",
        model: "gpt-5.2-codex",
        summary: "ChatGPT OAuth 响应正常",
      },
      {
        source: "openai_compatible",
        status: "failed",
        model: "fallback-model",
        summary: "OpenAI-compatible API 当前不可用",
        detail: "fallback offline",
      },
    ],
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AgentModelConfigSection", () => {
  it("shows compact source switches without a duplicate diagnostic panel", async () => {
    const user = userEvent.setup();
    const firstRender = renderSection();

    expect(await screen.findByText("模型配置")).toBeTruthy();
    expect(screen.queryByText("AI")).toBeNull();
    expect(screen.getAllByText("启用")).toHaveLength(2);
    expect(screen.getByText("owner@example.com")).toBeTruthy();
    expect(screen.getByDisplayValue("https://api.example.test/v1")).toBeTruthy();
    expect(screen.getByRole("tab", { name: /ChatGPT OAuth/ }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("switch", { name: "启用此来源：ChatGPT OAuth" })).toBeTruthy();
    expect(screen.getByRole("switch", { name: "启用此来源：OpenAI-compatible API" })).toBeTruthy();

    const diagnoseButton = screen.getByRole("button", { name: "诊断" });
    expect(diagnoseButton.previousElementSibling?.textContent).toBe("待测试");

    await user.click(diagnoseButton);

    await waitFor(() =>
      expect(notifications.warning).toHaveBeenCalledWith(
        "OpenAI-compatible API 当前不可用",
        {
          description:
            "fallback offline；一个模型来源不可用，已保留可用来源用于自动容灾。",
        },
      ),
    );
    expect(notifications.success).toHaveBeenCalledWith("ChatGPT OAuth 响应正常");
    expect(notifications.success).toHaveBeenCalledTimes(1);
    expect(notifications.warning).toHaveBeenCalledTimes(1);
    expect(screen.getByText("无效")).toBeTruthy();
    expect(screen.getByRole("status", { name: "ChatGPT OAuth 响应正常" })).toBeTruthy();
    expect(screen.getByRole("status", { name: "OpenAI-compatible API 当前不可用" })).toBeTruthy();
    expect(screen.queryByText("ChatGPT OAuth 响应正常")).toBeNull();
    expect(screen.queryByText("OpenAI-compatible API 当前不可用")).toBeNull();
    expect(screen.queryByText("一个模型来源不可用，已保留可用来源用于自动容灾。")).toBeNull();
    expect(notifications.warning).not.toHaveBeenCalledWith(
      "一个模型来源不可用，已保留可用来源用于自动容灾。",
      expect.anything(),
    );

    firstRender.unmount();
    renderSection();

    expect(await screen.findByRole("status", { name: "ChatGPT OAuth 响应正常" })).toBeTruthy();
    expect(
      screen.getByRole("status", { name: "OpenAI-compatible API 当前不可用" }),
    ).toBeTruthy();
  });

  it("shows and retains a healthy status without adding an inline result", async () => {
    api.diagnose.mockResolvedValueOnce({
      status: "healthy",
      primary_source: "chatgpt_oauth",
      active_source: "chatgpt_oauth",
      summary: "已启用的模型来源均可用。",
      items: [
        {
          source: "chatgpt_oauth",
          status: "healthy",
          model: "gpt-5.2-codex",
          summary: "ChatGPT OAuth 响应正常",
        },
        {
          source: "openai_compatible",
          status: "healthy",
          model: "fallback-model",
          summary: "OpenAI-compatible API 响应正常",
        },
      ],
    });
    const user = userEvent.setup();
    const firstRender = renderSection();

    await screen.findByText("模型配置");
    await user.click(screen.getByRole("button", { name: "诊断" }));

    await waitFor(() => expect(notifications.success).toHaveBeenCalledTimes(2));
    expect(notifications.success).toHaveBeenNthCalledWith(1, "ChatGPT OAuth 响应正常");
    expect(notifications.success).toHaveBeenNthCalledWith(2, "OpenAI-compatible API 响应正常");
    expect(notifications.success).not.toHaveBeenCalledWith("已启用的模型来源均可用。");
    expect(screen.getByText("可用")).toBeTruthy();
    expect(screen.queryByText("已启用的模型来源均可用。")).toBeNull();

    firstRender.unmount();
    renderSection();

    expect(await screen.findByText("可用")).toBeTruthy();
    expect(screen.getByRole("status", { name: "ChatGPT OAuth 响应正常" })).toBeTruthy();
    expect(screen.getByRole("status", { name: "OpenAI-compatible API 响应正常" })).toBeTruthy();
    expect(api.diagnose).toHaveBeenCalledTimes(1);
  });

  it("saves first, diagnoses automatically, and resets the status after another edit", async () => {
    api.updateConfig.mockResolvedValueOnce({
      ...modelConfig(),
      openai_compatible: {
        ...modelConfig().openai_compatible,
        model: "updated-model",
      },
    });
    const user = userEvent.setup();
    renderSection();

    const modelInput = await screen.findByDisplayValue("fallback-model");
    await user.clear(modelInput);
    await user.type(modelInput, "updated-model");
    expect(screen.getByText("待测试")).toBeTruthy();
    expect(screen.getByRole("button", { name: "诊断" }).hasAttribute("disabled")).toBe(true);

    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(api.updateConfig).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(api.diagnose).toHaveBeenCalledTimes(1));
    expect(screen.getByText("无效")).toBeTruthy();

    await user.type(screen.getByDisplayValue("updated-model"), "-draft");
    expect(screen.getByText("待测试")).toBeTruthy();
  });

  it("does not enable ChatGPT OAuth until the OAuth proxy is configured", async () => {
    api.getConfig.mockResolvedValueOnce({
      ...(await api.getConfig()),
      chatgpt_oauth: {
        enabled: false,
        model: "gpt-5.2-codex",
        timeout_seconds: 60,
        connected: false,
        account_email: null,
        plan_type: null,
        is_ready: false,
      },
    });
    api.getProxy.mockResolvedValueOnce({
      proxy_port: null,
      webhook_enabled: false,
      oauth_enabled: false,
    });
    const user = userEvent.setup();
    renderSection();

    const toggle = await screen.findByRole("switch", { name: "启用此来源：ChatGPT OAuth" });
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    await user.click(toggle);

    expect(toggle.getAttribute("aria-checked")).toBe("false");
    expect(notifications.warning).toHaveBeenCalledWith("请先在代理设置中填写代理端口并开启 OAuth 代理。");
    expect(api.getAccount).not.toHaveBeenCalled();
  });
});
