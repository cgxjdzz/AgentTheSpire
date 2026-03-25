import { useRef, useState, useEffect } from "react";
import { Loader2, Search, Wrench, RotateCcw } from "lucide-react";
import { AgentLog } from "../components/AgentLog";
import { StageStatus } from "../components/StageStatus";
import { BuildDeploy } from "../components/BuildDeploy";
import { WorkflowSocket } from "../lib/ws";

type AnalyzeStage = "idle" | "scanning" | "streaming" | "done" | "error";
type ModifyStage = "idle" | "running" | "done" | "error";

export default function ModEditor() {
  const [projectRoot, setProjectRoot] = useState("");

  useEffect(() => {
    fetch("/api/config").then(r => r.json()).then(cfg => {
      if (cfg?.default_project_root) setProjectRoot(cfg.default_project_root);
    }).catch(() => {});
  }, []);

  // 分析状态
  const [analyzeStage, setAnalyzeStage] = useState<AnalyzeStage>("idle");
  const [scanFiles, setScanFiles] = useState<number | null>(null);
  const [analysisChunks, setAnalysisChunks] = useState<string[]>([]);
  const [analysisCurrentStage, setAnalysisCurrentStage] = useState<string | null>(null);
  const [analysisStageHistory, setAnalysisStageHistory] = useState<string[]>([]);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const analyzeWsRef = useRef<WebSocket | null>(null);

  // 修改状态
  const [modRequest, setModRequest] = useState("");
  const [modifyStage, setModifyStage] = useState<ModifyStage>("idle");
  const [agentLog, setAgentLog] = useState<string[]>([]);
  const [modifyCurrentStage, setModifyCurrentStage] = useState<string | null>(null);
  const [modifyStageHistory, setModifyStageHistory] = useState<string[]>([]);
  const [modifyError, setModifyError] = useState<string | null>(null);
  const modifyWsRef = useRef<WorkflowSocket | null>(null);

  // ── 分析 Mod ──────────────────────────────────────────────────────────────

  function startAnalysis() {
    if (!projectRoot.trim()) return;
    setAnalyzeStage("scanning");
    setScanFiles(null);
    setAnalysisChunks([]);
    setAnalysisCurrentStage(null);
    setAnalysisStageHistory([]);
    setAnalysisError(null);

    const ws = new WebSocket(`ws://${location.host}/api/ws/analyze-mod`);
    analyzeWsRef.current = ws;

    ws.onopen = () => ws.send(JSON.stringify({ project_root: projectRoot.trim() }));

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.event === "stage_update") {
        setAnalysisCurrentStage(msg.message);
        setAnalysisStageHistory(prev => prev[prev.length - 1] === msg.message ? prev : [...prev, msg.message]);
      } else if (msg.event === "scan_info") {
        setScanFiles(msg.files);
        setAnalyzeStage("streaming");
      } else if (msg.event === "stream") {
        setAnalysisChunks(prev => [...prev, msg.chunk]);
      } else if (msg.event === "done") {
        setAnalyzeStage("done");
      } else if (msg.event === "error") {
        setAnalysisError(msg.message);
        setAnalyzeStage("error");
      }
    };

    ws.onerror = () => {
      setAnalysisError("WebSocket 连接失败");
      setAnalyzeStage("error");
    };
  }

  function resetAnalysis() {
    analyzeWsRef.current?.close();
    analyzeWsRef.current = null;
    setAnalyzeStage("idle");
    setScanFiles(null);
    setAnalysisChunks([]);
    setAnalysisCurrentStage(null);
    setAnalysisStageHistory([]);
    setAnalysisError(null);
  }

  // ── 修改 Mod ──────────────────────────────────────────────────────────────

  async function startModify() {
    if (!projectRoot.trim() || !modRequest.trim()) return;
    setModifyStage("running");
    setAgentLog([]);
    setModifyCurrentStage(null);
    setModifyStageHistory([]);
    setModifyError(null);

    const ws = new WorkflowSocket();
    modifyWsRef.current = ws;

    ws.on("stage_update", (d: any) => {
      setModifyCurrentStage(d.message);
      setModifyStageHistory(prev => prev[prev.length - 1] === d.message ? prev : [...prev, d.message]);
    });
    ws.on("progress",     (d: any) => setAgentLog(p => [...p, d.message]));
    ws.on("agent_stream", (d: any) => setAgentLog(p => [...p, d.chunk]));
    ws.on("done",         (d: any) => {
      setAgentLog(p => [...p, d.success ? "✓ 修改完成！" : "✗ 修改失败"]);
      setModifyStage("done");
    });
    ws.on("error",        (d: any) => {
      setModifyError(d.message);
      setModifyStage("error");
    });

    await ws.waitOpen();

    // 把分析结果（如有）附加到 implementation_notes，供 agent 参考
    const analysisContext = analysisChunks.length > 0
      ? `当前 mod 分析概况：\n${analysisChunks.join("")}\n\n`
      : "";

    ws.send({
      action: "start",
      asset_type: "custom_code",
      asset_name: "ModModification",
      description: modRequest.trim(),
      project_root: projectRoot.trim(),
      implementation_notes: analysisContext + "这是对已有 mod 的修改请求，请定位到相关文件进行修改，不要新建不必要的文件。",
    });
  }

  function resetModify() {
    modifyWsRef.current?.close();
    modifyWsRef.current = null;
    setModifyStage("idle");
    setAgentLog([]);
    setModifyCurrentStage(null);
    setModifyStageHistory([]);
    setModifyError(null);
  }

  const analysisText = analysisChunks.join("");
  const isAnalyzing = analyzeStage === "scanning" || analyzeStage === "streaming";
  const isModifying = modifyStage === "running";

  return (
    <div className="max-w-2xl mx-auto space-y-5">

      {/* 项目路径 */}
      <div className="rounded-xl border border-amber-300 bg-white shadow-md p-5 space-y-4">
        <h2 className="font-semibold text-slate-800">Mod 项目路径</h2>
        <input
          value={projectRoot}
          onChange={e => setProjectRoot(e.target.value)}
          placeholder="E:/STS2mod/testscenario/MyMod"
          className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 placeholder:text-slate-300 focus:outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-100 font-mono"
        />
      </div>

      {/* 分析 Mod */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Search size={15} className="text-slate-400" />
            <h3 className="font-semibold text-slate-700 text-sm">分析 Mod 内容</h3>
          </div>
          {analyzeStage !== "idle" && (
            <button
              onClick={resetAnalysis}
              className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-1 transition-colors"
            >
              <RotateCcw size={11} /> 重新分析
            </button>
          )}
        </div>

        {analyzeStage === "idle" && (
          <button
            onClick={startAnalysis}
            disabled={!projectRoot.trim()}
            className="w-full py-2 rounded-lg border border-amber-400 text-amber-600 font-medium text-sm hover:bg-amber-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
          >
            <Search size={14} />
            分析 Mod
          </button>
        )}

        {isAnalyzing && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 py-1">
              <Loader2 size={14} className="text-amber-500 animate-spin" />
              <span className="text-sm text-slate-400">
                {analyzeStage === "scanning"
                  ? "正在扫描源码文件…"
                  : `已扫描 ${scanFiles} 个文件，AI 分析中…`}
              </span>
            </div>
            <StageStatus current={analysisCurrentStage} history={analysisStageHistory} />
          </div>
        )}

        {(analysisText || analysisError) && (
          <div className="space-y-2">
            {analysisError ? (
              <pre className="text-xs text-red-600 font-mono whitespace-pre-wrap">{analysisError}</pre>
            ) : (
              <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed max-h-80 overflow-y-auto">
                {analysisText}
                {isAnalyzing && (
                  <span className="inline-block w-1.5 h-4 bg-amber-400 animate-pulse ml-0.5 align-text-bottom" />
                )}
              </pre>
            )}
          </div>
        )}
      </div>

      {/* 修改 Mod */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Wrench size={15} className="text-slate-400" />
          <h3 className="font-semibold text-slate-700 text-sm">修改 Mod</h3>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-slate-500">描述要做什么改动</label>
          <textarea
            value={modRequest}
            onChange={e => setModRequest(e.target.value)}
            disabled={isModifying}
            rows={4}
            placeholder={"例如：\n把 DarkBlade 的伤害从 8 改成 12，升级后改成 16\n或者：给 FangedGrimoire 增加一个条件，只有血量低于50%时才触发"}
            className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 placeholder:text-slate-300 focus:outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-100 resize-none disabled:opacity-50"
          />
        </div>

        {modifyStage === "idle" || modifyStage === "done" || modifyStage === "error" ? (
          <div className="flex gap-2">
            <button
              onClick={startModify}
              disabled={!projectRoot.trim() || !modRequest.trim()}
              className="flex-1 py-2.5 rounded-lg bg-amber-500 text-white font-bold text-sm hover:bg-amber-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              执行修改
            </button>
            {(modifyStage === "done" || modifyStage === "error") && (
              <button
                onClick={resetModify}
                className="py-2.5 px-4 rounded-lg border border-slate-200 text-slate-400 hover:text-slate-600 text-sm transition-colors flex items-center gap-1.5"
              >
                <RotateCcw size={13} /> 重试
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center gap-2 py-1">
              <Loader2 size={14} className="text-amber-500 animate-spin" />
              <span className="text-sm text-slate-400">Code Agent 执行中…</span>
            </div>
            <StageStatus current={modifyCurrentStage} history={modifyStageHistory} />
          </div>
        )}

        {(agentLog.length > 0 || modifyError) && (
          <div className="space-y-2">
            {modifyError && (
              <pre className="text-xs text-red-600 font-mono whitespace-pre-wrap">{modifyError}</pre>
            )}
            {agentLog.length > 0 && <AgentLog lines={agentLog} />}
          </div>
        )}

        {modifyStage === "done" && (
          <BuildDeploy projectRoot={projectRoot} />
        )}
      </div>
    </div>
  );
}
