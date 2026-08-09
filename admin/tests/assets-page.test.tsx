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
      resource_key: "assets/asset-1.webp",
      public_slug: "hero-cover.webp",
      visibility: "public",
      scope: "user",
      category: "site",
      note: "首页封面",
      storage_path: "/tmp/media/assets/user/asset-1.webp",
      internal_url: "/media/assets/asset-1.webp",
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
  listAssetsHook: vi.fn(),
  syncRecords: [] as any[],
  retrySyncRecord: vi.fn(),
}));

vi.mock("@serino/api-client/admin", () => ({
  getListAssetsEndpointApiV1AdminAssetsGetQueryKey: () => ["assets"],
  useListAssetsEndpointApiV1AdminAssetsGet: (...args: unknown[]) => {
    api.listAssetsHook(...args);
    return {
      data: {
        data: {
          items: api.assets,
          total: api.assets.length,
          page: 1,
          page_size: 20,
        },
      },
      isLoading: false,
    };
  },
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
      items: api.syncRecords,
      total: api.syncRecords.length,
      page_size: 20,
    }),
  retryObjectStorageSyncRecord: (...args: unknown[]) => api.retrySyncRecord(...args),
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

function renderAssetsPage(initialEntry = "/assets") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <MemoryRouter
      initialEntries={[initialEntry]}
      future={{ v7_relativeSplatPath: true, v7_startTransition: true }}
    >
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
  api.syncRecords = [];
  api.retrySyncRecord.mockResolvedValue({ status: "retrying" });
  api.clipboardWrite = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);
  api.assets[0].file_name = "asset-file.webp";
  api.assets[0].note = "首页封面";
  api.assets[0].category = "site";
  api.assets[0].scope = "user";
  api.assets[0].visibility = "public";
  api.assets[0].public_url = "https://site.example/media/hero-cover.webp";
});

afterEach(() => {
  cleanup();
});

