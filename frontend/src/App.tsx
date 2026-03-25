import { useState, useCallback, useRef, useEffect } from "react";
import { Swords, Settings, RotateCcw, ChevronDown, ChevronUp, Loader2, AlertTriangle } from "lucide-react";
import { AgentLog } from "./components/AgentLog";
import { ApprovalPanel } from "./components/ApprovalPanel";
import { StageStatus } from "./components/StageStatus";
import { SettingsPanel } from "./components/SettingsPanel";
import { BuildDeploy } from "./components/BuildDeploy";
import { approveApproval, executeApproval, rejectApproval, type ApprovalRequest } from "./lib/approvals";
import { WorkflowSocket } from "./lib/ws";
import { cn } from "./lib/utils";
import BatchMode from "./pages/BatchMode";
import LogAnalysis from "./pages/LogAnalysis";
import ModEditor from "./pages/ModEditor";

type AssetType = "card" | "card_fullscreen" | "relic" | "power" | "character";
type Stage = "input" | "confirm_prompt" | "generating_image" | "pick_image" | "agent_running" | "approval_pending" | "done" | "error";

const ASSET_TYPES: { value: AssetType; label: string; desc: string; imgHint: string }[] = [
  { value: "card",            label: "卡牌",     desc: "普通卡牌",     imgHint: "横向图，建议 250×190 或更大 → 自动生成 ×2（小图 + 大图）" },
  { value: "card_fullscreen", label: "全画面卡", desc: "全画面卡牌",   imgHint: "竖向图，建议 250×350 或更大 → 自动生成 ×2（小图 + 大图）" },
  { value: "relic",           label: "遗物",     desc: "遗物",         imgHint: "方形图，主体居中 → 自动抠图，生成 ×3（图标 94×94 + 描边 + 大图 256×256）" },
  { value: "power",           label: "Power",    desc: "技能/状态图标", imgHint: "方形图标 → 自动抠图，生成 ×2（64×64 + 256×256）" },
  { value: "character",       label: "角色",     desc: "角色",         imgHint: "人物立绘，方形或竖向 → 自动抠图，生成 ×4（图标 + 选角图 + 锁定版 + 地图标记）" },
];

const PRESETS: { label: string; assetType: AssetType; assetName: string; description: string }[] = [
  {
    label: "BloodLance",
    assetType: "card",
    assetName: "BloodLance",
    description: "攻击牌，费用1，造成7点伤害；如果目标身上有中毒层数，额外造成等于中毒层数的伤害。升级后基础伤害提升到10。",
  },
  {
    label: "攻击卡",
    assetType: "card",
    assetName: "DarkBlade",
    description: "一把暗黑匕首，造成8点伤害，升级后造成12点伤害",
  },
  {
    label: "遗物",
    assetType: "relic",
    assetName: "FangedGrimoire",
    description: "每次造成伤害时，获得2点格挡。稀有度：普通",
  },
  {
    label: "Power",
    assetType: "power",
    assetName: "CorruptionBuff",
    description: "腐化叠层 buff：每叠加1层，回合结束时额外造成1点伤害，最多叠加10层",
  },
];

const ORDER: Stage[] = ["input", "confirm_prompt", "generating_image", "pick_image", "agent_running", "approval_pending", "done"];
function si(stage: Stage) {
  const i = ORDER.indexOf(stage);
  return i === -1 ? ORDER.indexOf("agent_running") : i;
}

type AppTab = "single" | "batch" | "edit" | "log";

