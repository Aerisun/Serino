// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SystemUpdateStatusRead } from "@serino/api-client/models";
import { SystemUpdateNotice } from "../src/pages/dashboard/SystemUpdateNotice";
import { LanguageProvider } from "../src/i18n";

const api = vi.hoisted(() => ({
  status: null as SystemUpdateStatusRead | null,
  checkPending: false,
  checkMutate: vi.fn(),
  upgradeMutate: vi.fn(),
  cancelMutate: vi.fn(),
  refetch: vi.fn(),
}));

vi.mock("@serino/api-client/admin", () => ({
  useUpdateStatusApiV1AdminSystemUpdatesStatusGet: () => ({
    data: api.status ? { data: api.status } : undefined,
    isError: false,
    refetch: api.refetch,
  }),
  useCheckUpdatesApiV1AdminSystemUpdatesCheckPost: (options?: { mutation?: { onSuccess?: () => void } }) => ({
    isPending: api.checkPending,
    mutate: (payload: unknown) => {
      api.checkMutate(payload);
      options?.mutation?.onSuccess?.();
    },
  }),
  useUpgradeSystemApiV1AdminSystemUpdatesUpgradePost: () => ({
    isPending: false,
    mutate: api.upgradeMutate,
  }),
  useCancelQueuedUpdateRequestApiV1AdminSystemUpdatesRequestsRequestIdDelete: () => ({
    isPending: false,
    mutate: api.cancelMutate,
  }),
}));

vi.mock("../src/components/MarkdownPreview", () => ({
  default: ({ content }: { content: string }) => <div>{content}</div>,
}));

function status(overrides: Partial<SystemUpdateStatusRead> = {}): SystemUpdateStatusRead {
  return {
    schema_version: 1,
    state: "idle",
    current_version: "v1.2.3",
    latest_version: null,
    channel: "stable",
    update_available: false,
    auto_update_supported: false,
    signature_verified: false,
    release: null,
    checked_at: "2026-07-05T10:00:00Z",
    recent_log: [],
    ...overrides,
  };
}

function renderNotice() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <LanguageProvider>
        <SystemUpdateNotice />
      </LanguageProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  api.status = null;
  api.checkPending = false;
  api.checkMutate.mockClear();
  api.upgradeMutate.mockClear();
  api.cancelMutate.mockClear();
  api.refetch.mockClear();
  localStorage.clear();
});

afterEach(() => {
  cleanup();
});

describe("SystemUpdateNotice", () => {
  it("shows a higher version even when backend upgrade is unsupported", async () => {
    api.status = status({
      current_version: "v1.2.3",
      latest_version: "v1.2.4",
      update_available: false,
      auto_update_supported: false,
      signature_verified: false,
      release: {
        version: "v1.2.4",
        notes: "## v1.2.4",
        notes_format: "markdown",
      },
    });

    renderNotice();

    await userEvent.click(screen.getByRole("button", { name: "新版本 v1.2.4" }));

    expect(screen.getByRole("button", { name: "检查" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "更新" })).toHaveProperty("disabled", true);
  });

  it("does not show checking state in the topbar", () => {
    api.status = status({
      state: "checking",
      latest_version: null,
      update_available: false,
    });

    renderNotice();

    expect(screen.queryByRole("button", { name: "检查更新中" })).toBeNull();
  });

  it("keeps the confirmed higher version visible while a refresh is checking", async () => {
    api.status = status({
      state: "available",
      current_version: "v1.2.3",
      latest_version: "v1.2.4",
      update_available: true,
    });

    renderNotice();

    expect(screen.getByRole("button", { name: "新版本 v1.2.4" })).toBeTruthy();
    await waitFor(() => {
      expect(localStorage.getItem("serino:system-update-status:v1")).toContain("v1.2.4");
    });

    cleanup();
    api.status = status({
      state: "checking",
      current_version: "v1.2.3",
      latest_version: null,
      update_available: false,
    });

    renderNotice();

    expect(screen.getByRole("button", { name: "新版本 v1.2.4" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "检查更新中" })).toBeNull();
  });

  it("keeps the dialog check button wired to the existing check endpoint", async () => {
    api.status = status({
      current_version: "v1.2.3",
      latest_version: "v1.2.4",
      update_available: true,
      auto_update_supported: false,
      signature_verified: false,
    });

    renderNotice();

    await userEvent.click(screen.getByRole("button", { name: "新版本 v1.2.4" }));
    await userEvent.click(screen.getByRole("button", { name: "检查" }));

    expect(api.checkMutate).toHaveBeenCalledWith({ data: { force: true } });
    expect(api.refetch).toHaveBeenCalled();
  });
});
