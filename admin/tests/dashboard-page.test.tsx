// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import DashboardPage from "../src/pages/DashboardPage";
import { LanguageProvider } from "../src/i18n";

const api = vi.hoisted(() => ({
  state: {
    backupEnabled: true,
    unreadTotal: 0,
    commits: [
      {
        id: "commit-1",
        transport: "sftp",
        trigger_kind: "manual",
        site_slug: "aerisun",
        remote_commit_id: "remote-commit-1",
        manifest_digest: "manifest-digest",
        backup_path: "/srv/serino-backups/current/commits/commit-1/manifest.json",
        datasets: {},
        stats_json: {},
        snapshot_started_at: "2026-07-02T00:00:00+08:00",
        snapshot_finished_at: "2026-07-02T00:01:00+08:00",
        restored_at: null,
        created_at: "2026-07-02T00:00:00+08:00",
        updated_at: "2026-07-02T00:01:00+08:00",
      },
    ] as any[],
  },
  adminApiRequest: vi.fn(),
}));

vi.mock("@serino/api-client/admin", () => ({
  useGetBackupSyncConfigApiV1AdminSystemBackupSyncConfigGet: () => ({
    data: { data: { enabled: api.state.backupEnabled } },
    isLoading: false,
  }),
  useListBackupSyncCommitsApiV1AdminSystemBackupSyncCommitsGet: () => ({
    data: { data: api.state.commits },
    isLoading: false,
  }),
}));

vi.mock("@/lib/adminApi", () => ({
  adminApiRequest: (...args: unknown[]) => api.adminApiRequest(...args),
}));

vi.mock("../src/pages/moderation/moderationQueries", () => ({
  moderationAttentionCountQueryOptions: () => ({
    queryKey: ["moderation", "attention-counts"],
    queryFn: () => Promise.resolve({ unread_total: api.state.unreadTotal }),
  }),
}));

function dashboardStats() {
  return {
    posts: 1,
    diary_entries: 2,
    thoughts: 3,
    excerpts: 4,
    comments: 0,
    guestbook_entries: 0,
    friends: 1,
    assets: 1,
    posts_by_visibility: {},
    content_by_month: [],
    recent_content: [],
    traffic: {
      total_views: 0,
      top_pages: [],
      distribution: [],
      history: [],
      last_snapshot_at: null,
    },
    visitors: {
      total_visits: 0,
      unique_visitors_24h: 0,
      unique_visitors_7d: 0,
      average_request_duration_ms: 0,
      top_pages: [],
      history: [],
      recent_visits: [],
      last_visit_at: null,
    },
    aux_metrics: {
      pending_moderation: 0,
      published_posts: 1,
      published_diary_entries: 2,
      published_thoughts: 3,
      published_excerpts: 4,
    },
  };
}

function renderPage() {
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
          <DashboardPage />
        </LanguageProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  api.state.backupEnabled = true;
  api.state.unreadTotal = 0;
  api.state.commits = [api.state.commits[0]];
  api.adminApiRequest.mockResolvedValue(dashboardStats());
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("DashboardPage backup summary", () => {
  it("shows unread moderation activity instead of pending-review activity", async () => {
    api.state.unreadTotal = 3;
    renderPage();

    expect(await screen.findByText("未读内容")).toBeTruthy();
    expect(screen.getByText("建议尽快查看，避免遗漏")).toBeTruthy();
    expect(screen.queryByText("待审核")).toBeNull();
  });

  it("shows the latest backup time when backup sync is enabled", async () => {
    renderPage();

    const backupSummary = await screen.findByText(/最近一次备份/);

    expect(backupSummary.textContent).toContain("Jul 2");
    expect(screen.queryByText(/最近快照/)).toBeNull();
  });

  it("hides the backup summary when backup sync is disabled", async () => {
    api.state.backupEnabled = false;

    renderPage();

    await waitFor(() => expect(api.adminApiRequest).toHaveBeenCalled());

    expect(screen.queryByText(/最近一次备份/)).toBeNull();
    expect(screen.queryByText(/最近快照/)).toBeNull();
  });
});
