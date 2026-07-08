// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import AssetsPage from "../src/pages/assets/AssetsPage";
import { LanguageProvider } from "../src/i18n";

const api = vi.hoisted(() => ({
  assets: [
    {
      id: "asset-1",
      file_name: "asset-file.webp",
      resource_key: "internal/assets/site/abcdef123456.webp",
      public_slug: "hero-cover.webp",
      visibility: "public",
      scope: "user",
      category: "site",
      note: "首页封面",
      storage_path: "/tmp/asset-file.webp",
      internal_url: "/media/internal/assets/site/abcdef123456.webp",
      public_url: "https://site.example/media/hero-cover.webp",
      mime_type: "image/webp",
      byte_size: 1024,
      sha256: "abcdef",
      storage_provider: "local",
      remote_status: "none",
      mirror_status: "completed",
      mirror_last_error: null,
      oss_acceleration_enabled_at_upload: false,
      created_at: "2026-07-06T00:18:00+08:00",
      updated_at: "2026-07-06T00:18:00+08:00",
    },
  ] as any[],
  deleteMutate: vi.fn(),
  updateMutateAsync: vi.fn(),
  invalidateQueries: vi.fn(),
  clipboardWrite: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@serino/api-client/admin", () => ({
  getListAssetsEndpointApiV1AdminAssetsGetQueryKey: () => ["assets"],
  useListAssetsEndpointApiV1AdminAssetsGet: () => ({
    data: {
      data: {
        items: api.assets,
        total: api.assets.length,
        page: 1,
        page_size: 20,
      },
    },
    isLoading: false,
  }),
  useDeleteAssetEndpointApiV1AdminAssetsAssetIdDelete: () => ({
    mutate: api.deleteMutate,
    isPending: false,
  }),
  useUpdateAssetEndpointApiV1AdminAssetsAssetIdPatch: () => ({
    mutateAsync: api.updateMutateAsync,
    isPending: false,
  }),
}));

vi.mock("@/pages/more/objectStorageApi", () => ({
  getObjectStorageConfig: () =>
    Promise.resolve({
      enabled: false,
      last_health_ok: false,
    }),
  listObjectStorageSyncRecords: () =>
    Promise.resolve({
      items: [],
      total: 0,
      page_size: 20,
    }),
}));

vi.mock("@/lib/managedAssetUpload", () => ({
  uploadManagedAsset: vi.fn(),
}));

vi.mock("@tanstack/react-query", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-query")>("@tanstack/react-query");
  return {
    ...actual,
    useQueryClient: () => ({
      invalidateQueries: api.invalidateQueries,
    }),
  };
});

vi.mock("sonner", () => ({
  toast: {
    success: api.toastSuccess,
    error: api.toastError,
  },
}));

function renderAssetsPage() {
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
          <AssetsPage />
        </LanguageProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

function expectCategoryAndSlugShareTwoColumnRow(dialog: HTMLElement) {
  const categoryLabel = within(dialog).getByText("分类");
  const slugLabel = within(dialog).getByText("公开 slug");
  const categoryBlock = categoryLabel.closest("div");
  const slugBlock = slugLabel.closest("div");
  const row = categoryBlock?.parentElement;

  expect(categoryBlock).not.toBeNull();
  expect(slugBlock).not.toBeNull();
  expect(row?.contains(slugBlock)).toBe(true);
  expect(row?.className).toContain("sm:grid-cols-2");
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: async () => undefined },
  });
  window.open = vi.fn();
  window.confirm = vi.fn();
  api.updateMutateAsync.mockResolvedValue({ data: api.assets[0] });
  api.clipboardWrite = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);
});

afterEach(() => {
  cleanup();
});

describe("AssetsPage public slug", () => {
  it("keeps category and slug in the same two-column row for upload and edit dialogs", async () => {
    const user = userEvent.setup();
    renderAssetsPage();

    await user.click(screen.getByRole("button", { name: /上传/ }));
    expectCategoryAndSlugShareTwoColumnRow(screen.getByRole("dialog"));

    await user.keyboard("{Escape}");
    await user.click(screen.getByTitle("编辑"));
    expectCategoryAndSlugShareTwoColumnRow(screen.getByRole("dialog"));
  });

  it("shows the public slug in a three-column expanded details grid", async () => {
    const user = userEvent.setup();
    renderAssetsPage();

    await user.click(screen.getByRole("button", { name: "展开" }));

    const slugValue = screen.getByText("hero-cover.webp");
    const expandedGrid = slugValue.closest("div.grid");
    expect(screen.getByText("公开 slug")).not.toBeNull();
    expect(expandedGrid?.className).toContain("sm:grid-cols-3");
  });

  it("copies the backend-provided public slug URL", async () => {
    renderAssetsPage();

    screen.getByTitle("复制外部链接").click();

    await waitFor(() => {
      expect(api.clipboardWrite).toHaveBeenCalledWith("https://site.example/media/hero-cover.webp");
    });
  });
});
