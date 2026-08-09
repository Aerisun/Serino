// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "../src/i18n";
import ModerationPage from "../src/pages/moderation/ModerationPage";

const api = vi.hoisted(() => ({
  listComments: vi.fn(),
}));

vi.mock("@serino/api-client/admin", () => ({
  getListCommentsApiV1AdminModerationCommentsGetQueryKey: (params?: unknown) => [
    "moderation-comments",
    params,
  ],
  getListGuestbookApiV1AdminModerationGuestbookGetQueryKey: (params?: unknown) => [
    "moderation-guestbook",
    params,
  ],
  listCommentsApiV1AdminModerationCommentsGet: (...args: unknown[]) =>
    api.listComments(...args),
  listGuestbookApiV1AdminModerationGuestbookGet: vi.fn().mockResolvedValue({
    data: { items: [], total: 0, page: 1, page_size: 20 },
  }),
  markCommentsReadApiV1AdminModerationCommentsReadPatch: vi.fn(),
  markGuestbookReadApiV1AdminModerationGuestbookReadPatch: vi.fn(),
  moderateCommentEndpointApiV1AdminModerationCommentsCommentIdModeratePost: vi.fn(),
  moderateGuestbookEndpointApiV1AdminModerationGuestbookEntryIdModeratePost: vi.fn(),
  updateCommentFeedbackEndpointApiV1AdminModerationCommentsCommentIdFeedbackPatch: vi.fn(),
  listPosts: vi.fn().mockResolvedValue({ data: { items: [] } }),
  listDiary: vi.fn().mockResolvedValue({ data: { items: [] } }),
  listThoughts: vi.fn().mockResolvedValue({ data: { items: [] } }),
  listExcerpts: vi.fn().mockResolvedValue({ data: { items: [] } }),
  useGetContentSubscriptionConfigApiV1AdminSubscriptionsConfigGet: () => ({
    data: { data: { comment_feedback_enabled: false } },
  }),
  useGetProfileApiV1AdminSiteConfigProfileGet: () => ({
    data: {
      data: {
        feature_flags: {
          diary_private_enabled: false,
          post_access_approval_enabled: false,
        },
      },
    },
  }),
}));

vi.mock("../src/pages/moderation/moderationQueries", () => ({
  MODERATION_ATTENTION_COUNT_QUERY_KEY: ["moderation", "attention-counts"],
  moderationAttentionCountQueryOptions: () => ({
    queryKey: ["moderation", "attention-counts"],
    queryFn: () =>
      Promise.resolve({
        comments: { pending: 0, unread: 0 },
        guestbook: { pending: 0, unread: 0 },
        diary_access: { pending: 0 },
        post_access: { pending: 0 },
        pending_total: 0,
        unread_total: 0,
      }),
  }),
}));

vi.mock("../src/pages/moderation/DiaryAccessRequestsPanel", () => ({
  DiaryAccessRequestsPanel: () => null,
}));

vi.mock("../src/pages/moderation/PostAccessRequestsPanel", () => ({
  PostAccessRequestsPanel: () => null,
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <LanguageProvider>
        <ModerationPage />
      </LanguageProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  localStorage.clear();
});

describe("moderation friend source", () => {
  it("shows the friend-link source in both the list and detail panel", async () => {
    api.listComments.mockResolvedValue({
      data: {
        items: [
          {
            id: "friend-comment-1",
            content_type: "friends",
            content_slug: "friends",
            parent_id: null,
            author_name: "Friend applicant",
            author_email: null,
            auth_provider: null,
            body: "希望交换友链。",
            status: "approved",
            feedback_enabled: true,
            is_read: true,
            deletion_reason: null,
            created_at: "2026-08-09T10:00:00+08:00",
            updated_at: "2026-08-09T10:00:00+08:00",
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getAllByText("友链")).toHaveLength(2);
    });
  });
});
