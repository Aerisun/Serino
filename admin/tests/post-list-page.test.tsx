// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import PostListPage from "../src/pages/posts/PostListPage";
import { LanguageProvider } from "../src/i18n";

const api = vi.hoisted(() => ({
  listResponse: {
    data: {
      items: [
        {
          id: "post-rss-excluded",
          slug: "post-rss-excluded",
          title: "不会出现在 RSS 的公开文章",
          summary: "",
          body: "文章正文",
          tags: [],
          visibility: "public",
          kind: "note",
          exclude_from_rss: true,
          published_at: "2026-07-28T10:00:00+08:00",
          created_at: "2026-07-28T10:00:00+08:00",
          updated_at: "2026-07-28T10:00:00+08:00",
        },
        {
          id: "post-approval",
          slug: "post-approval",
          title: "需要审批的公开文章",
          summary: "",
          body: "文章正文",
          tags: [],
          visibility: "public",
          kind: "manuscript",
          exclude_from_rss: false,
          requires_approval: true,
          published_at: "2026-07-29T10:00:00+08:00",
          created_at: "2026-07-29T10:00:00+08:00",
          updated_at: "2026-07-29T10:00:00+08:00",
        },
        {
          id: "post-approval-no-rss",
          slug: "post-approval-no-rss",
          title: "需要审批且不展示 RSS 的公开文章",
          summary: "",
          body: "文章正文",
          tags: [],
          visibility: "public",
          kind: "manuscript",
          exclude_from_rss: true,
          requires_approval: true,
          published_at: "2026-07-30T10:00:00+08:00",
          created_at: "2026-07-30T10:00:00+08:00",
          updated_at: "2026-07-30T10:00:00+08:00",
        },
      ],
      total: 1,
      page_size: 20,
    },
  },
}));

vi.mock("@serino/api-client/admin", () => ({
  getListPostsQueryKey: () => ["posts"],
  useListPosts: () => ({ data: api.listResponse, isLoading: false }),
  useBulkDeletePosts: () => ({
    mutateAsync: vi.fn().mockResolvedValue({ data: { affected: 0 } }),
    isPending: false,
  }),
  useBulkVisibilityPosts: () => ({
    mutateAsync: vi.fn().mockResolvedValue({ data: { affected: 0 } }),
    isPending: false,
  }),
}));

function renderPostListPage() {
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
          <PostListPage />
        </LanguageProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PostListPage", () => {
  it("shows approval states in the visibility column and keeps RSS state distinguishable", () => {
    renderPostListPage();

    expect(screen.getAllByText("公开 (不RSS)")).toHaveLength(2);
    const badges = screen.getAllByText("公开 (不RSS)");
    expect(badges.every((badge) => badge.className.includes("bg-green-100")))
      .toBe(true);
    const desktopBadge = badges.find((badge) => badge.closest("td"));
    expect(desktopBadge).toBeDefined();
    expect(desktopBadge?.closest("td")?.className).toContain("text-center");
    expect(screen.getAllByText("审批")).toHaveLength(2);
    const approvalBadges = [
      ...screen.getAllByText("审批"),
      ...screen.getAllByText("审批 (不RSS)"),
    ];
    expect(approvalBadges).toHaveLength(4);
    expect(approvalBadges.every((badge) => badge.className.includes("bg-violet-100"))).toBe(true);
  });

  it("shows the post kind as its own list column", () => {
    renderPostListPage();

    expect(screen.getByRole("columnheader", { name: "类别" })).toBeTruthy();
    const notes = screen.getAllByText("手记");
    const manuscripts = screen.getAllByText("文稿");
    expect(notes.length).toBeGreaterThan(0);
    expect(manuscripts.length).toBeGreaterThan(0);
    expect(notes.every((note) => note.className.includes("text-pink-400"))).toBe(true);
    expect(manuscripts.every((manuscript) => manuscript.className.includes("text-cyan-600"))).toBe(true);
  });
});