export default function App() {
  const [activeTab, setActiveTab] = useState<AppTab>("single");
  const [stage, setStage] = useState<Stage>("input");
  const stageRef = useRef<Stage>("input");
  function updateStage(s: Stage) { stageRef.current = s; setStage(s); }

  const [assetType, setAssetType] = useState<AssetType>("relic");
  const [assetName, setAssetName] = useState("");
  const [description, setDescription] = useState("");
  const [projectRoot, setProjectRoot] = useState("");

  const [images, setImages] = useState<string[]>([]);
  const [pendingSlots, setPendingSlots] = useState(0);
  const batchOffsetRef = useRef(0);
  const [promptPreview, setPromptPreview] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [promptFallbackWarn, setPromptFallbackWarn] = useState<string | null>(null);
  const [currentPrompt, setCurrentPrompt] = useState("");
  const [showMorePrompt, setShowMorePrompt] = useState(false);

  const [genLog, setGenLog] = useState<string[]>([]);
  const [agentLog, setAgentLog] = useState<string[]>([]);
  const [flowStageCurrent, setFlowStageCurrent] = useState<string | null>(null);
  const [flowStageHistory, setFlowStageHistory] = useState<string[]>([]);
  const [agentStageCurrent, setAgentStageCurrent] = useState<string | null>(null);
  const [agentStageHistory, setAgentStageHistory] = useState<string[]>([]);
  const [approvalSummary, setApprovalSummary] = useState("");
  const [approvalRequests, setApprovalRequests] = useState<ApprovalRequest[]>([]);
  const [approvalBusyActionId, setApprovalBusyActionId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [errorTrace, setErrorTrace] = useState<string | null>(null);
  const [socket, setSocket] = useState<WorkflowSocket | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [autoMode, setAutoMode] = useState(false);
  const autoModeRef = useRef(false);
  const [imageMode, setImageMode] = useState<"ai" | "upload">("ai");
  const [uploadedImageB64, setUploadedImageB64] = useState<string>("");
  const [uploadedImageName, setUploadedImageName] = useState<string>("");
  const [uploadedImagePreview, setUploadedImagePreview] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  // 启动时从 config 读默认项目路径
  useEffect(() => {
    fetch("/api/config").then(r => r.json()).then(cfg => {
      if (cfg?.default_project_root && !projectRoot) {
        setProjectRoot(cfg.default_project_root);
      }
    }).catch(() => {});
  }, []);

  const appendGen   = useCallback((m: string) => setGenLog(p => [...p, m]), []);
  const appendAgent = useCallback((m: string) => setAgentLog(p => [...p, m]), []);
  const pushStage = useCallback((scope: string, message: string) => {
    if (scope === "agent") {
      setAgentStageCurrent(message);
      setAgentStageHistory(prev => prev[prev.length - 1] === message ? prev : [...prev, message]);
      return;
    }
    setFlowStageCurrent(message);
    setFlowStageHistory(prev => prev[prev.length - 1] === message ? prev : [...prev, message]);
  }, []);

  const step = si(stage);

  async function startWorkflow() {
    if (!assetName.trim() || !description.trim() || !projectRoot.trim()) return;
    setGenLog([]);
    setAgentLog([]);
    setFlowStageCurrent(null);
    setFlowStageHistory([]);
    setAgentStageCurrent(null);
    setAgentStageHistory([]);
    setApprovalSummary("");
    setApprovalRequests([]);
    setApprovalBusyActionId(null);
    setImages([]);
    setPendingSlots(0);
    batchOffsetRef.current = 0;
    setPromptPreview("");
    setNegativePrompt("");
    setPromptFallbackWarn(null);
    setCurrentPrompt("");
    setShowMorePrompt(false);
    setErrorMsg(null);
    setErrorTrace(null);
    // upload 模式直接跳过生图阶段；ai 模式先进 generating_image
    if (imageMode !== "upload") updateStage("generating_image");

    const ws = new WorkflowSocket();
    setSocket(ws);
    ws.on("stage_update",   (d: any) => pushStage(d.scope, d.message));
    ws.on("progress",       (d: any) => appendGen(`${d.message}`));
    ws.on("agent_stream",   (d: any) => appendAgent(d.chunk));
    ws.on("error",          (d: any) => { setErrorMsg(d.message); setErrorTrace(d.traceback || null); updateStage("error"); });
    ws.on("approval_pending", (d: any) => {
      setApprovalSummary(d.summary || "");
      setApprovalRequests(d.requests || []);
      appendAgent("已生成待审批动作，等待用户审批后继续执行。");
      updateStage("approval_pending");
    });
    ws.on("prompt_preview", (d: any) => {
      if (autoModeRef.current) {
        ws.send({ action: "confirm", prompt: d.prompt, negative_prompt: d.negative_prompt || "" });
        appendGen("自动模式：跳过 prompt 确认");
        return;
      }
      setPromptPreview(d.prompt);
      setCurrentPrompt(d.prompt);
      setNegativePrompt(d.negative_prompt || "");
      setPromptFallbackWarn(d.fallback_warning || null);
      updateStage("confirm_prompt");
    });
    ws.on("image_ready", (d: any) => {
      setImages(prev => {
        const next = [...prev];
        next[batchOffsetRef.current + d.index] = d.image;
        return next;
      });
      setPendingSlots(0);
      setCurrentPrompt(d.prompt);
      setShowMorePrompt(false);
      if (autoModeRef.current) {
        appendGen("自动模式：自动选第 1 张图");
        ws.send({ action: "select", index: 0 });
        updateStage("agent_running");
        return;
      }
      updateStage("pick_image");
    });
    ws.on("done", (d: any) => {
      appendAgent(d.success ? "✓ 构建成功！" : "✗ 构建失败");
      updateStage("done");
    });

    try {
      await ws.waitOpen();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
      updateStage("error");
      return;
    }
    if (imageMode === "upload" && uploadedImageB64) {
      updateStage("agent_running");
      ws.send({ action: "start", asset_type: assetType, asset_name: assetName, description, project_root: projectRoot, provided_image_b64: uploadedImageB64, provided_image_name: uploadedImageName });
    } else {
      ws.send({ action: "start", asset_type: assetType, asset_name: assetName, description, project_root: projectRoot });
    }
  }

  function handleConfirmPrompt() {
    if (!socket) return;
    updateStage("generating_image");
    socket.send({ action: "confirm", prompt: promptPreview, negative_prompt: negativePrompt });
  }

  function handleSelectImage(index: number) {
    if (!socket) return;
    updateStage("agent_running");
    socket.send({ action: "select", index });
  }

  function handleGenerateMore() {
    if (!socket) return;
    batchOffsetRef.current = images.length;
    setPendingSlots(1);
    setShowMorePrompt(false);
    socket.send({ action: "generate_more", prompt: currentPrompt, negative_prompt: negativePrompt || undefined });
  }

  function handleImageFile(file: File) {
    setUploadedImageName(file.name);
    const reader = new FileReader();
    reader.onload = ev => {
      const dataUrl = ev.target?.result as string;
      setUploadedImagePreview(dataUrl);
      // 去掉 "data:image/png;base64," 前缀，只保留纯 base64
      setUploadedImageB64(dataUrl.split(",")[1] ?? "");
    };
    reader.readAsDataURL(file);
  }

  function reset() {
    socket?.close();
    setSocket(null);
    updateStage("input");
    setUploadedImageB64("");
    setUploadedImageName("");
    setUploadedImagePreview(null);
    setImages([]);
    setPendingSlots(0);
    batchOffsetRef.current = 0;
    setGenLog([]);
    setAgentLog([]);
    setFlowStageCurrent(null);
    setFlowStageHistory([]);
    setAgentStageCurrent(null);
    setAgentStageHistory([]);
    setApprovalSummary("");
    setApprovalRequests([]);
    setApprovalBusyActionId(null);
    setPromptPreview("");
    setNegativePrompt("");
    setPromptFallbackWarn(null);
    setCurrentPrompt("");
    setShowMorePrompt(false);
    setErrorMsg(null);
    setErrorTrace(null);
  }

  // 判断错误发生在哪个阶段，用于在对应步骤内显示
  const errorInStep2 = stage === "error" && step <= 2;
  const errorInStep3 = stage === "error" && step > 2;

  async function handleApprovalAction(
    actionId: string,
    action: (id: string) => Promise<ApprovalRequest>,
  ) {
    setApprovalBusyActionId(actionId);
    try {
      const updated = await action(actionId);
      setApprovalRequests(prev => prev.map(req => req.action_id === actionId ? updated : req));
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : String(error));
      updateStage("error");
    } finally {
      setApprovalBusyActionId(null);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-slate-200 px-6 py-3 flex items-center justify-between bg-white/80 backdrop-blur-sm shadow-sm">
        <div className="flex items-center gap-2">
          <Swords className="text-amber-600" size={22} />
          <span className="font-bold tracking-wide text-amber-600 text-lg">AgentTheSpire</span>
        </div>
        <button onClick={() => setSettingsOpen(true)} className="flex items-center gap-1.5 py-1.5 px-3 rounded-lg bg-slate-100 hover:bg-amber-50 hover:text-amber-700 text-slate-500 hover:border-amber-300 border border-transparent transition-colors text-sm font-medium">
          <Settings size={14} />
          设置
        </button>
      </header>

      {/* Tab 切换 */}
      <div className="px-6 pt-4 flex gap-1 border-b border-slate-200 bg-white">
        <button
          onClick={() => setActiveTab("single")}
          className={cn(
            "px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors",
            activeTab === "single"
              ? "border-amber-500 text-amber-600 bg-amber-50"
              : "border-transparent text-slate-400 hover:text-slate-600"
          )}
        >
          单资产
        </button>
        <button
          onClick={() => setActiveTab("batch")}
          className={cn(
            "px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors",
            activeTab === "batch"
              ? "border-amber-500 text-amber-600 bg-amber-50"
              : "border-transparent text-slate-400 hover:text-slate-600"
          )}
        >
          Mod 规划
        </button>
        <button
          onClick={() => setActiveTab("edit")}
          className={cn(
            "px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors",
            activeTab === "edit"
              ? "border-amber-500 text-amber-600 bg-amber-50"
              : "border-transparent text-slate-400 hover:text-slate-600"
          )}
        >
          修改 Mod
        </button>
        <button
          onClick={() => setActiveTab("log")}
          className={cn(
            "px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors",
            activeTab === "log"
              ? "border-amber-500 text-amber-600 bg-amber-50"
              : "border-transparent text-slate-400 hover:text-slate-600"
          )}
        >
          崩溃分析
        </button>
      </div>

      {activeTab === "batch" && (
        <div className="px-6 py-6">
          <BatchMode />
        </div>
      )}

      {activeTab === "edit" && (
        <div className="px-6 py-6">
          <ModEditor />
        </div>
      )}

      {activeTab === "log" && (
        <div className="px-6 py-6">
          <LogAnalysis />
        </div>
      )}

      {activeTab === "single" && (
      <main className="px-6 py-6 grid grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)] gap-5 items-start">

        {/* ── 左栏：Step 1 输入 ── */}
        <Step num={1} title="描述设计" active={step === 0} done={step > 0}>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-500">资产类型</label>
              <div className="flex gap-2 flex-wrap">
                {ASSET_TYPES.map((t) => (
                  <button
                    key={t.value}
                    disabled={step > 0}
                    onClick={() => setAssetType(t.value)}
                    className={cn(
                      "py-1 px-3 rounded-md border text-sm transition-all",
                      assetType === t.value
                        ? "border-amber-500 bg-amber-50 text-amber-700 font-medium"
                        : "border-slate-200 hover:border-amber-300 text-slate-500 hover:text-slate-700",
                      step > 0 && "opacity-50 cursor-not-allowed"
                    )}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
              <p className="text-xs text-slate-400">{ASSET_TYPES.find(t => t.value === assetType)?.imgHint}</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-500">资产名称（英文）</label>
                <input
                  value={assetName} disabled={step > 0}
                  onChange={(e) => setAssetName(e.target.value)}
                  placeholder="DarkBlade"
                  className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 placeholder:text-slate-300 focus:outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-100 disabled:opacity-50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-500">Mod 项目路径</label>
                <input
                  value={projectRoot} disabled={step > 0}
                  onChange={(e) => setProjectRoot(e.target.value)}
                  placeholder="E:/STS2mod"
                  className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 placeholder:text-slate-300 focus:outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-100 font-mono disabled:opacity-50"
                />
              </div>
            </div>

            {step === 0 && (
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-500">快速示例</label>
                <div className="flex gap-1.5 flex-wrap">
                  {PRESETS.map((p) => (
                    <button
                      key={p.label}
                      onClick={() => { setAssetType(p.assetType); setAssetName(p.assetName); setDescription(p.description); }}
                      className="px-2.5 py-1 rounded-md border border-slate-200 text-xs text-slate-500 hover:border-amber-300 hover:text-amber-600 transition-colors"
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-500">设计描述</label>
              <textarea
                value={description} disabled={step > 0}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
                placeholder="描述这个资产的外观、效果、数值……"
                className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 placeholder:text-slate-300 focus:outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-100 resize-none disabled:opacity-50"
              />
            </div>

            {step === 0 ? (
              <div className="space-y-3">
                {/* 图片来源选择 */}
                <div className="space-y-2">
                  <label className="text-xs font-medium text-slate-500">图片来源</label>
                  <div className="flex gap-2">
                    {(["ai", "upload"] as const).map(mode => (
                      <button
                        key={mode}
                        onClick={() => setImageMode(mode)}
                        className={cn(
                          "flex-1 py-1.5 rounded-lg border text-xs font-medium transition-all",
                          imageMode === mode
                            ? "border-amber-500 bg-amber-50 text-amber-700"
                            : "border-slate-200 text-slate-500 hover:border-amber-300"
                        )}
                      >
                        {mode === "ai" ? "✦ AI 生图" : "↑ 自定义图片"}
                      </button>
                    ))}
                  </div>

                  {/* 拖拽上传区 */}
                  {imageMode === "upload" && (<>
                    <div
                      onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                      onDragLeave={() => setDragOver(false)}
                      onDrop={e => {
                        e.preventDefault();
                        setDragOver(false);
                        const file = e.dataTransfer.files[0];
                        if (file) handleImageFile(file);
                      }}
                      onClick={() => {
                        const input = document.createElement("input");
                        input.type = "file";
                        input.accept = "image/*";
                        input.onchange = (e) => {
                          const file = (e.target as HTMLInputElement).files?.[0];
                          if (file) handleImageFile(file);
                        };
                        input.click();
                      }}
                      className={cn(
                        "relative rounded-lg border-2 border-dashed cursor-pointer transition-colors overflow-hidden",
                        dragOver ? "border-amber-400 bg-amber-50" : "border-slate-200 hover:border-amber-300 bg-slate-50",
                        uploadedImagePreview ? "h-32" : "h-20"
                      )}
                    >
                      {uploadedImagePreview ? (
                        <>
                          <img src={uploadedImagePreview} alt="preview" className="w-full h-full object-contain" />
                          <div className="absolute inset-0 bg-black/30 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity">
                            <span className="text-white text-xs font-medium">点击替换</span>
                          </div>
                        </>
                      ) : (
                        <div className="flex flex-col items-center justify-center h-full gap-1">
                          <span className="text-slate-400 text-lg">↑</span>
                          <span className="text-xs text-slate-400">拖拽或点击选择图片</span>
                        </div>
                      )}
                    </div>
                    {uploadedImageName && (
                      <p className="text-xs text-slate-400 truncate">{uploadedImageName}</p>
                    )}
                  </>)}
                </div>

                <button
                  onClick={startWorkflow}
                  disabled={!assetName.trim() || !description.trim() || !projectRoot.trim() || (imageMode === "upload" && !uploadedImageB64)}
                  className="w-full py-2.5 rounded-lg bg-amber-500 text-white font-bold text-sm hover:bg-amber-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  开始生成
                </button>

                {imageMode === "ai" && (
                  <label className="flex items-center gap-2 cursor-pointer select-none">
                    <div
                      onClick={() => { const v = !autoMode; setAutoMode(v); autoModeRef.current = v; }}
                      className={cn(
                        "relative w-8 h-4 rounded-full transition-colors shrink-0",
                        autoMode ? "bg-amber-500" : "bg-slate-200"
                      )}
                    >
                      <span className={cn(
                        "absolute top-0.5 w-3 h-3 rounded-full bg-white shadow transition-transform",
                        autoMode ? "translate-x-4" : "translate-x-0.5"
                      )} />
                    </div>
                    <span className="text-xs text-slate-400">自动模式（跳过确认，自动选第 1 张图）</span>
                  </label>
                )}
              </div>
            ) : (
              <button onClick={reset} className="w-full py-2 rounded-lg border border-slate-200 text-slate-400 hover:text-amber-600 hover:border-amber-300 text-sm transition-colors flex items-center justify-center gap-1.5">
                <RotateCcw size={13} />
                重新开始
              </button>
            )}
          </div>
        </Step>

        {/* ── 右栏：Steps 2-4 ── */}
        <div className="space-y-4">

          {/* Step 2: 生成图像 */}
          <Step num={2} title="生成图像" active={step >= 1 && step <= 3} done={step > 3}>
            {step === 0 && <p className="text-sm text-slate-300">等待开始…</p>}

            {/* Prompt 确认 */}
            {step === 1 && (
              <div className="space-y-3">
                {promptFallbackWarn && (
                  <div className="flex items-start gap-2 rounded-lg border border-yellow-300 bg-yellow-50 px-3 py-2">
                    <span className="text-yellow-600 font-bold text-xs shrink-0">⚠ AI 优化失败</span>
                    <p className="text-xs text-yellow-700 font-mono break-all">{promptFallbackWarn}</p>
                  </div>
                )}
                <p className="text-xs font-medium text-slate-500">AI 生成的图像提示词（可修改后确认）</p>
                <textarea
                  value={promptPreview} onChange={e => setPromptPreview(e.target.value)}
                  rows={6}
                  className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-100 resize-none font-mono"
                />
                {negativePrompt && (
                  <>
                    <p className="text-xs font-medium text-slate-500">Negative prompt</p>
                    <textarea
                      value={negativePrompt} onChange={e => setNegativePrompt(e.target.value)}
                      rows={2}
                      className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:border-amber-400 resize-none font-mono"
                    />
                  </>
                )}
                <button onClick={handleConfirmPrompt} className="w-full py-2.5 rounded-lg bg-amber-500 text-white font-bold text-sm hover:bg-amber-600 transition-colors">
                  确认，开始生图
                </button>
              </div>
            )}

            {/* 生成中 */}
            {step === 2 && !errorInStep2 && (
              <div className="space-y-3">
                <StageStatus current={flowStageCurrent} history={flowStageHistory} />
                {genLog.length > 0
                  ? <AgentLog lines={genLog} />
                  : (
                    <div className="flex items-center gap-2.5 py-3">
                      <Loader2 size={16} className="text-amber-500 animate-spin" />
                      <span className="text-sm text-slate-400">正在生成图像…</span>
                    </div>
                  )
                }
              </div>
            )}

            {/* 图片生成阶段的错误 */}
            {errorInStep2 && (
              <ErrorBlock message={errorMsg} traceback={errorTrace} log={genLog} onReset={reset} />
            )}

            {/* 图片画廊 */}
            {step === 3 && (
              <div className="space-y-4">
                <StageStatus current={flowStageCurrent} history={flowStageHistory} />
                {genLog.length > 0 && <AgentLog lines={genLog} />}

                <div className="flex flex-wrap gap-3">
                  {images.map((b64, i) => (
                    <div
                      key={i}
                      className="group relative rounded-lg overflow-hidden border border-slate-200 bg-slate-100 hover:border-amber-400 transition-colors"
                      style={{ width: images.length === 1 ? "280px" : "200px" }}
                    >
                      <img
                        src={`data:image/png;base64,${b64}`}
                        alt={`生成图 ${i + 1}`}
                        className="w-full h-auto block"
                      />
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <button
                          onClick={() => handleSelectImage(i)}
                          className="py-1.5 px-4 rounded-lg bg-amber-500 text-white font-bold text-sm hover:bg-amber-400 transition-colors shadow-lg"
                        >
                          用这张
                        </button>
                      </div>
                      <div className="absolute top-1.5 left-1.5 w-5 h-5 rounded-full bg-black/50 text-white text-xs flex items-center justify-center font-bold">
                        {i + 1}
                      </div>
                    </div>
                  ))}
                  {Array.from({ length: pendingSlots }, (_, i) => (
                    <div
                      key={`pending-${i}`}
                      className="rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 flex items-center justify-center"
                      style={{ width: "200px", minHeight: "150px" }}
                    >
                      <Loader2 size={20} className="text-amber-400 animate-spin" />
                    </div>
                  ))}
                </div>

                {/* 再来一张 */}
                <div className="space-y-2 pt-2 border-t border-slate-100">
                  <button
                    onClick={() => setShowMorePrompt(v => !v)}
                    className="text-xs text-slate-400 hover:text-amber-600 transition-colors flex items-center gap-1"
                  >
                    {showMorePrompt ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                    {showMorePrompt ? "收起" : "修改提示词"}
                  </button>
                  {showMorePrompt && (
                    <textarea
                      value={currentPrompt}
                      onChange={e => setCurrentPrompt(e.target.value)}
                      rows={4}
                      className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-100 resize-none font-mono"
                    />
                  )}
                  <button
                    onClick={handleGenerateMore}
                    className="w-full py-2 rounded-lg border border-amber-400 text-amber-600 font-medium text-sm hover:bg-amber-50 transition-colors"
                  >
                    再来一张
                  </button>
                </div>
              </div>
            )}
          </Step>

          {/* Step 3: Code Agent */}
          <Step num={3} title="Code Agent / 审批" active={(step >= 4 && step <= 5) || errorInStep3} done={stage === "done" && !errorInStep3}>
            {step >= 4 && !errorInStep3 && (
              <div className="space-y-3">
                {stage === "approval_pending" ? (
                  <ApprovalPanel
                    summary={approvalSummary}
                    requests={approvalRequests}
                    busyActionId={approvalBusyActionId}
                    onApprove={(actionId) => { void handleApprovalAction(actionId, approveApproval); }}
                    onReject={(actionId) => { void handleApprovalAction(actionId, (id) => rejectApproval(id)); }}
                    onExecute={(actionId) => { void handleApprovalAction(actionId, executeApproval); }}
                    onProceed={() => { socket?.send({ action: "approve_all" }); }}
                  />
                ) : (
                  <>
                    <StageStatus current={agentStageCurrent} history={agentStageHistory} isComplete={stage === "done"} />
                    {agentLog.length > 0 ? (
                      <AgentLog lines={agentLog} />
                    ) : (
                      <div className="flex items-center gap-2.5 py-3">
                        <Loader2 size={16} className="text-amber-500 animate-spin" />
                        <span className="text-sm text-slate-400">Code Agent 执行中…</span>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {/* Code Agent 阶段的错误：内联显示完整错误 + 之前的 agent 日志 */}
            {errorInStep3 && (
              <ErrorBlock message={errorMsg} traceback={errorTrace} log={agentLog} onReset={reset} />
            )}

            {step < 4 && !errorInStep3 && <p className="text-sm text-slate-300">等待选择图片…</p>}
          </Step>

          {/* Step 4: 完成 */}
          <Step num={4} title="完成" active={stage === "approval_pending" || stage === "done"} done={false}>
            {stage === "done" ? (
              <div className="space-y-3">
                <p className="text-sm text-green-600 font-medium">✓ Code Agent 完成</p>
                <BuildDeploy
                  projectRoot={projectRoot}
                  onOpenSettings={() => setSettingsOpen(true)}
                />
                <button onClick={reset} className="py-1.5 px-4 rounded-lg border border-slate-200 hover:border-amber-400 text-slate-500 hover:text-amber-600 transition-colors text-sm flex items-center gap-1.5">
                  <RotateCcw size={13} />
                  创建新资产
                </button>
              </div>
            ) : stage === "error" ? (
              <div className="space-y-3">
                <p className="text-sm text-red-500 font-medium">✗ 构建失败，查看上方错误详情</p>
                <button onClick={reset} className="py-1.5 px-4 rounded-lg border border-slate-200 hover:border-red-300 text-slate-500 hover:text-red-500 transition-colors text-sm flex items-center gap-1.5">
                  <RotateCcw size={13} />
                  重试
                </button>
              </div>
            ) : stage === "approval_pending" ? (
              <div className="space-y-3">
                <p className="text-sm text-amber-600 font-medium">等待审批通过后继续执行</p>
                <button onClick={reset} className="py-1.5 px-4 rounded-lg border border-slate-200 hover:border-amber-300 text-slate-500 hover:text-amber-600 transition-colors text-sm flex items-center gap-1.5">
                  <RotateCcw size={13} />
                  重新开始
                </button>
              </div>
            ) : (
              <p className="text-sm text-slate-300">等待 Code Agent 完成…</p>
            )}
          </Step>
        </div>
      </main>
      )}

      {settingsOpen && <SettingsPanel onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}

/* ── 内联错误块：显示错误信息 + 已有日志 ── */
function ErrorBlock({ message, traceback, log, onReset }: { message: string | null; traceback: string | null; log: string[]; onReset: () => void }) {
  const [showTrace, setShowTrace] = useState(false);

  return (
    <div className="space-y-3">
      {log.length > 0 && <AgentLog lines={log} />}

      <div className="rounded-lg border border-red-200 bg-red-50 p-4 space-y-3">
        <div className="flex items-start gap-2.5">
          <AlertTriangle size={16} className="text-red-500 shrink-0 mt-0.5" />
          <div className="space-y-2 flex-1 min-w-0">
            <p className="text-sm font-semibold text-red-700">执行失败</p>
            {message && (
              <pre className="text-xs text-red-600/90 font-mono whitespace-pre-wrap break-all leading-relaxed bg-red-100/50 rounded p-2.5 max-h-64 overflow-y-auto">
                {message}
              </pre>
            )}
            {!message && (
              <p className="text-xs text-red-500">未收到错误详情，查看下方 Traceback</p>
            )}
            {traceback && (
              <>
                <button
                  onClick={() => setShowTrace(v => !v)}
                  className="text-xs text-red-400 hover:text-red-600 transition-colors flex items-center gap-1"
                >
                  {showTrace ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                  {showTrace ? "收起 Traceback" : "展开 Traceback"}
                </button>
                {showTrace && (
                  <pre className="text-xs text-red-500/80 font-mono whitespace-pre-wrap break-all leading-relaxed bg-red-100/30 rounded p-2.5 max-h-64 overflow-y-auto border border-red-200/50">
                    {traceback}
                  </pre>
                )}
              </>
            )}
          </div>
        </div>
        <button
          onClick={onReset}
          className="w-full py-2 rounded-lg border border-red-200 text-red-600 hover:bg-red-100 text-sm font-medium transition-colors flex items-center justify-center gap-1.5"
        >
          <RotateCcw size={13} />
          重试
        </button>
      </div>
    </div>
  );
}

/* ── Step 容器 ── */
function Step({ num, title, active, done, children }: {
  num: number; title: string; active: boolean; done: boolean; children: React.ReactNode;
}) {
  return (
    <div className={cn(
      "rounded-xl border p-5 transition-all",
      active ? "border-amber-300 bg-white shadow-md" : done ? "border-slate-200 bg-white" : "border-slate-100 bg-slate-50",
    )}>
      <div className="flex items-center gap-3 mb-4">
        <div className={cn(
          "w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0",
          active ? "bg-amber-500 text-white" : done ? "bg-amber-100 text-amber-600" : "bg-slate-200 text-slate-400",
        )}>
          {done ? "✓" : num}
        </div>
        <h2 className={cn("font-semibold text-sm", active ? "text-slate-800" : done ? "text-amber-600" : "text-slate-400")}>
          {title}
        </h2>
      </div>
      <div className={cn(!active && !done && "opacity-40 pointer-events-none")}>
        {children}
      </div>
    </div>
  );
}
