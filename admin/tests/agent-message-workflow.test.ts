import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  canAddWorkflowNode,
  deriveTriggerBindings,
  friendlyNodeTypeLabel,
  type WorkflowCanvasNode,
} from "../src/pages/automation/workflow-editor-core";

const manualTrigger = {
  id: "trigger",
  type: "workflowNode",
  position: { x: 0, y: 0 },
  data: {
    nodeType: "trigger.manual",
    label: "手动触发",
    config: {},
  },
} as WorkflowCanvasNode;

const workflowsSource = readFileSync(
  new URL("../src/pages/automation/AgentWorkflowsSection.tsx", import.meta.url),
  "utf-8",
);
const editorSource = readFileSync(
  new URL(
    "../src/pages/automation/WorkflowVisualEditorDialog.tsx",
    import.meta.url,
  ),
  "utf-8",
);
const messagesSource = readFileSync(
  new URL("../src/pages/automation/AgentMessagesPage.tsx", import.meta.url),
  "utf-8",
);

describe("Agent internal message workflow", () => {
  it("allows exactly one trigger while keeping message output available", () => {
    expect(canAddWorkflowNode([manualTrigger], "trigger.message")).toBe(false);
    expect(canAddWorkflowNode([manualTrigger], "output.message")).toBe(true);
    expect(canAddWorkflowNode([], "trigger.message")).toBe(true);
    expect(deriveTriggerBindings([manualTrigger])).toHaveLength(1);
  });

  it("exposes clear labels for the internal message nodes", () => {
    expect(friendlyNodeTypeLabel("trigger.message", undefined, "zh")).toBe("留言触发");
    expect(friendlyNodeTypeLabel("output.message", undefined, "zh")).toBe("留言");
  });

  it("places the quick trigger before the visual editor without duplicating it on the canvas", () => {
    const quickTriggerIndex = workflowsSource.indexOf(
      "<WorkflowQuickTriggerButton",
    );
    const visualEditorIndex = workflowsSource.indexOf("{copy.visualEditor}");

    expect(quickTriggerIndex).toBeGreaterThan(-1);
    expect(quickTriggerIndex).toBeLessThan(visualEditorIndex);
    expect(editorSource).not.toContain("supportsQuickTrigger");
    expect(editorSource).not.toContain("messageDialogOpen");
  });

  it("renders a three-column message list without the filter toolbar", () => {
    const columnsSource = messagesSource.slice(
      messagesSource.indexOf("columns={["),
      messagesSource.indexOf("data={items}"),
    );
    const messageColumnSource = columnsSource.slice(
      columnsSource.indexOf('header: lang === "zh" ? "留言" : "Message"'),
      columnsSource.indexOf('header: lang === "zh" ? "工作流" : "Workflow"'),
    );

    expect(messagesSource).not.toContain("AdminToolbar");
    expect(messagesSource).not.toContain("NativeSelect");
    expect(messagesSource).not.toContain("workflowKey");
    expect(messagesSource).not.toContain("executionMode");
    expect(messagesSource).not.toContain("RotateCcw");
    expect(messagesSource).toContain('tableClassName="table-fixed"');
    expect(columnsSource.match(/\bheader:/g)).toHaveLength(3);
    expect(columnsSource).not.toContain('"模式" : "Mode"');
    expect(columnsSource).not.toContain('"运行" : "Run"');
    expect(messageColumnSource).toContain("row.message_preview");
    expect(messageColumnSource).not.toContain("row.message}");
    expect(messageColumnSource).toContain("truncate");
    expect(messageColumnSource).not.toContain("whitespace-pre-wrap");
  });

  it("loads full content only after selection and renders it in a mobile-safe dialog", () => {
    expect(messagesSource).toContain("setSelectedMessage(row)");
    expect(messagesSource).toContain(
      "useGetMessageApiV1AdminAutomationMessagesMessageIdGet",
    );
    expect(messagesSource).toContain("enabled: selectedMessage !== null");
    expect(messagesSource).toMatch(
      /<MarkdownPreview[\s\S]*?content=\{messageDetail\.message\}/,
    );
    expect(messagesSource).toContain('max-h-[calc(100dvh-1.5rem)]');
    expect(messagesSource).toContain('w-[calc(100%-1.5rem)]');
    expect(messagesSource).toContain("overflow-y-auto");
    expect(messagesSource).toContain("overscroll-contain");
    expect(messagesSource).toContain('className="w-full sm:w-auto"');
    expect(messagesSource).not.toContain(
      "onRowClick={(row) => navigate(`${detailBasePath}/${row.run_id}`)}",
    );
  });
});
