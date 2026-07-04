import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = readFileSync(
  new URL("../src/pages/more/FeatureTogglesSection.tsx", import.meta.url),
  "utf-8",
);

describe("feature toggles layout", () => {
  it("puts restore-default actions before save in subscription template sections", () => {
    expect(source).toContain("setAdvancedForm(createAdvancedSubscriptionForm())");
    expect(source).toContain("setCommentFeedbackForm(createCommentFeedbackForm())");

    const restoreActions = source.match(/siteConfig\.mailTemplateRestoreDefault/g) ?? [];
    expect(restoreActions).toHaveLength(2);

    const subscriptionHeader = source.slice(
      source.indexOf("siteConfig.contentSubscriptionAdvancedTitle"),
      source.indexOf("siteConfig.contentSubscriptionAllowedTypes"),
    );
    expect(subscriptionHeader.indexOf("siteConfig.mailTemplateRestoreDefault")).toBeGreaterThan(-1);
    expect(subscriptionHeader.indexOf("siteConfig.mailTemplateRestoreDefault")).toBeLessThan(
      subscriptionHeader.indexOf("<DirtySaveButton"),
    );

    const commentFeedbackHeader = source.slice(
      source.indexOf("siteConfig.commentFeedbackAdvancedTitle"),
      source.indexOf("siteConfig.commentFeedbackSubjectTemplate"),
    );
    expect(commentFeedbackHeader.indexOf("siteConfig.mailTemplateRestoreDefault")).toBeGreaterThan(-1);
    expect(commentFeedbackHeader.indexOf("siteConfig.mailTemplateRestoreDefault")).toBeLessThan(
      commentFeedbackHeader.indexOf("<DirtySaveButton"),
    );
  });
});
