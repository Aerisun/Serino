// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import PostEditPage from "../src/pages/posts/PostEditPage";
import { LanguageProvider } from "../src/i18n";
import { readEditorDraftSnapshot, saveEditorDraftSnapshot } from "../src/lib/content-editor";

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
      exclude_from_rss: false,
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
  api.postResponse.data.exclude_from_rss = false;
});

describe("PostEditPage", () => {
  it("restores the matching local draft after an unexpected exit", async () => {
    saveEditorDraftSnapshot({
      contentType: "posts",
      draftId: "post-1",
      form: {
        ...api.postResponse.data,
        slug: "recovered-slug",
        body: "Recovered body",
      },
      isPublishedAtManual: false,
      isAutoTitleEnabled: false,
      sourceUpdatedAt: api.postResponse.data.updated_at,
    });

    renderPostEditPage();

    await waitFor(() => {
      expect((screen.getByLabelText("Slug") as HTMLInputElement).value).toBe("recovered-slug");
    });
    expect((screen.getByLabelText("正文") as HTMLTextAreaElement).value).toBe("Recovered body");
  });

  it("keeps the server content when a cached draft belongs to an older server version", async () => {
    saveEditorDraftSnapshot({
      contentType: "posts",
      draftId: "post-1",
      form: {
        ...api.postResponse.data,
        slug: "stale-local-slug",
      },
      isPublishedAtManual: false,
      isAutoTitleEnabled: false,
      sourceUpdatedAt: "2026-07-01T09:00:00+08:00",
    });

    renderPostEditPage();

    await waitFor(() => {
      expect((screen.getByLabelText("Slug") as HTMLInputElement).value).toBe("current-slug");
    });
  });

  it("keeps a draft on page exit and clears it only after a successful save", async () => {
    const user = userEvent.setup();
    api.updatePost.mockResolvedValue({ data: { id: "post-1" } });
    renderPostEditPage();

    const slugInput = screen.getByLabelText("Slug") as HTMLInputElement;
    await user.clear(slugInput);
    await user.type(slugInput, "exit-safe-slug");
    window.dispatchEvent(new Event("pagehide"));

    expect(readEditorDraftSnapshot("posts", "post-1", api.postResponse.data.updated_at))
      .toMatchObject({ form: { slug: "exit-safe-slug" } });

    await user.click(screen.getByRole("button", { name: "保存私密" }));

    await waitFor(() => {
      expect(readEditorDraftSnapshot("posts", "post-1", api.postResponse.data.updated_at))
        .toBeNull();
    });
  });

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

  it("lets editors exclude a post from RSS and saves the switch state", async () => {
    const user = userEvent.setup();
    api.updatePost.mockResolvedValue({ data: { id: "post-1" } });
    renderPostEditPage();

    const rssSwitch = screen.getByRole("switch", { name: "不展示 RSS" });
    expect(rssSwitch.getAttribute("aria-checked")).toBe("false");
    expect(rssSwitch.closest("[data-rss-exclusion-control]")?.className).toContain("max-md:basis-full");

    const rssControl = rssSwitch.closest("[data-rss-exclusion-control]");
    expect(within(rssControl!).getByText("不展示 RSS")).toBeTruthy();
    await user.click(within(rssControl!).getByRole("button", { name: "查看字段说明" }));
    expect((await screen.findByRole("dialog")).textContent).toContain(
      "公开文章仍可在网站中访问，但不会出现在 RSS 订阅中。",
    );

    const publishTimeInput = document.querySelector("[data-publish-time-input]");
    expect(rssControl?.compareDocumentPosition(publishTimeInput!)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );

    await user.click(rssSwitch);
    await user.click(screen.getByRole("button", { name: "保存私密" }));

    await waitFor(() => {
      expect(api.updatePost).toHaveBeenCalledWith({
        itemId: "post-1",
        data: expect.objectContaining({ exclude_from_rss: true }),
      });
    });
  });

  it("restores the saved RSS exclusion switch state", async () => {
    api.postResponse.data.exclude_from_rss = true;
    renderPostEditPage();

    await waitFor(() => {
      expect(screen.getByRole("switch", { name: "不展示 RSS" }).getAttribute("aria-checked"))
        .toBe("true");
    });
  });
});
