import test from "node:test";
import assert from "node:assert/strict";

import {
  describeApprovalPayload,
  summarizeApprovalPending,
  type ApprovalRequest,
} from "../src/lib/approvals.ts";

function makeRequest(overrides: Partial<ApprovalRequest> = {}): ApprovalRequest {
  return {
    action_id: "req_1",
    kind: "write_file",
    title: "Write source",
    reason: "Need generated file",
    risk_level: "medium",
    requires_approval: true,
    status: "pending",
    payload: {},
    ...overrides,
  };
}

test("优先使用后端给出的审批摘要", () => {
  const summary = summarizeApprovalPending("需要先审批", [makeRequest()]);
  assert.equal(summary, "需要先审批");
});

test("审批摘要为空时回退到动作数量文案", () => {
  const summary = summarizeApprovalPending("", [makeRequest(), makeRequest({ action_id: "req_2" })]);
  assert.equal(summary, "有 2 个动作等待审批");
});

test("优先提取命令与路径作为审批详情", () => {
  assert.equal(
    describeApprovalPayload(makeRequest({ payload: { command: ["dotnet", "publish"] } })),
    "dotnet publish",
  );
  assert.equal(
    describeApprovalPayload(makeRequest({ payload: { path: "Cards/TestCard.cs" } })),
    "Cards/TestCard.cs",
  );
});
