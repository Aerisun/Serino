import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const readSource = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf-8");

const extractDefaultFeedbackTemplate = (source: string) => {
  const start = source.indexOf("const DEFAULT_DIARY_ACCESS_FEEDBACK_TEMPLATE =");
  const end = source.indexOf("interface DiaryAccessRow", start);
  expect(start).toBeGreaterThanOrEqual(0);
  expect(end).toBeGreaterThan(start);
  return source.slice(start, end);
};

describe("diary access moderation layout", () => {
  it("keeps permission controls away from the card edges", () => {
    const source = readSource("../src/pages/moderation/DiaryAccessRequestsPanel.tsx");

    expect(source).toContain("justify-between gap-3 px-3 sm:px-4");
    expect(source).toContain("min-w-[7rem] justify-center");
  });

  it("offsets the feedback format action from the diary access title", () => {
    const source = readSource("../src/pages/moderation/DiaryAccessRequestsPanel.tsx");

    expect(source).toContain('className="sm:ml-2"');
    expect(source).toContain('{t("moderation.diaryAccessFeedbackTemplateAction")}');
  });

  it("gives the diary access tab room above the panel", () => {
    const source = readSource("../src/pages/moderation/ModerationPage.tsx");

    expect(source).toContain("mb-10 sm:mb-12");
    expect(source).toContain('<div className="pt-6">');
  });

  it("keeps the permission status column readable on narrow screens", () => {
    const source = readSource("../src/pages/moderation/DiaryAccessRequestsPanel.tsx");

    expect(source).toContain('className: "min-w-[8.5rem] whitespace-nowrap"');
    expect(source).toContain('className="min-w-[8.5rem] whitespace-nowrap p-4 align-middle"');
  });

  it("keeps the feedback template dialog focused on editing", () => {
    const source = readSource("../src/pages/moderation/DiaryAccessRequestsPanel.tsx");

    expect(source).not.toContain("moderation.diaryAccessFeedbackTemplateDefault");
    expect(source).toContain("moderation.diaryAccessFeedbackTemplateRestoreDefault");
    expect(source).toContain("LabelWithHelp");
    expect(source).toContain("moderation.diaryAccessFeedbackTemplateVariablesDescription");
    expect(source).toContain("moderation.diaryAccessFeedbackTemplatePlaceholderVisitorEmail");
    expect(source).toContain("moderation.diaryAccessFeedbackTemplatePlaceholderReviewedAt");
    expect(source).not.toContain('{t("common.cancel")}');
  });

  it("keeps expiry but no request reason in the default feedback template", () => {
    const source = readSource("../src/pages/moderation/DiaryAccessRequestsPanel.tsx");
    const defaultTemplate = extractDefaultFeedbackTemplate(source);

    expect(defaultTemplate).toContain("审核结果：{decision}");
    expect(defaultTemplate).toContain("权限到期时间：{expires_at}");
    expect(defaultTemplate).not.toContain("申请理由");
    expect(defaultTemplate).not.toContain("{reason}");
  });
});
