import { useState, useCallback, useRef, useEffect } from "react";
import {
  Loader2, ChevronDown, ChevronUp, RotateCcw,
  CheckCircle2, XCircle, Clock, ImageIcon, Code2, Sparkles, AlertTriangle,
  Upload, Wand2,
} from "lucide-react";
import { ApprovalPanel } from "../components/ApprovalPanel";
import { approveApproval, executeApproval, rejectApproval, type ApprovalRequest } from "../lib/approvals";
import { BatchSocket, PlanItem, ModPlan } from "../lib/batch_ws";
import { pickActiveItemOnDone, pickActiveItemOnStart } from "../lib/batchActiveItem";
import { AgentLog } from "../components/AgentLog";
import { StageStatus } from "../components/StageStatus";
import { BuildDeploy } from "../components/BuildDeploy";
import { cn } from "../lib/utils";

// ── 类型 ──────────────────────────────────────────────────────────────────────

type BatchStage = "input" | "planning" | "review_plan" | "executing" | "done" | "error";

type ItemStatus =
  | "pending"
  | "img_generating"
  | "awaiting_selection"
  | "approval_pending"
  | "code_generating"
  | "done"
  | "error";

interface ItemState {
  status: ItemStatus;
  currentStage: string | null;
  stageHistory: string[];
  progress: string[];
  images: string[];
  agentLog: string[];
  error: string | null;
  errorTrace: string | null;
  currentPrompt: string;
  showMorePrompt: boolean;
  approvalSummary: string;
  approvalRequests: ApprovalRequest[];
}

function defaultItemState(): ItemState {
  return {
    status: "pending",
    currentStage: null,
    stageHistory: [],
    progress: [],
    images: [],
    agentLog: [],
    error: null,
    errorTrace: null,
    currentPrompt: "",
    showMorePrompt: false,
    approvalSummary: "",
    approvalRequests: [],
  };
}

// ── 工具函数 ──────────────────────────────────────────────────────────────────

const TYPE_LABELS: Record<string, string> = {
  card: "卡牌",
  card_fullscreen: "全画面卡",
  relic: "遗物",
  power: "Power",
  character: "角色",
  custom_code: "代码",
};

const STATUS_ICONS: Record<ItemStatus, React.ReactNode> = {
  pending:            <Clock size={14} className="text-slate-300" />,
  img_generating:     <Loader2 size={14} className="text-amber-400 animate-spin" />,
  awaiting_selection: <ImageIcon size={14} className="text-amber-500" />,
  approval_pending:   <Clock size={14} className="text-violet-500" />,
  code_generating:    <Code2 size={14} className="text-blue-400 animate-pulse" />,
  done:               <CheckCircle2 size={14} className="text-green-500" />,
  error:              <XCircle size={14} className="text-red-500" />,
};

const STATUS_LABELS: Record<ItemStatus, string> = {
  pending:            "等待中",
  img_generating:     "生成图像",
  awaiting_selection: "等待选图",
  approval_pending:   "等待审批",
  code_generating:    "生成代码",
  done:               "完成",
  error:              "失败",
};

// ── 主组件 ────────────────────────────────────────────────────────────────────

