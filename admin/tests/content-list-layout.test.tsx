// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import ContentListPage from "../src/pages/common/ContentListPage";
import type { ContentListConfig } from "../src/pages/common/types";
import { LanguageProvider } from "../src/i18n";

const emptyListResponse = {
  data: {
    items: [],
    total: 0,
    page_size: 20,
  },
};

function createConfig(): ContentListConfig {
  return {
    resourceKey: "posts",
    titleKey: "posts.title",
    descriptionKey: "posts.description",
    newButtonLabelKey: "posts.newPost",
    newPath: "/posts/new",
    editPath: (id) => `/posts/${id}`,
    columns: [{ header: "标题", accessor: "title" }],
    useList: () => ({ data: emptyListResponse, isLoading: false }),
    useBulkDelete: () => ({
      mutateAsync: vi.fn().mockResolvedValue({ data: { affected: 0 } }),
      isPending: false,
    }),
    useBulkVisibility: () => ({
      mutateAsync: vi.fn().mockResolvedValue({ data: { affected: 0 } }),
      isPending: false,
    }),
    getQueryKey: () => ["posts"],
  };
}

function renderContentList() {
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
          <ContentListPage config={createConfig()} />
        </LanguageProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  localStorage.clear();
});

describe("ContentListPage layout", () => {
  it("keeps desktop search in the same filter row before the all button", () => {
    renderContentList();

    const toolbar = screen.getByRole("toolbar", { name: "内容筛选和排序" });
    const search = within(toolbar).getByPlaceholderText("搜索标题、内容...");
    const allButton = within(toolbar).getByRole("button", { name: "全部" });

    expect(toolbar.contains(search)).toBe(true);
    expect(toolbar.contains(allButton)).toBe(true);
    expect(search.className).toContain("md:w-72");
    expect(search.className).not.toContain("36vw");
    expect(
      search.compareDocumentPosition(allButton) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("keeps the sort select compact beside the filters", () => {
    renderContentList();

    const toolbar = screen.getByRole("toolbar", { name: "内容筛选和排序" });
    const sortSelect = within(toolbar).getByRole("combobox", { name: "排序" });
    const sortContainer = sortSelect.closest("div");

    expect(sortContainer?.className).toContain("md:w-48");
  });

  it("keeps the mobile title and create action in one header row", () => {
    renderContentList();

    const heading = screen.getByRole("heading", { name: "文章", level: 1 });
    const newButton = screen.getByRole("button", { name: /新建文章/ });
    const headerRow = heading.closest("div")?.parentElement;

    expect(headerRow?.contains(newButton)).toBe(true);
    expect(headerRow?.className).toContain("justify-between");
    expect(headerRow?.className).not.toContain("flex-col");
  });
});
