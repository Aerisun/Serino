// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import PostEditPage from "../src/pages/posts/PostEditPage";
import { LanguageProvider } from "../src/i18n";

const api = vi.hoisted(() => ({
  updatePost: vi.fn(),
  categoriesResponse: { data: [] },
  postResponse: {
    data: {
      id: "post-1",
      slug: "current-slug",
      title: "Current Title",
      summary: "Current summary",
      body: "Current body",
      tags: ["design"],
      visibility: "private",
      published_at: "2026-07-01T10:00:00+08:00",
      updated_at: "2026-07-01T10:00:00+08:00",
      category: "Notes",
    },
  },
  systemInfoResponse: { site_url: "https://example.test" },
}));

vi.mock("@serino/api-client/admin", () => ({
  getListPostsQueryKey: () => ["posts"],
  getGetPostsQueryKey: (id: string) => ["posts", id],
  getListContentCategoriesQueryKey: () => ["content-categories"],
  useListContentCategories: () => ({
    data: api.categoriesResponse,
    isLoading: false,
  }),
  useCreateContentCategory: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useGetDefaultContentTitle: () => ({ data: undefined }),
  getDefaultContentTitle: vi.fn(),
  useSystemInfoApiV1AdminSystemInfoGet: () => ({
    data: api.systemInfoResponse,
  }),
  useGetPosts: () => ({
    data: api.postResponse,
  }),
  useCreatePosts: () => ({
    mutateAsync: vi.fn(),
  }),
  useUpdatePosts: () => ({
    mutateAsync: api.updatePost,
  }),
  useDeletePosts: () => ({
    mutate: vi.fn(),
  }),
}));

vi.mock("../src/components/MarkdownEditor", () => ({
  MarkdownEditor: ({ value, onChange }: { value: string; onChange: (value: string) => void }) => (
    <textarea aria-label="正文" value={value} onChange={(event) => onChange(event.target.value)} />
  ),
}));

function renderPostEditPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <MemoryRouter
      initialEntries={["/posts/post-1"]}
      future={{ v7_relativeSplatPath: true, v7_startTransition: true }}
    >
      <QueryClientProvider client={queryClient}>
        <LanguageProvider>
          <Routes>
            <Route path="/posts/:id" element={<PostEditPage />} />
            <Route path="/posts" element={<div />} />
          </Routes>
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

describe("PostEditPage", () => {
  it("lets editors change the post slug and saves it with the article payload", async () => {
    api.updatePost.mockResolvedValue({ data: { id: "post-1" } });
    renderPostEditPage();

    const slugInput = screen.getByLabelText("Slug") as HTMLInputElement;
    expect(slugInput.value).toBe("current-slug");

    await userEvent.clear(slugInput);
    await userEvent.type(slugInput, "renamed-slug");
    await userEvent.click(screen.getByRole("button", { name: "保存私密" }));

    await waitFor(() => {
      expect(api.updatePost).toHaveBeenCalledWith({
        itemId: "post-1",
        data: expect.objectContaining({
          slug: "renamed-slug",
          title: "Current Title",
        }),
      });
    });
  });
});
