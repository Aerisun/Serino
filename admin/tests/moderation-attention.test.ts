import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const readSource = (path: string) => readFileSync(fileURLToPath(new URL(path, import.meta.url)), "utf8");
const moderationPage = readSource("../src/pages/moderation/ModerationPage.tsx");
const moderationQueries = readSource("../src/pages/moderation/moderationQueries.ts");
const adminLayout = readSource("../src/layouts/AdminLayout.tsx");
const moderationAttentionIndicator = readSource("../src/components/ModerationAttentionIndicator.tsx");
const diaryAccessRequestsPanel = readSource("../src/pages/moderation/DiaryAccessRequestsPanel.tsx");
const zhTranslations = readSource("../src/i18n/translations-zh.ts");

describe("moderation attention UI", () => {
  it("marks only selected comments or guestbook entries as read", () => {
    expect(moderationPage).toContain(
      "markCommentsReadApiV1AdminModerationCommentsReadPatch",
    );
    expect(moderationPage).toContain(
      "markGuestbookReadApiV1AdminModerationGuestbookReadPatch",
    );
    expect(moderationPage).toContain("{ ids: selectedIds }");
    expect(moderationPage).not.toContain("selectCurrentPage");
    expect(moderationPage).not.toContain('{t("common.clear")}');
  });

  it("treats pending records as unread in the list as well as the attention totals", () => {
    expect(moderationPage).toContain('"friends",');
    expect(moderationPage).toContain("function isUnreadModerationRecord");
    expect(moderationPage).toContain("normalizeModerationStatus(item.status) === \"pending\"");
    expect(moderationPage).toContain("isUnreadModerationRecord(row)");
    expect(moderationPage).toContain("getRowClassName");
  });

  it("keeps unread row highlighting without adding a dot before the author name", () => {
    expect(moderationPage).not.toContain('aria-label={t("moderation.unread")}');
  });

  it("enables the mark-read action only for selected unread entries", () => {
    expect(moderationPage).toContain("const selectedUnreadIds = useMemo(");
    expect(moderationPage).toContain("markReadItems(selectedUnreadIds)");
    expect(moderationPage).toContain("markRead.isPending || !selectedUnreadIds.length");
    expect(moderationPage).toContain('"border-amber-400 bg-amber-400 text-amber-950');
  });

  it("gives selected unread entries a yellow detail border and unread badge", () => {
    expect(moderationPage).toContain('selectedItem && isUnreadModerationRecord(selectedItem)');
    expect(moderationPage).toContain('"border-amber-400/70');
    expect(moderationPage).toContain('<Badge variant="warning">{t("moderation.unread")}</Badge>');
  });

  it("keeps the shared statistics focused on total, unread, and pending work", () => {
    expect(moderationPage).toContain("const summary = { pending: 0, unread: 0 }");
    expect(moderationPage).toContain("if (isUnreadModerationRecord(item)) summary.unread += 1;");
    expect(moderationPage).toContain("label: t(\"moderation.unread\")");
    expect(moderationPage).toContain("value: counts.unread");
    expect(moderationPage).toContain("label: t(\"moderation.statPending\")");
    expect(moderationPage).toContain("border-rose-500/25 bg-rose-500/[0.12] text-rose-700 dark:text-rose-200");
    expect(moderationPage).not.toContain('label: t("moderation.statApproved")');
    expect(moderationPage).not.toContain('label: t("moderation.statRejected")');
    expect(zhTranslations).toContain('"moderation.statTotal": "全部"');
  });

  it("uses the shared attention query for yellow unread dots and red pending counts", () => {
    expect(moderationQueries).toContain(
      "getAttentionCountsApiV1AdminModerationAttentionCountsGet",
    );
    expect(moderationPage).toContain("ModerationAttentionIndicator");
    expect(adminLayout).toContain("unread_total");
    expect(adminLayout).toContain("pending_total");
    expect(moderationPage).toContain("bg-amber-400");
    expect(moderationAttentionIndicator).toContain("bg-amber-400");
    expect(moderationAttentionIndicator).toContain("bg-destructive");
    expect(moderationAttentionIndicator).toContain("useI18n");
    expect(diaryAccessRequestsPanel).toContain("MODERATION_ATTENTION_COUNT_QUERY_KEY");
  });

  it("refreshes moderation attention once per minute while keeping focus refresh", () => {
    expect(moderationQueries).toContain("MODERATION_ATTENTION_COUNT_STALE_TIME = 60_000");
    expect(moderationQueries).toContain("refetchInterval: MODERATION_ATTENTION_COUNT_STALE_TIME");
    expect(moderationQueries).toContain("refetchOnWindowFocus: true");
  });

  it("prioritizes a single pending or unread numeric reminder", () => {
    expect(moderationAttentionIndicator).toContain("const isPending = pending > 0");
    expect(moderationAttentionIndicator).toContain("const count = isPending ? pending : unread");
    expect(moderationAttentionIndicator).toContain("{count}");
    expect(moderationAttentionIndicator).not.toContain("{unread > 0 ? (");
    expect(moderationAttentionIndicator).not.toContain("{pending > 0 ? (");
  });
});
