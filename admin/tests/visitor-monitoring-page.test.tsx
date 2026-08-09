// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { LanguageProvider } from "../src/i18n";
import VisitorMonitoringPage from "../src/pages/visitors/VisitorMonitoringPage";

const api = vi.hoisted(() => {
  const newestRecord = {
    id: "visit-new",
    visited_at: "2026-08-09T10:00:00+08:00",
    path: "/posts/one",
    ip_address: "198.51.100.10",
    location: "Shanghai",
    status_code: 200,
    status_text: "OK",
    duration_ms: 12,
    is_bot: false,
  };
  const oldestRecord = {
    ...newestRecord,
    id: "visit-old",
    visited_at: "2026-08-09T09:59:00+08:00",
    path: "/posts/two",
  };
  const groupResponse = {
    data: {
      items: [
        {
          id: "visit-new:visit-old",
          ip_address: "198.51.100.10",
          record_count: 2,
          newest_record: newestRecord,
          oldest_record: oldestRecord,
          newest_visited_at: newestRecord.visited_at,
          oldest_visited_at: oldestRecord.visited_at,
        },
      ],
      total: 41,
      page: 1,
      page_size: 20,
    },
  };

  return {
    detailParams: [] as Array<Record<string, unknown>>,
    groupParams: [] as Array<Record<string, unknown>>,
    prefetchParams: [] as Array<Record<string, unknown>>,
    groupResponse,
    refetchGroups: vi.fn(),
  };
});

vi.mock("@serino/api-client/admin", () => ({
  getVisitorRecordGroupsApiV1AdminSystemVisitorRecordGroupsGetQueryOptions: (
    params: Record<string, unknown>,
  ) => {
    api.prefetchParams.push(params);
    return {
      queryKey: ["visitor-record-groups", params],
      queryFn: async () => api.groupResponse,
    };
  },
  useSystemInfoApiV1AdminSystemInfoGet: () => ({
    data: { data: { site_url: "https://example.com" } },
  }),
  useVisitorRecordGroupsApiV1AdminSystemVisitorRecordGroupsGet: (
    params: Record<string, unknown>,
  ) => {
    api.groupParams.push(params);
    return {
      data: api.groupResponse,
      isFetching: false,
      isLoading: false,
      refetch: api.refetchGroups,
    };
  },
  useVisitorRecordGroupRecordsApiV1AdminSystemVisitorRecordGroupsNewestRecordIdOldestRecordIdRecordsGet: (
    _newestRecordId: string,
    _oldestRecordId: string,
    params: Record<string, unknown>,
  ) => {
    api.detailParams.push(params);
    return {
      data: {
        data: {
          items: api.groupResponse.data.items.flatMap((group) => [
            group.newest_record,
            group.oldest_record,
          ]),
          total: 41,
          page: 1,
          page_size: 20,
        },
      },
      isLoading: false,
    };
  },
}));

vi.mock("../src/pages/dashboard/dashboardQueries", () => ({
  dashboardStatsQueryOptions: () => ({
    queryKey: ["dashboard-stats", "summary"],
    queryFn: async () => ({
      visitors: {
        total_visits: 88,
        unique_visitors_24h: 12,
        unique_visitors_7d: 34,
        average_request_duration_ms: 56,
      },
    }),
  }),
}));

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
          <VisitorMonitoringPage />
        </LanguageProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  api.detailParams.length = 0;
  api.groupParams.length = 0;
  api.prefetchParams.length = 0;
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("VisitorMonitoringPage bot filter", () => {
  it("filters bots by default for both groups and lazy-loaded details", async () => {
    const user = userEvent.setup();
    renderPage();

    const filterBotsSwitch = screen.getByRole("switch", { name: "过滤机器人" });
    expect(filterBotsSwitch.getAttribute("aria-checked")).toBe("true");
    expect(api.groupParams.at(-1)).toMatchObject({ page: 1, include_bots: false });

    await user.click(screen.getByRole("button", { name: "展开" }));

    await waitFor(() => {
      expect(api.detailParams.at(-1)).toMatchObject({ page: 1, include_bots: false });
    });
  });

  it("returns to the first page when the filter is disabled without eager prefetch", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("88")).toBeTruthy();
    const firstPageIndicator = screen.getByText("1 / 3");
    const pagination = firstPageIndicator.parentElement;
    expect(pagination).not.toBeNull();
    const paginationButtons = within(pagination as HTMLElement).getAllByRole("button");
    await user.click(paginationButtons[1]);

    await waitFor(() => {
      expect(api.groupParams.at(-1)).toMatchObject({ page: 2, include_bots: false });
    });

    await user.click(screen.getByRole("switch", { name: "过滤机器人" }));

    await waitFor(() => {
      expect(api.groupParams.at(-1)).toMatchObject({ page: 1, include_bots: true });
    });
    expect(screen.getByText("1 / 3")).toBeTruthy();
    expect(screen.getByText("88")).toBeTruthy();
    expect(api.prefetchParams).toEqual([]);
  });

  it("returns expanded group details to the first page when the filter changes", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "展开" }));

    const detailPageIndicator = (await screen.findAllByText("1 / 3")).find((element) =>
      element.closest("tr"),
    );
    expect(detailPageIndicator?.parentElement).not.toBeNull();
    const detailPaginationButtons = within(
      detailPageIndicator?.parentElement as HTMLElement,
    ).getAllByRole("button");
    await user.click(detailPaginationButtons[1]);

    await waitFor(() => {
      expect(api.detailParams.at(-1)).toMatchObject({ page: 2, include_bots: false });
    });

    await user.click(screen.getByRole("switch", { name: "过滤机器人" }));

    await waitFor(() => {
      expect(api.detailParams.at(-1)).toMatchObject({ page: 1, include_bots: true });
    });
  });
});
