import { describeApprovalPayload, summarizeApprovalPending, type ApprovalRequest } from "../lib/approvals";

function riskLabel(risk: ApprovalRequest["risk_level"]): string {
  if (risk === "high") return "高风险";
  if (risk === "medium") return "中风险";
  return "低风险";
}

export function ApprovalPanel({
  summary,
  requests,
  busyActionId = null,
  onApprove,
  onReject,
  onExecute,
  onProceed,
}: {
  summary: string;
  requests: ApprovalRequest[];
  busyActionId?: string | null;
  onApprove?: (actionId: string) => void;
  onReject?: (actionId: string) => void;
  onExecute?: (actionId: string) => void;
  onProceed?: () => void;
}) {
  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
        <p className="text-sm font-semibold text-amber-700">等待审批</p>
        <p className="mt-1 text-xs text-amber-700/80">
          {summarizeApprovalPending(summary, requests)}
        </p>
      </div>

      <div className="space-y-2">
        {requests.map((request) => {
          const detail = describeApprovalPayload(request);
          return (
            <div key={request.action_id} className="rounded-lg border border-slate-200 bg-white p-3 space-y-2">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-slate-700">{request.title}</p>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                  {riskLabel(request.risk_level)}
                </span>
              </div>
              {request.reason && (
                <p className="text-xs text-slate-500">{request.reason}</p>
              )}
              {detail && (
                <pre className="rounded bg-slate-50 px-2.5 py-2 text-xs text-slate-500 font-mono whitespace-pre-wrap break-all">
                  {detail}
                </pre>
              )}
              <p className="text-xs text-slate-400">状态：{request.status}</p>
              <div className="flex flex-wrap gap-2">
                {request.status === "pending" && request.requires_approval && onApprove && (
                  <button
                    onClick={() => onApprove(request.action_id)}
                    disabled={busyActionId === request.action_id}
                    className="rounded-md bg-amber-500 px-2.5 py-1 text-xs font-medium text-white disabled:opacity-50"
                  >
                    批准
                  </button>
                )}
                {request.status === "pending" && request.requires_approval && onReject && (
                  <button
                    onClick={() => onReject(request.action_id)}
                    disabled={busyActionId === request.action_id}
                    className="rounded-md border border-slate-200 px-2.5 py-1 text-xs text-slate-500 disabled:opacity-50"
                  >
                    拒绝
                  </button>
                )}
                {(request.status === "approved" || (!request.requires_approval && request.status === "pending")) && onExecute && (
                  <button
                    onClick={() => onExecute(request.action_id)}
                    disabled={busyActionId === request.action_id}
                    className="rounded-md bg-slate-700 px-2.5 py-1 text-xs font-medium text-white disabled:opacity-50"
                  >
                    执行
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {onProceed && (
        <button
          onClick={onProceed}
          className="w-full rounded-md bg-amber-500 px-3 py-2 text-sm font-medium text-white hover:bg-amber-600"
        >
          确认，开始生成代码
        </button>
      )}
    </div>
  );
}
