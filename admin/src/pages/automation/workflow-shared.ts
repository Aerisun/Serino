import type {
  AgentWorkflowGraph,
  AgentWorkflowRuntimePolicy,
  AgentWorkflowTriggerBinding,
} from "@/pages/automation/api";
import type { WebhookDeliveryRead } from "@serino/api-client/models";

export const WORKFLOWS_QUERY_KEY = ["admin", "agent", "workflows"] as const;
export const WORKFLOW_CATALOG_QUERY_KEY = ["admin", "agent", "workflow-catalog"] as const;

export function deriveWorkflowSummary(
  name: string,
  graph: AgentWorkflowGraph,
  triggerBindings: AgentWorkflowTriggerBinding[],
) {
  const operationNodes = graph.nodes.filter((node) => node.type.startsWith("operation."));
  const actionNodes = graph.nodes.filter((node) => node.type === "apply.action");
  const highRiskOperationCount = operationNodes.filter(
    (node) => String((node.config || {}).risk_level || "").toLowerCase() === "high",
  ).length;
  return {
    trigger_labels: triggerBindings.map((item) => item.label),
    node_count: graph.nodes.length,
    operation_count: operationNodes.length + actionNodes.length,
    high_risk_operation_count: highRiskOperationCount,
    narrative: `${name} · ${graph.nodes.length} nodes`,
  };
}

export function latestDeliveriesBySubscription(deliveries: WebhookDeliveryRead[]) {
  const map = new Map<string, WebhookDeliveryRead>();
  for (const item of deliveries) {
    if (!map.has(item.subscription_id)) {
      map.set(item.subscription_id, item);
    }
  }
  return map;
}

export function runtimePolicyDefaults(
  policy: AgentWorkflowRuntimePolicy | null | undefined,
): AgentWorkflowRuntimePolicy {
  return {
    approval_mode: policy?.approval_mode || "risk_based",
    allow_high_risk_without_approval: Boolean(policy?.allow_high_risk_without_approval),
    max_steps: policy?.max_steps || 80,
    retry_policy: policy?.retry_policy || {},
    default_model: policy?.default_model ?? null,
  };
}
