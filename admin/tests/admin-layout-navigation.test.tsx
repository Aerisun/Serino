// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import AdminLayout from "../src/layouts/AdminLayout";
import { AuthContext } from "../src/auth/AuthProvider";
import { LanguageProvider } from "../src/i18n";

vi.mock("@serino/theme", () => ({
  useTheme: () => ({
    theme: "light",
    resolvedTheme: "light",
    setTheme: vi.fn(),
  }),
}));

vi.mock("../src/pages/moderation/moderationQueries", () => ({
  moderationAttentionCountQueryOptions: () => ({
    queryKey: ["moderation", "attention-counts"],
    queryFn: () =>
      Promise.resolve({
        comments: { pending: 0, unread: 0 },
        guestbook: { pending: 0, unread: 0 },
        diary_access: { pending: 0 },
        pending_total: 0,
        unread_total: 0,
      }),
    staleTime: 60_000,
  }),
}));

vi.mock("../src/pages/dashboard/SystemUpdateNotice", () => ({
  SystemUpdateNotice: () => <button type="button">新版本 v0.1.62</button>,
}));

function renderLayout() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <MemoryRouter
      initialEntries={["/"]}
      future={{ v7_relativeSplatPath: true, v7_startTransition: true }}
    >
      <QueryClientProvider client={queryClient}>
        <LanguageProvider>
          <AuthContext.Provider
            value={{
              user: { id: "admin-1", username: "admin" } as any,
              isLoading: false,
              isAuthenticated: true,
              login: vi.fn(),
              loginWithAdminEmail: vi.fn(),
              exchangeSiteUserLogin: vi.fn(),
              logout: vi.fn(),
            }}
          >
            <Routes>
              <Route element={<AdminLayout />}>
                <Route path="/" element={<div />} />
              </Route>
            </Routes>
          </AuthContext.Provider>
        </LanguageProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  window.scrollTo = vi.fn();
  HTMLElement.prototype.scrollTo = vi.fn();
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.clearAllMocks();
});

describe("AdminLayout navigation", () => {
  it("shows backups as the fourth item under management", () => {
    renderLayout();

    const mobileNav = screen.getAllByRole("navigation")[0];
    const managementGroup = within(mobileNav).getByText("管理").parentElement;
    const managementLinks = within(managementGroup as HTMLElement)
      .getAllByRole("link")
      .map((link) => link.textContent?.trim());

    expect(managementLinks).toEqual(["审核", "访客", "资源", "备份"]);
  });

  it("shows update notice in the topbar next to the admin panel title", () => {
    renderLayout();

    const title = screen.getByText("Serino 管理面板");
    const topbar = title.closest(".admin-glass-topbar");
    const updateButton = screen.getByRole("button", { name: "新版本 v0.1.62" });

    expect(topbar).not.toBeNull();
    expect(topbar?.contains(updateButton)).toBe(true);
  });
});