export default function BatchMode() {
  const [stage, setStage] = useState<BatchStage>("input");
  const [requirements, setRequirements] = useState("");
  const [projectRoot, setProjectRoot] = useState("");

  useEffect(() => {
    fetch("/api/config").then(r => r.json()).then(cfg => {
      if (cfg?.default_project_root) setProjectRoot(cfg.default_project_root);
    }).catch(() => {});
  }, []);

  const [plan, setPlan] = useState<ModPlan | null>(() => {
    try { const s = localStorage.getItem("ats_last_plan"); return s ? JSON.parse(s) : null; } catch { return null; }
  });
  const [editedItems, setEditedItems] = useState<PlanItem[]>(() => {
    try { const s = localStorage.getItem("ats_last_plan_items"); return s ? JSON.parse(s) : []; } catch { return []; }
  });
  const [activeItemId, setActiveItemId] = useState<string | null>(null);
  const [itemStates, setItemStates] = useState<Record<string, ItemState>>({});
  const itemStatesRef = useRef<Record<string, ItemState>>({});
  const [batchLog, setBatchLog] = useState<string[]>([]);
  const [currentBatchStage, setCurrentBatchStage] = useState<string | null>(null);
  const [batchStageHistory, setBatchStageHistory] = useState<string[]>([]);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [batchResult, setBatchResult] = useState<{ success: number; error: number } | null>(null);
  const [approvalBusyActionId, setApprovalBusyActionId] = useState<string | null>(null);

  const [autoSelectFirst, setAutoSelectFirst] = useState(false);
  const autoSelectRef = useRef(false);
  useEffect(() => { autoSelectRef.current = autoSelectFirst; }, [autoSelectFirst]);
  const socketRef = useRef<BatchSocket | null>(null);

  // ── State updater helpers ─────────────────────────────────────────────────

  const applyItemStates = useCallback((updater: (prev: Record<string, ItemState>) => Record<string, ItemState>) => {
    const next = updater(itemStatesRef.current);
    itemStatesRef.current = next;
    setItemStates(next);
  }, []);

  const updateItem = useCallback((id: string, patch: Partial<ItemState>) => {
    applyItemStates(prev => ({
      ...prev,
      [id]: { ...(prev[id] ?? defaultItemState()), ...patch },
    }));
  }, [applyItemStates]);

  const appendProgress = useCallback((id: string, msg: string) => {
    applyItemStates(prev => {
      const cur = prev[id] ?? defaultItemState();
      return { ...prev, [id]: { ...cur, progress: [...cur.progress, msg] } };
    });
  }, [applyItemStates]);

  const appendAgent = useCallback((id: string, chunk: string) => {
    applyItemStates(prev => {
      const cur = prev[id] ?? defaultItemState();
      return { ...prev, [id]: { ...cur, agentLog: [...cur.agentLog, chunk] } };
    });
  }, [applyItemStates]);

  const addImage = useCallback((id: string, b64: string, index: number, prompt: string) => {
    applyItemStates(prev => {
      const cur = prev[id] ?? defaultItemState();
      const images = [...cur.images];
      images[index] = b64;
      return { ...prev, [id]: { ...cur, images, currentPrompt: prompt, status: "awaiting_selection" } };
    });
    // 如果当前没有 active item，自动跳到这个需要选图的 item
    setActiveItemId(prev => prev ?? id);
  }, [applyItemStates]);

  // ── Start ─────────────────────────────────────────────────────────────────

  async function startPlanning() {
    if (!requirements.trim()) return;
    setStage("planning");
    setBatchLog([]);
    setGlobalError(null);
    itemStatesRef.current = {};
    setItemStates({});
    setBatchResult(null);
    setCurrentBatchStage(null);
    setBatchStageHistory([]);
    setPlan(null);
    setActiveItemId(null);

    const ws = new BatchSocket();
    socketRef.current = ws;
    _registerBatchHandlers(ws);

    await ws.waitOpen();
    ws.send({ action: "start", requirements, project_root: projectRoot });
  }

  function _registerBatchHandlers(ws: BatchSocket) {
    ws.on("planning", () => setBatchLog(l => [...l, "正在规划 Mod..."]));
    ws.on("plan_ready", (d) => {
      setPlan(d.plan);
      setEditedItems(d.plan.items);
      setStage("review_plan");
      try {
        localStorage.setItem("ats_last_plan", JSON.stringify(d.plan));
        localStorage.setItem("ats_last_plan_items", JSON.stringify(d.plan.items));
      } catch {}
    });
    ws.on("batch_progress", (d) => setBatchLog(l => [...l, d.message]));
    ws.on("stage_update", (d) => {
      if (d.item_id) {
        applyItemStates(prev => {
          const cur = prev[d.item_id!] ?? defaultItemState();
          return {
            ...prev,
            [d.item_id!]: {
              ...cur,
              currentStage: d.message,
              stageHistory: cur.stageHistory[cur.stageHistory.length - 1] === d.message ? cur.stageHistory : [...cur.stageHistory, d.message],
            },
          };
        });
        return;
      }
      setCurrentBatchStage(d.message);
      setBatchStageHistory(prev => prev[prev.length - 1] === d.message ? prev : [...prev, d.message]);
    });
    ws.on("batch_started", (d) => {
      const init: Record<string, ItemState> = {};
      d.items.forEach(it => { init[it.id] = defaultItemState(); });
      itemStatesRef.current = init;
      setItemStates(init);
      setStage("executing");
      setActiveItemId(d.items[0]?.id ?? null);
    });
    ws.on("item_started", (d) => {
      updateItem(d.item_id, { status: "img_generating" });
      setActiveItemId(prev => pickActiveItemOnStart(prev, itemStatesRef.current, d.item_id));
    });
    ws.on("item_progress", (d) => {
      appendProgress(d.item_id, d.message);
      if (d.message.includes("Code Agent")) {
        updateItem(d.item_id, { status: "code_generating" });
      }
    });
    ws.on("item_image_ready", (d) => {
      addImage(d.item_id, d.image, d.index, d.prompt);
      if (autoSelectRef.current) {
        ws.send({ action: "select_image", item_id: d.item_id, index: 0 });
        updateItem(d.item_id, { status: "code_generating" });
      }
    });
    ws.on("item_agent_stream", (d) => { appendAgent(d.item_id, d.chunk); });
    ws.on("item_approval_pending", (d) => {
      updateItem(d.item_id, {
        status: "approval_pending",
        approvalSummary: d.summary,
        approvalRequests: d.requests,
      });
      setActiveItemId(prev => prev ?? d.item_id);
    });
    ws.on("item_done", (d) => {
      updateItem(d.item_id, { status: "done" });
      setActiveItemId(prev => pickActiveItemOnDone(prev, d.item_id, itemStatesRef.current));
    });
    ws.on("item_error", (d) => {
      updateItem(d.item_id, { status: "error", error: d.message, errorTrace: d.traceback ?? null });
    });
    ws.on("batch_done", (d) => {
      setBatchResult({ success: d.success_count, error: d.error_count });
      setStage("done");
    });
    ws.on("error", (d) => { setGlobalError(d.message); setStage("error"); });
  }

  async function confirmPlan() {
    if (!plan) return;
    const itemsForStorage = editedItems.map(it => ({ ...it, provided_image_b64: undefined }));
    try { localStorage.setItem("ats_last_plan_items", JSON.stringify(itemsForStorage)); } catch {}

    if (!socketRef.current) {
      // 恢复的规划：重新建连接，直接跳到执行
      const ws = new BatchSocket();
      socketRef.current = ws;
      _registerBatchHandlers(ws);
      await ws.waitOpen();
      setStage("executing");
      ws.send({ action: "start_with_plan", project_root: projectRoot, plan: { ...plan, items: editedItems } });
    } else {
      setStage("executing");
      socketRef.current.send({ action: "confirm_plan", plan: { ...plan, items: editedItems } });
    }
  }

  function handleSelectImage(itemId: string, index: number) {
    if (!socketRef.current) return;
    socketRef.current.send({ action: "select_image", item_id: itemId, index });
    updateItem(itemId, { status: "code_generating" });
    const nextAwaiting = editedItems.find(
      it => it.id !== itemId && itemStatesRef.current[it.id]?.status === "awaiting_selection"
    );
    if (nextAwaiting) setActiveItemId(nextAwaiting.id);
  }

  function handleRetryItem(itemId: string) {
    if (!socketRef.current) return;
    socketRef.current.send({ action: "retry_item", item_id: itemId });
    updateItem(itemId, { status: "img_generating", error: null, errorTrace: null, progress: [], agentLog: [], images: [] });
  }

  function handleGenerateMore(itemId: string) {
    if (!socketRef.current) return;
    const state = itemStatesRef.current[itemId];
    socketRef.current.send({
      action: "generate_more",
      item_id: itemId,
      prompt: state?.currentPrompt,
    });
    updateItem(itemId, { status: "img_generating", showMorePrompt: false });
  }

  function reset() {
    socketRef.current?.close();
    socketRef.current = null;
    setStage("input");
    setPlan(null);
    setEditedItems([]);
    itemStatesRef.current = {};
    setItemStates({});
    setBatchLog([]);
    setGlobalError(null);
    setBatchResult(null);
    setActiveItemId(null);
    setApprovalBusyActionId(null);
  }

  async function handleApprovalAction(
    actionId: string,
    action: (id: string) => Promise<ApprovalRequest>,
  ) {
    setApprovalBusyActionId(actionId);
    try {
      const updated = await action(actionId);
      applyItemStates(prev => {
        const next: Record<string, ItemState> = { ...prev };
        for (const [id, state] of Object.entries(prev)) {
          const nextRequests = state.approvalRequests.map(req => req.action_id === actionId ? updated : req);
          const nextStatus =
            state.status === "approval_pending" && nextRequests.length > 0 && nextRequests.every(req => req.status === "succeeded")
              ? "done"
              : state.status;
          next[id] = { ...state, approvalRequests: nextRequests, status: nextStatus };
        }
        return next;
      });
    } catch (error) {
      setGlobalError(error instanceof Error ? error.message : String(error));
      setStage("error");
    } finally {
      setApprovalBusyActionId(null);
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5">
      {/* 输入阶段 */}
      {stage === "input" && (
        <div className="rounded-xl border border-amber-300 bg-white shadow-md p-5 space-y-4">
          <h2 className="font-semibold text-slate-800">描述你的 Mod 需求</h2>
          <p className="text-xs text-slate-400">
            用自然语言描述整个 Mod 的内容，AI 会自动规划需要哪些卡牌、遗物、机制，并逐一创建。
          </p>
          <textarea
            value={requirements}
            onChange={e => setRequirements(e.target.value)}
            rows={6}
            placeholder={"例如：\n我想做一个暗法师角色，主题是腐化和献祭。\n包含3张卡牌（攻击、技能、力量各一张），\n2个遗物（战斗开始触发），\n以及一个腐化叠层的 buff 机制。"}
            className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 placeholder:text-slate-300 focus:outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-100 resize-none"
          />
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-500">Mod 项目路径</label>
            <input
              value={projectRoot}
              onChange={e => setProjectRoot(e.target.value)}
              placeholder="E:/STS2mod"
              className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 placeholder:text-slate-300 focus:outline-none focus:border-amber-400 font-mono"
            />
          </div>
          <button
            onClick={startPlanning}
            disabled={!requirements.trim() || !projectRoot.trim()}
            className="w-full py-2.5 rounded-lg bg-amber-500 text-white font-bold text-sm hover:bg-amber-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
          >
            <Sparkles size={15} />
            规划 Mod
          </button>
          {plan && (
            <button
              onClick={() => setStage("review_plan")}
              className="w-full py-2 rounded-lg border border-amber-200 text-amber-600 text-sm hover:bg-amber-50 transition-colors"
            >
              恢复上次规划：{plan.mod_name}
            </button>
          )}
        </div>
      )}

      {/* 规划中 */}
      {stage === "planning" && (
        <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-3">
          <div className="flex items-center gap-2.5">
            <Loader2 size={16} className="text-amber-500 animate-spin" />
            <span className="text-sm font-medium text-slate-600">AI 正在规划 Mod...</span>
          </div>
          {batchLog.length > 0 && <AgentLog lines={batchLog} />}
        </div>
      )}

      {/* 审阅计划 */}
      {stage === "review_plan" && plan && (
        <ReviewPlan
          plan={plan}
          editedItems={editedItems}
          setEditedItems={setEditedItems}
          onConfirm={confirmPlan}
          onReset={reset}
        />
      )}

      {/* 全局错误 */}
      {stage === "error" && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-5 space-y-3">
          <div className="flex items-start gap-2">
            <AlertTriangle size={16} className="text-red-500 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-red-700">规划失败</p>
              {globalError && <pre className="text-xs text-red-600 font-mono mt-1 whitespace-pre-wrap">{globalError}</pre>}
            </div>
          </div>
          <button onClick={reset} className="text-sm text-red-500 hover:text-red-700 flex items-center gap-1">
            <RotateCcw size={13} /> 重试
          </button>
        </div>
      )}

      {/* 执行阶段 + 完成 */}
      {(stage === "executing" || stage === "done") && (
        <ExecutionView
          items={editedItems}
          itemStates={itemStates}
          activeItemId={activeItemId}
          setActiveItemId={setActiveItemId}
          batchLog={batchLog}
          currentBatchStage={currentBatchStage}
          batchStageHistory={batchStageHistory}
          batchResult={batchResult}
          stage={stage}
          projectRoot={projectRoot}
          autoSelectFirst={autoSelectFirst}
          onAutoSelectToggle={() => setAutoSelectFirst(v => !v)}
          onSelectImage={handleSelectImage}
          onGenerateMore={handleGenerateMore}
          onRetryItem={handleRetryItem}
          approvalBusyActionId={approvalBusyActionId}
          onApproveAction={(actionId) => { void handleApprovalAction(actionId, approveApproval); }}
          onRejectAction={(actionId) => { void handleApprovalAction(actionId, (id) => rejectApproval(id)); }}
          onExecuteAction={(actionId) => { void handleApprovalAction(actionId, executeApproval); }}
          onUpdatePrompt={(id, prompt) =>
            updateItem(id, { currentPrompt: prompt })
          }
          onToggleMorePrompt={(id) =>
            applyItemStates(prev => ({
              ...prev,
              [id]: { ...prev[id], showMorePrompt: !prev[id]?.showMorePrompt },
            }))
          }
          onReset={reset}
        />
      )}
    </div>
  );
}

