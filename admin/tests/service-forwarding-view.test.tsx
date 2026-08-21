// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "../src/i18n";
import { ServiceForwardingView } from "../src/pages/assets/ServiceForwardingView";

const api = vi.hoisted(() => ({
  rules: [
    {
      id: "forward-1",
      name: "代码服务",
      slug: "code",
      path: "/code",
      source: "local",
      target_url: "http://127.0.0.1:3000",
      public_url: "https://site.example/code",
      status: "reachable",
      checked_at: "2026-08-21T20:00:00+08:00",
      status_message: null,
    },
  ] as any[],
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  test: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  clipboardWrite: vi.fn(),
}));

vi.mock("@/pages/assets/serviceForwardApi", () => ({
  listServiceForwards: (...args: unknown[]) => api.list(...args),
  createServiceForward: (...args: unknown[]) => api.create(...args),
  updateServiceForward: (...args: unknown[]) => api.update(...args),
  deleteServiceForward: (...args: unknown[]) => api.remove(...args),
  testServiceForward: (...args: unknown[]) => api.test(...args),
}));

vi.mock("sonner", () => ({
  toast: {
    success: api.toastSuccess,
    error: api.toastError,
  },
}));

function renderView(createOpen = false, onCreateOpenChange = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return {
    onCreateOpenChange,
    ...render(
      <QueryClientProvider client={queryClient}>
        <LanguageProvider>
          <ServiceForwardingView
            createOpen={createOpen}
            onCreateOpenChange={onCreateOpenChange}
          />
        </LanguageProvider>
      </QueryClientProvider>,
    ),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  api.list.mockResolvedValue(api.rules);
  api.create.mockResolvedValue(api.rules[0]);
  api.update.mockResolvedValue(api.rules[0]);
  api.remove.mockResolvedValue(undefined);
  api.test.mockResolvedValue(api.rules[0]);
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: async () => undefined },
  });
  api.clipboardWrite = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);
  window.open = vi.fn();
});

afterEach(() => {
  cleanup();
});

describe("ServiceForwardingView", () => {
  it("shows a retry action when the forwarding list cannot be loaded", async () => {
    api.list.mockRejectedValueOnce(new Error("offline"));
    const user = userEvent.setup();
    renderView();

    expect((await screen.findByRole("alert")).textContent).toContain("无法加载服务转发");
    await user.click(screen.getByRole("button", { name: "重新加载" }));

    await waitFor(() => expect(api.list).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("代码服务")).toBeTruthy();
  });

  it("renders a compact forwarding list and tests a target", async () => {
    const user = userEvent.setup();
    renderView();

    expect(await screen.findByText("代码服务")).toBeTruthy();
    expect(screen.getByText("/code")).toBeTruthy();
    expect(screen.getByText("http://127.0.0.1:3000")).toBeTruthy();
    expect(screen.getByText("可访问")).toBeTruthy();
    const serviceLink = screen.getByRole("link", { name: "打开服务" });
    expect(serviceLink.getAttribute("href")).toBe("/code");
    expect(serviceLink.textContent).toContain("/code");

    await user.click(screen.getByRole("button", { name: "检测连通性" }));

    await waitFor(() => expect(api.test).toHaveBeenCalledWith("forward-1"));
    expect(api.toastSuccess).toHaveBeenCalledWith("服务可以访问");
  });

  it("creates a local forwarding rule without exposing auth settings", async () => {
    const user = userEvent.setup();
    const { onCreateOpenChange } = renderView(true);

    await user.type(screen.getByRole("textbox", { name: "服务备注名" }), "本地面板");
    await user.type(screen.getByRole("textbox", { name: "slug" }), "panel");
    await user.clear(screen.getByRole("spinbutton", { name: "端口" }));
    await user.type(screen.getByRole("spinbutton", { name: "端口" }), "8080");
    expect(screen.queryByRole("textbox", { name: /用户名/ })).toBeNull();
    expect(screen.queryByRole("textbox", { name: /密码/ })).toBeNull();
    expect(screen.queryByText("目标协议")).toBeNull();
    expect(screen.queryByText("这里只设置转发目标")).toBeNull();

    await user.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => {
      expect(api.create).toHaveBeenCalledWith({
        name: "本地面板",
        slug: "panel",
        source: "local",
        port: 8080,
      });
    });
    expect(onCreateOpenChange).toHaveBeenCalledWith(false);
  });

  it("creates a Tailscale forwarding rule from one service URL", async () => {
    const user = userEvent.setup();
    renderView(true);

    await user.type(screen.getByRole("textbox", { name: "服务备注名" }), "家中面板");
    await user.type(
      screen.getByRole("textbox", { name: "slug" }),
      "/model/embedding/v1/",
    );
    await user.selectOptions(screen.getByRole("combobox", { name: "来源" }), "tailscale");

    expect(screen.queryByRole("spinbutton", { name: "端口" })).toBeNull();
    await user.type(
      screen.getByRole("textbox", { name: "Tailscale 服务网址" }),
      "https://lab.tail246500.ts.net/model/embedding/v1",
    );
    await user.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => {
      expect(api.create).toHaveBeenCalledWith({
        name: "家中面板",
        slug: "model/embedding/v1",
        source: "tailscale",
        target_url: "https://lab.tail246500.ts.net/model/embedding/v1",
      });
    });
  });

  it("edits and deletes an existing forwarding rule", async () => {
    const user = userEvent.setup();
    renderView();

    await user.click(await screen.findByRole("button", { name: "编辑" }));
    const port = screen.getByRole("spinbutton", { name: "端口" });
    await user.clear(port);
    await user.type(port, "3100");
    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(api.update).toHaveBeenCalledWith("forward-1", expect.objectContaining({
        name: "代码服务",
        slug: "code",
        port: 3100,
      }));
    });

    await user.click(screen.getByRole("button", { name: "删除" }));
    expect(screen.getByText("删除服务转发？")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "确认删除" }));

    await waitFor(() => expect(api.remove).toHaveBeenCalledWith("forward-1"));
  });
});
