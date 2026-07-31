import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = readFileSync(
  new URL("../src/pages/more/FeatureTogglesSection.tsx", import.meta.url),
  "utf-8",
);

describe("feature toggles layout", () => {
  it("groups personalization controls and persists owner-comment activity filters", () => {
    expect(source).toContain('title={t("siteConfig.personalization")}');
    expect(source).toContain('"toc"');
    expect(source).toContain('"reading_progress"');
    expect(source).toContain("recent_activity_owner_comment_content_types");
    expect(source).toContain('t("siteConfig.recentActivityOwnerComment")');
    expect(source).toContain('t("siteConfig.recentActivityOwnerCommentHelp")');
    expect(source).toContain('key: "posts"');
    expect(source).toContain('key: "diary"');
    expect(source).toContain('key: "thoughts"');
    expect(source).toContain('key: "excerpts"');
    expect(source).toContain('t("siteConfig.featurePostAccessApproval")');
    expect(source).toContain('t("siteConfig.featurePostAccessApprovalHelp")');
    expect(source).toContain('post_access_approval_enabled');
    expect(source).toContain("<LabelWithHelp");
  });

  it("keeps every personalization control in the final collapsed section", () => {
    const personalizationStart = source.indexOf(
      '<CollapsibleSection title={t("siteConfig.personalization")}>',
    );
    const personalizationEnd = source.indexOf("</CollapsibleSection>", personalizationStart);
    const personalizationSection = source.slice(personalizationStart, personalizationEnd);
    const afterPersonalization = source.slice(
      personalizationEnd + "</CollapsibleSection>".length,
    );

    expect(personalizationEnd).toBeGreaterThan(personalizationStart);
    expect(personalizationSection).toContain("{personalizationFlags.map");
    expect(personalizationSection).toContain('t("siteConfig.recentActivityOwnerComment")');
    expect(personalizationSection).toContain("aria-controls={ownerCommentActivityContentId}");
    expect(personalizationSection).toContain("aria-hidden={!ownerCommentActivityExpanded}");
    expect(personalizationSection).toContain("inert={!ownerCommentActivityExpanded ? true : undefined}");
    expect(personalizationSection).not.toContain("diary_private_enabled");
    expect(personalizationSection).not.toContain("checked={subscriptionEnabled}");
    expect(personalizationSection).not.toContain("checked={commentFeedbackEnabled}");
    expect(personalizationStart).toBeGreaterThan(
      source.indexOf("checked={subscriptionEnabled}"),
    );
    expect(personalizationStart).toBeGreaterThan(
      source.indexOf("checked={commentFeedbackEnabled}"),
    );
    expect(afterPersonalization).not.toContain("<AppleSwitch");
    expect(afterPersonalization).not.toContain("<CollapsibleSection");
  });

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
