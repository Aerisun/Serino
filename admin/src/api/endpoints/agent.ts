import { getAdminToken } from "@/lib/storage";

export interface AgentModelConfig {
  enabled: boolean;
  provider: string;
  base_url: string;
  model: string;
  api_key: string;
  temperature: number;
  timeout_seconds: number;
  advisory_prompt: string;
  is_ready: boolean;
}

export interface AgentModelConfigTestResult {
  ok: boolean;
  model: string;
  endpoint: string;
  summary: string;
}

export interface AgentWorkflow {
  key: string;
  name: string;
  description: string;
  trigger_event: string;
  target_type: string | null;
  enabled: boolean;
  require_human_approval: boolean;
  instructions: string;
  built_in: boolean;
}

export interface AgentWorkflowDraftMessage {
  role: string;
  content: string;
  created_at: string;
}

export interface AgentWorkflowDraftOption {
  label: string;
  value: string;
  description: string;
  requires_input: boolean;
}

export interface AgentWorkflowDraftQuestion {
  key: string;
  prompt: string;
  options: AgentWorkflowDraftOption[];
}

export interface AgentWorkflowDraft {
  id: string;
  status: string;
  summary: string;
  ready_to_create: boolean;
  suggested_template: string | null;
  questions?: AgentWorkflowDraftQuestion[];
  current_question: string;
  options: AgentWorkflowDraftOption[];
  working_document: string;
  messages: AgentWorkflowDraftMessage[];
  created_at: string;
  updated_at: string;
}

export interface AgentWorkflowDraftCreateResult {
  ok: boolean;
  summary: string;
  draft_cleared: boolean;
  workflow: AgentWorkflow;
}

export type AgentWorkflowDraftStreamEvent =
  | { type: "status"; status: string; elapsed_seconds?: number }
  | { type: "chunk"; content: string }
  | { type: "done"; draft: AgentWorkflowDraft }
  | { type: "error"; error: string };

export interface AgentModelConfigUpdate {
  enabled: boolean;
  provider: string;
  base_url: string;
  model: string;
  api_key: string;
  temperature: number;
  timeout_seconds: number;
  advisory_prompt: string;
}

export interface AgentWorkflowInput {
  key?: string;
  name: string;
  description: string;
  trigger_event: string;
  target_type: string | null;
  enabled: boolean;
  require_human_approval: boolean;
  instructions: string;
}

async function adminRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAdminToken();
  if (!token) {
    throw new Error("未登录，无法执行管理操作");
  }

  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new Error("请求失败，请检查网络连接或后端服务状态");
  }

  const payload = await response
    .json()
    .catch(() => null);
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? payload.detail
        : undefined;
    throw new Error(typeof detail === "string" ? detail : "操作失败");
  }
  return payload as T;
}

export function getAgentModelConfig() {
  return adminRequest<AgentModelConfig>("/api/v1/admin/automation/model-config", {
    method: "GET",
  });
}

export function updateAgentModelConfig(data: AgentModelConfigUpdate) {
  return adminRequest<AgentModelConfig>("/api/v1/admin/automation/model-config", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function testAgentModelConfig(data: AgentModelConfigUpdate) {
  return adminRequest<AgentModelConfigTestResult>("/api/v1/admin/automation/model-config/test", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getAgentWorkflows() {
  return adminRequest<AgentWorkflow[]>("/api/v1/admin/automation/workflows", {
    method: "GET",
  });
}

export function createAgentWorkflow(data: AgentWorkflowInput) {
  return adminRequest<AgentWorkflow>("/api/v1/admin/automation/workflows", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateAgentWorkflow(workflowKey: string, data: AgentWorkflowInput) {
  return adminRequest<AgentWorkflow>(`/api/v1/admin/automation/workflows/${workflowKey}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteAgentWorkflow(workflowKey: string) {
  const token = getAdminToken();
  if (!token) {
    throw new Error("未登录，无法执行管理操作");
  }

  let response: Response;
  try {
    response = await fetch(`/api/v1/admin/automation/workflows/${workflowKey}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  } catch {
    throw new Error("请求失败，请检查网络连接或后端服务状态");
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? payload.detail
        : undefined;
    throw new Error(typeof detail === "string" ? detail : "操作失败");
  }
}

export function getAgentWorkflowDraft() {
  return adminRequest<AgentWorkflowDraft | null>("/api/v1/admin/automation/workflow-draft", {
    method: "GET",
  });
}

export function sendAgentWorkflowDraftMessage(message: string) {
  return adminRequest<AgentWorkflowDraft>("/api/v1/admin/automation/workflow-draft/messages", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export async function streamAgentWorkflowDraftMessage(
  message: string,
  onEvent: (event: AgentWorkflowDraftStreamEvent) => void,
) {
  const token = getAdminToken();
  if (!token) {
    throw new Error("未登录，无法执行管理操作");
  }

  let response: Response;
  try {
    response = await fetch("/api/v1/admin/automation/workflow-draft/messages/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ message }),
    });
  } catch {
    throw new Error("请求失败，请检查网络连接或后端服务状态");
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? payload.detail
        : undefined;
    throw new Error(typeof detail === "string" ? detail : "操作失败");
  }

  if (!response.body) {
    throw new Error("服务端未返回流式响应");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const event = JSON.parse(trimmed) as AgentWorkflowDraftStreamEvent;
      if (event.type === "error") {
        throw new Error(event.error || "操作失败");
      }
      onEvent(event);
    }
  }

  const finalChunk = buffer.trim();
  if (finalChunk) {
    const event = JSON.parse(finalChunk) as AgentWorkflowDraftStreamEvent;
    if (event.type === "error") {
      throw new Error(event.error || "操作失败");
    }
    onEvent(event);
  }
}

export function createAgentWorkflowFromDraft(force = false) {
  return adminRequest<AgentWorkflowDraftCreateResult>("/api/v1/admin/automation/workflow-draft/create", {
    method: "POST",
    body: JSON.stringify({ force }),
  });
}

export async function clearAgentWorkflowDraft() {
  const token = getAdminToken();
  if (!token) {
    throw new Error("未登录，无法执行管理操作");
  }

  let response: Response;
  try {
    response = await fetch("/api/v1/admin/automation/workflow-draft", {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  } catch {
    throw new Error("请求失败，请检查网络连接或后端服务状态");
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? payload.detail
        : undefined;
    throw new Error(typeof detail === "string" ? detail : "操作失败");
  }
}
