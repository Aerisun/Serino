// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ThoughtEditPage from "../src/pages/thoughts/ThoughtEditPage";
import { LanguageProvider } from "../src/i18n";

const api = vi.hoisted(() => ({
  listCategories: vi.fn(() => ({ data: { data: [] }, isLoading: false })),
  thoughtResponse: {
    data: {
      id: "thought-1",
      slug: "current-thought",
      title: "碎碎念一则 (26.4.5.)",
      summary: "",
      body: "当前碎碎念",
      tags: [],
      visibility: "private",
      published_at: "2026-04-05T10:00:00+08:00",
      updated_at: "2026-04-05T10:00:00+08:00",
      category: "历史分类",
      mood: "平静",
    },
  },
}));

vi.mock("@serino/api-client/admin", () => ({
  getListThoughtsQueryKey: () => ["thoughts"],
  getGetThoughtsQueryKey: (id: string) => ["thoughts", id],
  getListContentCategoriesQueryKey: () => ["content-categories"],
  getDefaultContentTitle: vi.fn(),
  useGetDefaultContentTitle: () => ({ data: undefined }),
  useGetThoughts: () => ({ data: api.thoughtResponse }),
  useCreateThoughts: () => ({ mutateAsync: vi.fn() }),
  useUpdateThoughts: () => ({ mutateAsync: vi.fn() }),
  useDeleteThoughts: () => ({ mutate: vi.fn() }),
  useSystemInfoApiV1AdminSystemInfoGet: () => ({ data: { site_url: "https://example.test" } }),
  useListContentCategories: api.listCategories,
  useCreateContentCategory: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("../src/components/MarkdownEditor", () => ({
  MarkdownEditor: ({ value, onChange }: { value: string; onChange: (value: string) => void }) => (
    <textarea aria-label="正文" value={value} onChange={(event) => onChange(event.target.value)} />
  ),
}));

function renderThoughtEditPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <MemoryRouter initialEntries={["/thoughts/thought-1"]} future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
      <QueryClientProvider client={queryClient}>
        <LanguageProvider>
          <Routes>
            <Route path="/thoughts/:id" element={<ThoughtEditPage />} />
            <Route path="/thoughts" element={<div />} />
          </Routes>
        </LanguageProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  localStorage.clear();
});

describe("ThoughtEditPage", () => {
  it("does not render or fetch categories for thoughts", async () => {
    renderThoughtEditPage();

    await waitFor(() => {
      expect(screen.getByText("心情")).toBeTruthy();
    });

    expect(screen.queryByText("分类")).toBeNull();
    expect(api.listCategories).not.toHaveBeenCalled();
  });
});