// ── 计划审阅组件 ──────────────────────────────────────────────────────────────

function ReviewPlan({
  plan, editedItems, setEditedItems, onConfirm, onReset,
}: {
  plan: ModPlan;
  editedItems: PlanItem[];
  setEditedItems: (items: PlanItem[]) => void;
  onConfirm: () => void;
  onReset: () => void;
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [uploadPreviews, setUploadPreviews] = useState<Record<string, string>>({});

  function updateItem(id: string, patch: Partial<PlanItem>) {
    setEditedItems(editedItems.map(it => it.id === id ? { ...it, ...patch } : it));
  }

  function handleImageFile(id: string, file: File) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target?.result as string;
      const b64 = dataUrl.split(",")[1];
      setUploadPreviews(p => ({ ...p, [id]: dataUrl }));
      updateItem(id, { provided_image_b64: b64 });
    };
    reader.readAsDataURL(file);
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-amber-300 bg-white shadow-md p-5">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="font-bold text-slate-800">{plan.mod_name}</h2>
            <p className="text-xs text-slate-500 mt-0.5">{plan.summary}</p>
          </div>
          <span className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5 font-medium">
            {editedItems.length} 个资产
          </span>
        </div>

        <div className="space-y-2">
          {editedItems.map(item => (
            <div key={item.id} className="rounded-lg border border-slate-200 bg-slate-50 overflow-hidden">
              <button
                className="w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-slate-100 transition-colors"
                onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
              >
                <span className="text-xs font-medium text-slate-400 bg-slate-200 rounded px-1.5 py-0.5 shrink-0">
                  {TYPE_LABELS[item.type] ?? item.type}
                </span>
                <span className="text-sm font-medium text-slate-700 flex-1">{item.name}</span>
                {item.depends_on.length > 0 && (
                  <span className="text-xs text-slate-400">依赖 {item.depends_on.length}</span>
                )}
                {expandedId === item.id
                  ? <ChevronUp size={13} className="text-slate-400 shrink-0" />
                  : <ChevronDown size={13} className="text-slate-400 shrink-0" />
                }
              </button>

              {expandedId === item.id && (
                <div className="px-3 pb-3 space-y-2 border-t border-slate-200 pt-2.5">
                  <div className="space-y-1">
                    <label className="text-xs text-slate-400">名称（英文）</label>
                    <input
                      value={item.name}
                      onChange={e => updateItem(item.id, { name: e.target.value })}
                      className="w-full bg-white border border-slate-200 rounded px-2 py-1 text-sm focus:outline-none focus:border-amber-400"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-400">描述</label>
                    <textarea
                      value={item.description}
                      onChange={e => updateItem(item.id, { description: e.target.value })}
                      rows={2}
                      className="w-full bg-white border border-slate-200 rounded px-2 py-1 text-sm resize-none focus:outline-none focus:border-amber-400"
                    />
                  </div>
                  {item.needs_image && (
                    <div className="space-y-2">
                      {/* 图片模式切换 */}
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-slate-400">图片来源：</span>
                        <button
                          onClick={() => updateItem(item.id, { provided_image_b64: undefined })}
                          className={cn(
                            "flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium transition-colors",
                            !item.provided_image_b64
                              ? "bg-amber-500 text-white"
                              : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                          )}
                        >
                          <Wand2 size={11} /> AI 生成
                        </button>
                        <button
                          onClick={() => {
                            const input = document.createElement("input");
                            input.type = "file"; input.accept = "image/*";
                            input.onchange = () => { if (input.files?.[0]) handleImageFile(item.id, input.files[0]); };
                            input.click();
                          }}
                          className={cn(
                            "flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium transition-colors",
                            item.provided_image_b64
                              ? "bg-amber-500 text-white"
                              : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                          )}
                        >
                          <Upload size={11} /> 上传图片
                        </button>
                      </div>
                      {/* 上传预览 */}
                      {item.provided_image_b64 && uploadPreviews[item.id] && (
                        <div className="relative w-24 h-24 rounded-lg overflow-hidden border border-amber-300">
                          <img src={uploadPreviews[item.id]} alt="preview" className="w-full h-full object-cover" />
                          <button
                            onClick={() => {
                              updateItem(item.id, { provided_image_b64: undefined });
                              setUploadPreviews(p => { const n = { ...p }; delete n[item.id]; return n; });
                            }}
                            className="absolute top-0.5 right-0.5 w-4 h-4 rounded-full bg-black/60 text-white text-xs flex items-center justify-center hover:bg-red-500"
                          >×</button>
                        </div>
                      )}
                      {/* AI 生成时显示图像描述 */}
                      {!item.provided_image_b64 && (
                        <div className="space-y-1">
                          <label className="text-xs text-slate-400">图像描述（AI 生图用）</label>
                          <textarea
                            value={item.image_description}
                            onChange={e => updateItem(item.id, { image_description: e.target.value })}
                            rows={2}
                            className="w-full bg-white border border-slate-200 rounded px-2 py-1 text-sm resize-none focus:outline-none focus:border-amber-400"
                          />
                        </div>
                      )}
                    </div>
                  )}
                  <div className="space-y-1">
                    <label className="text-xs text-slate-400">技术实现说明（给 Code Agent）</label>
                    <textarea
                      value={item.implementation_notes}
                      onChange={e => updateItem(item.id, { implementation_notes: e.target.value })}
                      rows={3}
                      className="w-full bg-white border border-slate-200 rounded px-2 py-1 text-xs font-mono resize-none focus:outline-none focus:border-amber-400"
                    />
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="flex gap-2 mt-4">
          <button
            onClick={onConfirm}
            className="flex-1 py-2.5 rounded-lg bg-amber-500 text-white font-bold text-sm hover:bg-amber-600 transition-colors"
          >
            确认，开始执行
          </button>
          <button
            onClick={onReset}
            className="py-2.5 px-4 rounded-lg border border-slate-200 text-slate-400 hover:text-slate-600 text-sm transition-colors"
          >
            重来
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 执行视图 ──────────────────────────────────────────────────────────────────

function ExecutionView({
  items, itemStates, activeItemId, setActiveItemId,
  batchLog, currentBatchStage, batchStageHistory, batchResult, stage, projectRoot,
  autoSelectFirst, onAutoSelectToggle,
  onSelectImage, onGenerateMore, onRetryItem, approvalBusyActionId, onApproveAction, onRejectAction, onExecuteAction, onUpdatePrompt, onToggleMorePrompt, onReset,
}: {
  items: PlanItem[];
  itemStates: Record<string, ItemState>;
  activeItemId: string | null;
  setActiveItemId: (id: string) => void;
  batchLog: string[];
  currentBatchStage: string | null;
  batchStageHistory: string[];
  batchResult: { success: number; error: number } | null;
  stage: "executing" | "done";
  projectRoot: string;
  autoSelectFirst: boolean;
  onAutoSelectToggle: () => void;
  onSelectImage: (id: string, idx: number) => void;
  onGenerateMore: (id: string) => void;
  onRetryItem: (id: string) => void;
  approvalBusyActionId: string | null;
  onApproveAction: (actionId: string) => void;
  onRejectAction: (actionId: string) => void;
  onExecuteAction: (actionId: string) => void;
  onUpdatePrompt: (id: string, prompt: string) => void;
  onToggleMorePrompt: (id: string) => void;
  onReset: () => void;
}) {
  const awaitingCount = items.filter(it => itemStates[it.id]?.status === "awaiting_selection").length;
  const approvalCount = items.filter(it => itemStates[it.id]?.status === "approval_pending").length;
  const activeItem = items.find(it => it.id === activeItemId);
  const activeState = activeItemId ? itemStates[activeItemId] : null;

  return (
    <div className="grid grid-cols-[220px_minmax(0,1fr)] gap-4 items-start">
      {/* 左：资产列表 */}
      <div className="rounded-xl border border-slate-200 bg-white p-3 space-y-1 sticky top-24">
        <div className="flex items-center justify-between px-1 mb-2">
          <p className="text-xs font-medium text-slate-400">资产列表</p>
          <button
            onClick={onAutoSelectToggle}
            className={cn(
              "flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium transition-colors",
              autoSelectFirst ? "bg-amber-500 text-white" : "bg-slate-100 text-slate-400 hover:bg-slate-200"
            )}
            title="自动选用第一张生成图，无需手动确认"
          >
            <Wand2 size={10} />
            自动选图
          </button>
        </div>

        {awaitingCount > 0 && !autoSelectFirst && (
          <div className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-2.5 py-1.5 mb-2 font-medium">
            {awaitingCount} 个图片等待选择
          </div>
        )}
        {approvalCount > 0 && (
          <div className="text-xs text-violet-600 bg-violet-50 border border-violet-200 rounded-lg px-2.5 py-1.5 mb-2 font-medium">
            {approvalCount} 个资产等待审批
          </div>
        )}

        {items.map(item => {
          const state = itemStates[item.id];
          const status: ItemStatus = state?.status ?? "pending";
          const isActive = item.id === activeItemId;
          const needsAction = status === "awaiting_selection";

          return (
            <button
              key={item.id}
              onClick={() => setActiveItemId(item.id)}
              className={cn(
                "w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-left transition-colors",
                isActive ? "bg-amber-50 border border-amber-300" : "hover:bg-slate-50 border border-transparent",
                needsAction && !isActive && "border-amber-200 bg-amber-50/50",
              )}
            >
              <span className="shrink-0">{STATUS_ICONS[status]}</span>
              <div className="flex-1 min-w-0">
                <p className={cn("text-xs font-medium truncate", isActive ? "text-amber-700" : "text-slate-700")}>
                  {item.name}
                </p>
                <p className="text-xs text-slate-400">{TYPE_LABELS[item.type] ?? item.type}</p>
              </div>
              {needsAction && (
                <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0 animate-pulse" />
              )}
            </button>
          );
        })}

        {/* 全局进度日志（折叠） */}
        {(batchLog.length > 0 || currentBatchStage) && stage === "executing" && (
          <div className="mt-2 pt-2 border-t border-slate-100">
            <StageStatus current={currentBatchStage} history={batchStageHistory} />
            <div className="max-h-28 overflow-y-auto space-y-0.5">
              {batchLog.slice(-8).map((line, i) => (
                <p key={i} className="text-xs text-slate-400 font-mono leading-relaxed truncate">{line}</p>
              ))}
            </div>
          </div>
        )}

        {stage === "done" && batchResult && (
          <div className="mt-2 pt-2 border-t border-slate-100 space-y-2">
            {approvalCount > 0 ? (
              <p className="text-xs text-violet-600 font-medium px-1">等待审批通过后继续执行</p>
            ) : batchResult.error === 0 ? (
              <p className="text-xs text-green-600 font-medium px-1">✓ 全部完成</p>
            ) : (
              <p className="text-xs text-red-500 px-1">
                {batchResult.success} 成功 / {batchResult.error} 失败
              </p>
            )}
            {approvalCount === 0 && <BuildDeploy projectRoot={projectRoot} />}
            <button
              onClick={onReset}
              className="w-full py-1.5 rounded-lg border border-slate-200 text-slate-400 hover:text-amber-600 hover:border-amber-300 text-xs transition-colors flex items-center justify-center gap-1"
            >
              <RotateCcw size={11} /> 新建 Mod
            </button>
          </div>
        )}
      </div>

      {/* 右：当前 item 详情 */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 min-h-[300px]">
        {!activeItem || !activeState ? (
          <div className="space-y-3">
            {batchLog.length > 0
              ? <AgentLog lines={batchLog} />
              : <div className="flex items-center justify-center h-48 text-slate-300 text-sm">从左侧选择一个资产查看详情</div>
            }
          </div>
        ) : (
          <ItemDetailPanel
            item={activeItem}
            state={activeState}
            onSelectImage={(idx) => onSelectImage(activeItem.id, idx)}
            onGenerateMore={() => onGenerateMore(activeItem.id)}
            onRetryItem={() => onRetryItem(activeItem.id)}
            approvalBusyActionId={approvalBusyActionId}
            onApproveAction={onApproveAction}
            onRejectAction={onRejectAction}
            onExecuteAction={onExecuteAction}
            onUpdatePrompt={(p) => onUpdatePrompt(activeItem.id, p)}
            onToggleMorePrompt={() => onToggleMorePrompt(activeItem.id)}
          />
        )}
      </div>
    </div>
  );
}

// ── 单个资产详情面板 ──────────────────────────────────────────────────────────

function ItemDetailPanel({
  item, state,
  onSelectImage, onGenerateMore, onRetryItem, approvalBusyActionId, onApproveAction, onRejectAction, onExecuteAction, onUpdatePrompt, onToggleMorePrompt,
}: {
  item: PlanItem;
  state: ItemState;
  onSelectImage: (idx: number) => void;
  onGenerateMore: () => void;
  onRetryItem: () => void;
  approvalBusyActionId: string | null;
  onApproveAction: (actionId: string) => void;
  onRejectAction: (actionId: string) => void;
  onExecuteAction: (actionId: string) => void;
  onUpdatePrompt: (p: string) => void;
  onToggleMorePrompt: () => void;
}) {
  const [showTrace, setShowTrace] = useState(false);

  return (
    <div className="space-y-4">
      {/* 标题行 */}
      <div className="flex items-center gap-3">
        <span className="text-xs font-medium text-slate-400 bg-slate-100 rounded px-1.5 py-0.5">
          {TYPE_LABELS[item.type] ?? item.type}
        </span>
        <h3 className="font-bold text-slate-800">{item.name}</h3>
        <span className={cn(
          "ml-auto text-xs px-2 py-0.5 rounded-full font-medium",
          state.status === "done"               ? "bg-green-100 text-green-700" :
          state.status === "error"              ? "bg-red-100 text-red-600" :
          state.status === "awaiting_selection" ? "bg-amber-100 text-amber-700" :
          state.status === "approval_pending"   ? "bg-violet-100 text-violet-700" :
          state.status === "code_generating"    ? "bg-blue-100 text-blue-600" :
                                                  "bg-slate-100 text-slate-500"
        )}>
          {STATUS_LABELS[state.status]}
        </span>
      </div>

      {/* 进度日志 */}
      <StageStatus current={state.currentStage} history={state.stageHistory} isComplete={state.status === "done"} />
      {state.progress.length > 0 && (
        <AgentLog lines={state.progress} />
      )}

      {state.status === "approval_pending" && (
        <ApprovalPanel
          summary={state.approvalSummary}
          requests={state.approvalRequests}
          busyActionId={approvalBusyActionId}
          onApprove={onApproveAction}
          onReject={onRejectAction}
          onExecute={onExecuteAction}
        />
      )}

      {/* 图片画廊（等待选择时） */}
      {state.images.length > 0 && state.status !== "done" && (
        <div className="space-y-3">
          <p className="text-xs font-medium text-slate-500">
            {state.status === "awaiting_selection" ? "请选择一张图片" : "已选图片"}
          </p>
          <div className="flex flex-wrap gap-3">
            {state.images.map((b64, i) => (
              <div
                key={i}
                className="group relative rounded-lg overflow-hidden border border-slate-200 hover:border-amber-400 transition-colors"
                style={{ width: state.images.length === 1 ? "240px" : "180px" }}
              >
                <img src={`data:image/png;base64,${b64}`} alt={`图 ${i + 1}`} className="w-full h-auto block" />
                {state.status === "awaiting_selection" && (
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <button
                      onClick={() => onSelectImage(i)}
                      className="py-1.5 px-4 rounded-lg bg-amber-500 text-white font-bold text-sm hover:bg-amber-400 transition-colors shadow-lg"
                    >
                      用这张
                    </button>
                  </div>
                )}
                <div className="absolute top-1 left-1 w-5 h-5 rounded-full bg-black/50 text-white text-xs flex items-center justify-center font-bold">
                  {i + 1}
                </div>
              </div>
            ))}
          </div>

          {/* 再来一张 */}
          {state.status === "awaiting_selection" && (
            <div className="space-y-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => onSelectImage(0)}
                className="w-full py-1.5 rounded-lg bg-amber-500 text-white text-sm font-bold hover:bg-amber-600 transition-colors"
              >
                选第一张
              </button>
              <button
                onClick={onToggleMorePrompt}
                className="text-xs text-slate-400 hover:text-amber-600 flex items-center gap-1 transition-colors"
              >
                {state.showMorePrompt ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                {state.showMorePrompt ? "收起" : "修改提示词"}
              </button>
              {state.showMorePrompt && (
                <textarea
                  value={state.currentPrompt}
                  onChange={e => onUpdatePrompt(e.target.value)}
                  rows={3}
                  className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-xs font-mono resize-none focus:outline-none focus:border-amber-400"
                />
              )}
              <button
                onClick={onGenerateMore}
                className="w-full py-1.5 rounded-lg border border-amber-300 text-amber-600 text-sm hover:bg-amber-50 transition-colors"
              >
                再来一张
              </button>
            </div>
          )}
        </div>
      )}

      {/* Code Agent 日志 */}
      {state.agentLog.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-slate-500">Code Agent</p>
          <AgentLog lines={state.agentLog} />
        </div>
      )}

      {/* 完成提示 */}
      {state.status === "done" && (
        <p className="text-sm text-green-600 font-medium">✓ {item.name} 创建完成</p>
      )}

      {/* 错误 */}
      {state.status === "error" && state.error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 space-y-2">
          <div className="flex items-start gap-2">
            <AlertTriangle size={14} className="text-red-500 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-red-700">执行失败</p>
              <pre className="text-xs text-red-600 font-mono mt-1 whitespace-pre-wrap break-all">{state.error}</pre>
            </div>
          </div>
          <button
            onClick={onRetryItem}
            className="w-full py-1.5 rounded-lg bg-red-500 text-white text-sm font-bold hover:bg-red-600 transition-colors flex items-center justify-center gap-1"
          >
            <RotateCcw size={13} /> 重新生成此资产
          </button>
          {state.errorTrace && (
            <>
              <button
                onClick={() => setShowTrace(v => !v)}
                className="text-xs text-red-400 hover:text-red-600 flex items-center gap-1"
              >
                {showTrace ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                {showTrace ? "收起" : "展开"} Traceback
              </button>
              {showTrace && (
                <pre className="text-xs text-red-500/80 font-mono whitespace-pre-wrap break-all max-h-48 overflow-y-auto bg-red-100/30 rounded p-2">
                  {state.errorTrace}
                </pre>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
