// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "../src/i18n";
import { VisitorsUsersPanel } from "../src/pages/visitors/VisitorsUsersPage";

const api = vi.hoisted(() => ({
  deleteVisitor: vi.fn(),
  deleteOptions: null as any,
  users: [
    {
      id: "visitor-1",
      email: "visitor@example.com",
      display_name: "访客一号",
      avatar_url: "https://example.com/avatar.png",
      primary_auth_provider: "google",
      auth_mode: "binding",
      oauth_accounts: [
        {
          provider: "google",
          provider_email: "visitor@example.com",
          provider_display_name: "访客一号",
          created_at: "2026-07-15T21:47:00+08:00",
        },
        {
          provider: "github",
          provider_email: "visitor@example.com",
          provider_display_name: "访客一号",
          created_at: "2026-07-15T21:47:00+08:00",
        },
      ],
      last_login_at: "2026-07-15T21:47:00+08:00",
    },
  ],
}));

vi.mock("@serino/api-client/admin", () => ({
  getListVisitorUsersApiV1AdminVisitorsUsersGetQueryKey: () => ["visitor-users"],
  useListVisitorUsersApiV1AdminVisitorsUsersGet: () => ({
    data: { data: { items: api.users, total: api.users.length } },
    isLoading: false,
  }),
  useDeleteVisitorUserApiV1AdminVisitorsUsersUserIdDelete: (options: any) => {
    api.deleteOptions = options;
    return {
      mutate: api.deleteVisitor,
      isPending: false,
    };
  },
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

function renderVisitorsUsersPanel() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <LanguageProvider>
        <VisitorsUsersPanel />
      </LanguageProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("VisitorsUsersPanel", () => {
  it("keeps the main row to visitor, binding method, and recent login", async () => {
    const user = userEvent.setup();
    renderVisitorsUsersPanel();

    expect(screen.getByRole("columnheader", { name: "访客" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "绑定方式" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "最近登录" })).toBeTruthy();
    expect(screen.queryByRole("columnheader", { name: "邮箱标识" })).toBeNull();
    expect(screen.queryByRole("columnheader", { name: "方式" })).toBeNull();
    expect(screen.queryByRole("columnheader", { name: "绑定" })).toBeNull();
    expect(screen.queryByText("visitor@example.com")).toBeNull();

    const google = screen.getByText("Google");
    const github = screen.getByText("GitHub");
    expect(google.className).toContain("bg-emerald-500");
    expect(github.className).toContain("bg-blue-500");

    const row = screen.getByText("访客一号").closest("tr");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByRole("button", { name: "展开" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "删除用户" })).toBeNull();

    await user.click(within(row as HTMLElement).getByRole("button", { name: "展开" }));
    const expandedRow = screen.getByText("visitor@example.com").closest("tr");
    expect(expandedRow).not.toBeNull();
    const expandedContent = (expandedRow as HTMLElement).querySelector("td > div");
    expect(expandedContent?.className).toContain("md:grid-cols");

    const emailLabel = within(expandedRow as HTMLElement).getByText("邮箱标识：");
    expect(emailLabel.className).toContain("font-semibold");
    expect(emailLabel.className).not.toContain("w-36");

    const emailIdentity = emailLabel.parentElement;
    expect(emailIdentity?.className).toContain("md:col-start-2");

    const deleteButton = within(expandedRow as HTMLElement).getByRole("button", {
      name: "删除用户",
    });
    expect(deleteButton.className).toContain("md:col-start-3");
    expect(deleteButton.className).toContain("bg-destructive");
  });

  it("requires confirmation before deleting a visitor", async () => {
    const user = userEvent.setup();
    api.deleteVisitor.mockImplementation(() => api.deleteOptions.mutation.onSuccess());
    renderVisitorsUsersPanel();

    await user.click(screen.getByRole("button", { name: "展开" }));
    await user.click(screen.getByRole("button", { name: "删除用户" }));
    expect(screen.getByRole("dialog").textContent).toContain(
      "删除该访客会同时删除其评论、留言、附属回复树和订阅，且无法恢复。",
    );

    await user.click(screen.getByRole("button", { name: "删除" }));
    await waitFor(() => {
      expect(api.deleteVisitor).toHaveBeenCalledWith({ userId: "visitor-1" });
    });
  });
});
