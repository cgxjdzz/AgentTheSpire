import { useRef, useState } from "react";
import { Loader2, Bug, RotateCcw } from "lucide-react";
import { AgentLog } from "../components/AgentLog";
import { StageStatus } from "../components/StageStatus";

type Stage = "input" | "analyzing" | "done" | "error";

export default function LogAnalysis() {
  const [stage, setStage] = useState<Stage>("input");
  const [context, setContext] = useState("");
  const [logLines, setLogLines] = useState<number | null>(null);
  const [chunks, setChunks] = useState<string[]>([]);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [stageHistory, setStageHistory] = useState<string[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  function reset() {
    wsRef.current?.close();
    wsRef.current = null;
    setStage("input");
    setLogLines(null);
    setChunks([]);
    setCurrentStage(null);
    setStageHistory([]);
    setErrorMsg(null);
  }

  function analyze() {
    setStage("analyzing");
    setLogLines(null);
    setChunks([]);
    setCurrentStage(null);
    setStageHistory([]);
    setErrorMsg(null);

    const ws = new WebSocket(`ws://${location.host}/api/ws/analyze-log`);
    wsRef.current = ws;

    ws.onopen = () => ws.send(JSON.stringify({ context }));

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.event === "stage_update") {
        setCurrentStage(msg.message);
        setStageHistory(prev => prev[prev.length - 1] === msg.message ? prev : [...prev, msg.message]);
      } else if (msg.event === "log_info") {
        setLogLines(msg.lines);
      } else if (msg.event === "stream") {
        setChunks(prev => [...prev, msg.chunk]);
      } else if (msg.event === "done") {
        setStage("done");
      } else if (msg.event === "error") {
        setErrorMsg(msg.message);
        setStage("error");
      }
    };

    ws.onerror = () => {
      setErrorMsg("WebSocket 连接失败");
      setStage("error");
    };
  }

  const analysisText = chunks.join("");

  return (
    <div className="max-w-2xl mx-auto space-y-5">
      {/* 输入卡片 */}
      <div className="rounded-xl border border-amber-300 bg-white shadow-md p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Bug size={16} className="text-amber-600" />
          <h2 className="font-semibold text-slate-800">游戏崩溃 / 加载失败分析</h2>
        </div>
        <p className="text-xs text-slate-400">
          自动读取 STS2 游戏日志，AI 分析崩溃原因并给出修复建议。
        </p>
        <div className="space-y-1">
          <label className="text-xs font-medium text-slate-500">补充说明（可选）</label>
          <textarea
            value={context}
            onChange={e => setContext(e.target.value)}
            disabled={stage === "analyzing"}
            rows={3}
            placeholder="描述你遇到的问题，例如：加了 MyMod 之后黑屏，或者游戏直接崩溃…"
            className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 placeholder:text-slate-300 focus:outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-100 resize-none disabled:opacity-50"
          />
        </div>

        {stage === "input" || stage === "done" || stage === "error" ? (
          <div className="flex gap-2">
            <button
              onClick={analyze}
              className="flex-1 py-2.5 rounded-lg bg-amber-500 text-white font-bold text-sm hover:bg-amber-600 transition-colors"
            >
              分析日志
            </button>
            {(stage === "done" || stage === "error") && (
              <button
                onClick={reset}
                className="py-2.5 px-4 rounded-lg border border-slate-200 text-slate-400 hover:text-slate-600 text-sm transition-colors flex items-center gap-1.5"
              >
                <RotateCcw size={13} /> 重新分析
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center gap-2 py-1">
              <Loader2 size={14} className="text-amber-500 animate-spin" />
              <span className="text-sm text-slate-400">
                {logLines != null ? `已读取 ${logLines} 行日志，AI 分析中…` : "正在读取日志…"}
              </span>
            </div>
            <StageStatus current={currentStage} history={stageHistory} />
          </div>
        )}
      </div>

      {/* 分析结果 */}
      {(analysisText || errorMsg) && (
        <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-3">
          <p className="text-xs font-medium text-slate-500">分析结果</p>
          {errorMsg ? (
            <pre className="text-xs text-red-600 font-mono whitespace-pre-wrap">{errorMsg}</pre>
          ) : (
            <div className="prose prose-sm prose-slate max-w-none">
              <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed">
                {analysisText}
                {stage === "analyzing" && (
                  <span className="inline-block w-1.5 h-4 bg-amber-400 animate-pulse ml-0.5 align-text-bottom" />
                )}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
