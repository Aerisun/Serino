// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "../src/i18n";
import { ProxyConfigSection } from "../src/pages/more/ProxyConfigSection";

const api = vi.hoisted(() => ({
  get: vi.fn(),
  save: vi.fn(),
  test: vi.fn(),
}));
const notifications = vi.hoisted(() => ({
  success: vi.fn(),
  warning: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: notifications }));

vi.mock("@serino/api-client/admin", () => ({
  getProxyConfigApiV1AdminProxyConfigGet: (...args: unknown[]) =>
    api.get(...args),
  putProxyConfigApiV1AdminProxyConfigPut: (...args: unknown[]) =>
    api.save(...args),
  postProxyConfigTestApiV1AdminProxyConfigTestPost: (...args: unknown[]) =>
    api.test(...args),
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
        <ProxyConfigSection />
      </LanguageProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  api.get.mockResolvedValue({
    data: {
      proxy_port: 7890,
      webhook_enabled: false,
      oauth_enabled: true,
    },
  });
  api.test.mockResolvedValue({
    data: {
      ok: true,
      proxy_url: "http://127.0.0.1:7890",
      summary: "代理端口测试通过",
    },
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ProxyConfigSection", () => {
  it("omits the OAuth dependency note and detailed health result cards", async () => {
    const user = userEvent.setup();
    renderSection();

    await screen.findByRole("switch", { name: "OAuth 走代理" });
    expect(
      screen.queryByText(
        "ChatGPT OAuth 来源依赖 OAuth 代理；关闭前需要先在模型配置中停用 ChatGPT OAuth。",
      ),
    ).toBeNull();

    await user.click(screen.getByRole("button", { name: "端口测试" }));
    await waitFor(() => expect(api.test).toHaveBeenCalledTimes(1));

    expect(screen.queryByText("最近一次测试")).toBeNull();
    expect(screen.queryByText("http://127.0.0.1:7890")).toBeNull();
  });

  it("shows the backend action message when ChatGPT still requires the OAuth proxy", async () => {
    const detail = "ChatGPT OAuth 来源已启用，请先停用该来源再关闭 OAuth 代理。";
    api.save.mockRejectedValue(
      Object.assign(new Error("Request failed with status code 422"), {
        response: { data: { detail } },
      }),
    );
    const user = userEvent.setup();
    renderSection();

    const oauthSwitch = await screen.findByRole("switch", {
      name: "OAuth 走代理",
    });
    await user.click(oauthSwitch);
    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(notifications.error).toHaveBeenCalledWith(detail));
    expect(api.test).not.toHaveBeenCalled();
  });
});
