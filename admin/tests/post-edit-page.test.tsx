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
      requires_approval: false,
      published_at: "2026-07-01T10:00:00+08:00",
      updated_at: "2026-07-01T10:00:00+08:00",
      category: "Notes",
    },
  },
  systemInfoResponse: { site_url: "https://example.test" },
  profileResponse: { data: { feature_flags: { post_access_approval_enabled: true } } },
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
  useGetProfileApiV1AdminSiteConfigProfileGet: () => ({
    data: api.profileResponse,
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
  api.postResponse.data.requires_approval = false;
  api.postResponse.data.visibility = "private";
  api.profileResponse.data.feature_flags.post_access_approval_enabled = true;
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

  it("shows public-only post settings in the requested order and saves their switch states", async () => {
    const user = userEvent.setup();
    api.updatePost.mockResolvedValue({ data: { id: "post-1" } });
    api.postResponse.data.visibility = "public";
    renderPostEditPage();

    const rssSwitch = screen.getByRole("switch", { name: "不展示 RSS" });
    const approvalSwitch = screen.getByRole("switch", { name: "查看需要审批" });
    expect(rssSwitch.getAttribute("aria-checked")).toBe("false");
    expect(approvalSwitch.getAttribute("aria-checked")).toBe("false");
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
    const approvalControl = approvalSwitch.closest("[data-post-approval-control]");
    expect(rssControl?.compareDocumentPosition(approvalControl!)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    expect(approvalControl?.compareDocumentPosition(publishTimeInput!)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );

    await user.click(rssSwitch);
    await user.click(approvalSwitch);
    await user.click(screen.getByRole("button", { name: "发布" }));

    await waitFor(() => {
      expect(api.updatePost).toHaveBeenCalledWith({
        itemId: "post-1",
        data: expect.objectContaining({ exclude_from_rss: true, requires_approval: true }),
      });
    });
  });

  it("restores the saved public-only post setting switch states", async () => {
    api.postResponse.data.exclude_from_rss = true;
    api.postResponse.data.requires_approval = true;
    api.postResponse.data.visibility = "public";
    renderPostEditPage();

    await waitFor(() => {
      expect(screen.getByRole("switch", { name: "不展示 RSS" }).getAttribute("aria-checked"))
        .toBe("true");
      expect(screen.getByRole("switch", { name: "查看需要审批" }).getAttribute("aria-checked"))
        .toBe("true");
    });
  });

  it("keeps RSS available but hides the per-article approval switch when the global feature is disabled", async () => {
    api.postResponse.data.visibility = "public";
    api.profileResponse.data.feature_flags.post_access_approval_enabled = false;
    renderPostEditPage();

    expect(await screen.findByRole("switch", { name: "不展示 RSS" })).toBeTruthy();
    expect(screen.queryByRole("switch", { name: "查看需要审批" })).toBeNull();
  });

  it("hides RSS and approval switches while the post is private", async () => {
    renderPostEditPage();

    await waitFor(() => {
      expect(screen.queryByRole("switch", { name: "不展示 RSS" })).toBeNull();
      expect(screen.queryByRole("switch", { name: "查看需要审批" })).toBeNull();
    });
  });
});
