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
});
