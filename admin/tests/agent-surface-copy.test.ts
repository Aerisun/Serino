import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const approvalsSource = readFileSync(
  new URL("../src/pages/automation/ApprovalsPage.tsx", import.meta.url),
  "utf-8",
);
const runsSource = readFileSync(
  new URL("../src/pages/automation/AgentRunsPage.tsx", import.meta.url),
  "utf-8",
);
const approvalsPanelSource = approvalsSource.slice(
  approvalsSource.indexOf("export function ApprovalsPanel"),
  approvalsSource.indexOf("export default function ApprovalsPage"),
);
const runsPanelSource = runsSource.slice(
  runsSource.indexOf("export function AgentRunsPanel"),
  runsSource.indexOf("export default function AgentRunsPage"),
);

describe("Agent activity surface copy", () => {
  it("removes only the Approval eyebrow from the approvals panel", () => {
    expect(approvalsPanelSource).not.toContain('eyebrow="Approval"');
    expect(approvalsPanelSource).toContain(
      'description={t("automation.approvalsDescription")}',
    );
  });

  it("removes the Automation eyebrow and description from the runs panel", () => {
    expect(runsPanelSource).not.toContain('eyebrow="Automation"');
    expect(runsPanelSource).not.toContain(
      'description={t("automation.runsDescription")}',
    );
  });
});
