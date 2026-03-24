export type ApprovalRiskLevel = "low" | "medium" | "high";

export interface ApprovalRequest {
  action_id: string;
  kind: string;
  title: string;
  reason: string;
  risk_level: ApprovalRiskLevel;
  requires_approval: boolean;
  status: string;
  payload: Record<string, unknown>;
}

export function summarizeApprovalPending(summary: string, requests: ApprovalRequest[]): string {
  const trimmed = summary.trim();
  return trimmed || `有 ${requests.length} 个动作等待审批`;
}

export function describeApprovalPayload(request: ApprovalRequest): string {
  const command = request.payload.command;
  if (Array.isArray(command)) {
    return command.join(" ");
  }

  const path = request.payload.path;
  if (typeof path === "string" && path) {
    return path;
  }

  return "";
}

async function postApproval(path: string, body?: object): Promise<ApprovalRequest> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export function approveApproval(actionId: string): Promise<ApprovalRequest> {
  return postApproval(`/api/approvals/${actionId}/approve`);
}

export function rejectApproval(actionId: string, reason = "Rejected from UI"): Promise<ApprovalRequest> {
  return postApproval(`/api/approvals/${actionId}/reject`, { reason });
}

export function executeApproval(actionId: string): Promise<ApprovalRequest> {
  return postApproval(`/api/approvals/${actionId}/execute`);
}