describe("AssetsPage public slug", () => {
  it("opens the OSS sync view from a diagnostic deep link", () => {
    renderAssetsPage("/assets?view=oss_sync");

    expect(screen.getByRole("button", { name: "OSS 同步记录" }).getAttribute("aria-pressed")).toBe("true");
    expect(api.listAssetsHook.mock.calls[0]?.[1]?.query?.enabled).toBe(false);
  });

  it("queues a failed OSS sync record for retry from the diagnostic destination", async () => {
    api.syncRecords = [
      {
        id: "failed-local-delete",
        record_type: "local_delete",
        status: "failed",
        object_key: "/data/media/obsolete.png",
        retry_count: 3,
        last_error: "permission denied",
        created_at: "2026-08-09T04:20:00+08:00",
        updated_at: "2026-08-09T04:21:00+08:00",
      },
    ];
    const user = userEvent.setup();
    renderAssetsPage("/assets?view=oss_sync");

    await user.click(await screen.findByRole("button", { name: "重试" }));

    await waitFor(() => {
      expect(api.retrySyncRecord).toHaveBeenCalledWith("local_delete", "failed-local-delete");
    });
    expect(api.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["admin", "object-storage-sync-records"],
    });
    expect(api.toastSuccess).toHaveBeenCalledWith("已加入重试队列");
  });

  it("shows the four resource folders with user resources selected first", () => {
    renderAssetsPage();

    expect(screen.getByRole("button", { name: "用户资源" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "文章资源" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "访客资源" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "系统资源" })).toBeTruthy();
  });

  it("keeps compact columns stable when a resource has a long filename", () => {
    const longFileName = "科研_申请经验分享_qty_【P-Talk-3】_补充材料与完整附件版本.pdf";
    const longNote = "这是一条需要展示两行的较长资源备注，用于验证超出内容会被稳定收起。";
    api.assets[0].file_name = longFileName;
    api.assets[0].note = longNote;

    renderAssetsPage();

    const table = screen.getByRole("table");
    expect(table.className).toContain("table-fixed");
    expect(table.className).toContain("min-w-[59rem]");

    const fileNameElement = screen.getByText(longFileName);
    expect(fileNameElement.getAttribute("title")).toBe(longFileName);
    expect(fileNameElement.className).toContain("truncate");
    expect(fileNameElement.className).not.toContain("flex-1");
    expect(fileNameElement.parentElement?.className).toContain("gap-1.5");
    expect(fileNameElement.closest("td")?.className).toContain("min-w-[12rem]");
    expect(screen.getByRole("columnheader", { name: "备注" }).className).toContain("min-w-[10rem]");

    const noteElement = screen.getByText(longNote);
    expect(noteElement.getAttribute("title")).toBe(longNote);
    expect(noteElement.className).toContain("line-clamp-2");
    expect(noteElement.className).toContain("text-[13px]");
    expect(noteElement.className).toContain("leading-5");
    expect(noteElement.className).not.toContain("truncate");

    expect(screen.getByRole("columnheader", { name: "文件名" }).className).not.toContain("text-center");
    expect(screen.getByRole("columnheader", { name: "备注" }).className).not.toContain("text-center");
    expect(screen.getByRole("columnheader", { name: "分类" }).className).toContain("text-center");

    const firstRow = fileNameElement.closest("tr");
    expect(firstRow).not.toBeNull();
    const firstRowCells = within(firstRow as HTMLElement).getAllByRole("cell");
    expect(firstRowCells[1].className).not.toContain("text-center");
    expect(firstRowCells[2].className).not.toContain("text-center");
    expect(firstRowCells[3].className).toContain("text-center");

    for (const [header, minWidth] of [
      ["分类", "min-w-[8rem]"],
      ["资源范围", "min-w-[5.25rem]"],
      ["可见性", "min-w-[4.75rem]"],
      ["文件大小", "min-w-[5.5rem]"],
      ["链接", "min-w-[4.75rem]"],
    ]) {
      const headerCell = screen.getByRole("columnheader", { name: header });
      expect(headerCell.className).toContain(minWidth);
      expect(headerCell.className).toContain("whitespace-nowrap");
    }

    const linkHeader = screen.getByRole("columnheader", { name: "链接" });
    const actionHeader = screen.getByRole("columnheader", { name: "操作" });
    expect(linkHeader.className).toContain("text-center");
    expect(actionHeader.className).toContain("min-w-[4.75rem]");
    expect(actionHeader.className).toContain("text-center");

    const linkControls = screen.getByTitle("复制内部链接").parentElement;
    const actionControls = screen.getByTitle("编辑").parentElement;
    expect(linkControls?.className).toContain("justify-center");
    expect(actionControls?.className).toContain("justify-center");
  });

  it("centers the empty note placeholder while keeping note content left-aligned", () => {
    api.assets[0].note = "";

    renderAssetsPage();

    const resourceRow = screen.getByText("asset-file.webp").closest("tr");
    expect(resourceRow).not.toBeNull();
    expect(within(resourceRow as HTMLElement).getByText("-").className).toContain("text-center");
  });

  it("opens a public file directly in a new tab with the external-link icon", async () => {
    const user = userEvent.setup();
    renderAssetsPage();

    const previewButton = screen.getByTitle("查看");
    expect(previewButton.querySelector(".lucide-external-link")).not.toBeNull();
    await user.click(previewButton);

    expect(window.open).toHaveBeenCalledWith(
      "/media/assets/asset-1.webp",
      "_blank",
      "noopener,noreferrer",
    );
  });

  it("opens an internal file through the protected redirect route", async () => {
    api.assets[0].visibility = "internal";
    api.assets[0].public_url = null;
    const user = userEvent.setup();
    renderAssetsPage();

    await user.click(screen.getByTitle("查看"));

    expect(window.open).toHaveBeenCalledWith(
      "/assets/preview/asset-1",
      "_blank",
      "noopener,noreferrer",
    );
  });

  it("truncates a long selected upload filename and exposes the full name on hover", async () => {
    const user = userEvent.setup();
    renderAssetsPage();

    await user.click(screen.getByRole("button", { name: /上传/ }));

    const dialog = screen.getByRole("dialog");
    const fileInput = dialog.querySelector<HTMLInputElement>('input[type="file"]');
    if (!fileInput) throw new Error("Expected the upload dialog to include a file input");

    const fileName = "a-very-long-upload-filename-that-must-not-resize-the-dialog.png";
    await user.upload(fileInput, new File(["image"], fileName, { type: "image/png" }));

    const fileNameElement = within(dialog).getByText(fileName);
    expect(fileNameElement.getAttribute("title")).toBe(fileName);
    expect(fileNameElement.className).toContain("truncate");
    expect(fileNameElement.parentElement?.className).toContain("min-w-0");
  });

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
