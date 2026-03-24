import { useEffect, useState } from "react";
import { X, FolderOpen, Gamepad2, Cpu, Image, Search } from "lucide-react";

const inputCls = "w-full bg-white border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-800 placeholder:text-slate-300 focus:outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-100";
const selectCls = "w-full bg-white border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-800 focus:outline-none focus:border-amber-400";

const PROVIDER_MODELS: Record<string, string[]> = {
  bfl:         ["flux.2-flex", "flux.2-pro", "flux.2-klein", "flux.2-max", "flux.1.1-pro"],
  fal:         ["flux.2-flex", "flux.2-pro", "flux.2-dev", "flux.2-schnell"],
  volcengine:  ["doubao-seedream-3-0-t2i-250415", "doubao-seedream-3-0-1-5b-t2i-250616"],
  wanxiang:    [],
};

const TEXT_PROVIDERS = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "moonshot", label: "Moonshot" },
  { value: "deepseek", label: "DeepSeek" },
  { value: "qwen", label: "Qwen" },
  { value: "zhipu", label: "Zhipu" },
];

function SGroup({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-slate-400">{icon}</span>
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{title}</h3>
      </div>
      <div className="space-y-2.5 pl-1">{children}</div>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-slate-500">{label}</label>
      {children}
      {hint && <p className="text-xs text-slate-400">{hint}</p>}
    </div>
  );
}

export function SettingsPanel({ onClose }: { onClose: () => void }) {
  const [cfg, setCfg] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [detectNotes, setDetectNotes] = useState<string[]>([]);
  const [llmKey, setLlmKey] = useState("");
  const [imgKey, setImgKey] = useState("");
  const [imgSecret, setImgSecret] = useState("");

  useEffect(() => {
    fetch("/api/config").then(r => r.json()).then(setCfg);
  }, []);

  function set(path: string[], value: string | number) {
    setCfg((prev: any) => {
      const next = structuredClone(prev);
      let cur = next;
      for (let i = 0; i < path.length - 1; i++) cur = cur[path[i]];
      cur[path[path.length - 1]] = value;
      return next;
    });
  }

  function handleProviderChange(provider: string) {
    const models = PROVIDER_MODELS[provider] ?? [];
    setCfg((prev: any) => {
      const next = structuredClone(prev);
      next.image_gen.provider = provider;
      if (models.length > 0 && !models.includes(next.image_gen.model)) {
        next.image_gen.model = models[0];
      }
      return next;
    });
  }

  async function detectPaths() {
    setDetecting(true);
    setDetectNotes([]);
    try {
      const res = await fetch("/api/config/detect_paths").then(r => r.json());
      const notes: string[] = res.notes ?? [];
      if (res.sts2_path) {
        set(["sts2_path"], res.sts2_path);
        notes.push(`✓ STS2: ${res.sts2_path}`);
      }
      if (res.godot_exe_path) {
        set(["godot_exe_path"], res.godot_exe_path);
        notes.push(`✓ Godot: ${res.godot_exe_path}`);
      }
      setDetectNotes(notes);
    } catch {
      setDetectNotes(["检测失败，请手动填写路径"]);
    } finally {
      setDetecting(false);
    }
  }

  async function save() {
    setSaving(true);
    const body = structuredClone(cfg);
    if (llmKey.trim()) body.llm.api_key = llmKey.trim();
    if (imgKey.trim()) body.image_gen.api_key = imgKey.trim();
    if (imgSecret.trim()) body.image_gen.api_secret = imgSecret.trim();
    await fetch("/api/config", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setSaving(false);
    onClose();
  }

  const currentProvider = cfg?.image_gen?.provider ?? "bfl";
  const models = PROVIDER_MODELS[currentProvider] ?? [];

  const missingPaths = cfg && (!cfg.default_project_root || !cfg.sts2_path);

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex justify-end" onClick={onClose}>
      <div
        className="w-full max-w-sm bg-white border-l border-slate-200 h-full overflow-y-auto shadow-xl"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between z-10">
          <div>
            <h2 className="font-bold text-slate-800">设置</h2>
            {missingPaths && (
              <p className="text-xs text-amber-600 mt-0.5">⚠ 请配置项目路径</p>
            )}
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors p-1 rounded-lg hover:bg-slate-100">
            <X size={18} />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {!cfg ? (
            <p className="text-slate-400 text-sm">加载中…</p>
          ) : (
            <>
              {/* ── 项目配置（最重要，放最前面）── */}
              <SGroup icon={<FolderOpen size={14} />} title="项目配置">
                <button
                  onClick={detectPaths}
                  disabled={detecting}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-slate-500 text-xs hover:border-amber-300 hover:text-amber-600 disabled:opacity-40 transition-colors"
                >
                  <Search size={12} />
                  {detecting ? "检测中…" : "自动检测路径"}
                </button>
                {detectNotes.length > 0 && (
                  <div className="space-y-0.5">
                    {detectNotes.map((n, i) => (
                      <p key={i} className={`text-xs ${n.startsWith("✓") ? "text-green-600" : "text-slate-400"}`}>{n}</p>
                    ))}
                  </div>
                )}
                <Field
                  label="默认 Mod 项目目录"
                  hint="新建/修改 Mod 时的默认路径"
                >
                  <input
                    value={cfg.default_project_root || ""}
                    onChange={e => set(["default_project_root"], e.target.value)}
                    placeholder="E:/STS2mod/testscenario"
                    className={inputCls + " font-mono"}
                  />
                </Field>
                <Field
                  label="STS2 游戏根目录"
                  hint="用于一键部署 Mod 文件"
                >
                  <input
                    value={cfg.sts2_path || ""}
                    onChange={e => set(["sts2_path"], e.target.value)}
                    placeholder="E:/steam/steamapps/common/Slay the Spire 2"
                    className={inputCls + " font-mono"}
                  />
                </Field>
                <Field
                  label="Godot 4.5.1 Mono 路径"
                  hint="用于打包 .pck 文件，必须是 4.5.1 Mono 版本"
                >
                  <input
                    value={cfg.godot_exe_path || ""}
                    onChange={e => set(["godot_exe_path"], e.target.value)}
                    placeholder="C:/tools/Godot_v4.5.1-stable_mono_win64.exe"
                    className={inputCls + " font-mono"}
                  />
                </Field>
              </SGroup>

              <div className="border-t border-slate-100" />

              {/* ── LLM 配置 ── */}
              <SGroup icon={<Cpu size={14} />} title="LLM 配置">
                <Field label="文本任务模式" hint="规划、日志分析、提示词优化走这里的配置">
                  <select value={cfg.llm?.mode || ""} onChange={e => set(["llm", "mode"], e.target.value)} className={selectCls}>
                    <option value="agent_cli">Agent CLI</option>
                    <option value="api">API</option>
                  </select>
                </Field>
                <Field label="代码代理后端" hint="代码生成、编译修复、项目修改使用这个代理">
                  <select
                    value={cfg.llm?.agent_backend || "claude"}
                    onChange={e => set(["llm", "agent_backend"], e.target.value)}
                    className={selectCls}
                  >
                    <option value="claude">Claude CLI</option>
                    <option value="codex">Codex CLI</option>
                  </select>
                </Field>
                <Field
                  label="代码执行模式"
                  hint="审批模式：执行前展示操作预览，用户确认后再调用代理。推荐在使用 Codex 时开启。"
                >
                  <select
                    value={cfg.llm?.execution_mode || "legacy_direct"}
                    onChange={e => set(["llm", "execution_mode"], e.target.value)}
                    className={selectCls}
                  >
                    <option value="legacy_direct">直接执行</option>
                    <option value="approval_first">审批后执行</option>
                  </select>
                </Field>
                {cfg.llm?.mode === "api" && (
                  <Field label="API 提供商">
                    <select
                      value={cfg.llm?.provider || "anthropic"}
                      onChange={e => set(["llm", "provider"], e.target.value)}
                      className={selectCls}
                    >
                      {TEXT_PROVIDERS.map(provider => (
                        <option key={provider.value} value={provider.value}>{provider.label}</option>
                      ))}
                    </select>
                  </Field>
                )}
                {cfg.llm?.mode === "agent_cli" && (
                  <Field label="CLI 模型（可选）" hint="留空使用 Codex 或 Claude CLI 的默认模型">
                    <input
                      value={cfg.llm?.model || ""}
                      onChange={e => set(["llm", "model"], e.target.value)}
                      placeholder="例如 gpt-5-codex / opus / sonnet"
                      className={inputCls}
                    />
                  </Field>
                )}
                <Field label="API Key（留空不修改）">
                  <input value={llmKey} onChange={e => setLlmKey(e.target.value)} placeholder={cfg.llm?.api_key ? "已设置" : "未设置"} className={inputCls} />
                </Field>
                <Field label="Base URL（可选）">
                  <input value={cfg.llm?.base_url || ""} onChange={e => set(["llm", "base_url"], e.target.value)} placeholder="https://..." className={inputCls} />
                </Field>
                <Field label="AI 附加提示词" hint="会追加到全部 AI 调用，包括文本分析、规划、提示词优化和代码代理">
                  <textarea
                    value={cfg.llm?.custom_prompt || ""}
                    onChange={e => set(["llm", "custom_prompt"], e.target.value)}
                    placeholder="例如：始终用简体中文回答；优先最小改动；输出先给结论后给细节"
                    rows={5}
                    className={inputCls + " min-h-28 resize-y"}
                  />
                </Field>
              </SGroup>

              <div className="border-t border-slate-100" />

              {/* ── 图像生成 ── */}
              <SGroup icon={<Image size={14} />} title="图像生成">
                <Field label="提供商">
                  <select value={currentProvider} onChange={e => handleProviderChange(e.target.value)} className={selectCls}>
                    <option value="bfl">BFL (FLUX.2)</option>
                    <option value="fal">fal.ai</option>
                    <option value="volcengine">火山引擎 (即梦 Seedream)</option>
                    <option value="wanxiang">通义万相</option>
                  </select>
                </Field>
                {models.length > 0 && (
                  <Field label="模型">
                    <select value={cfg.image_gen?.model || ""} onChange={e => set(["image_gen", "model"], e.target.value)} className={selectCls}>
                      {models.map(m => <option key={m} value={m}>{m}</option>)}
                    </select>
                  </Field>
                )}
                {currentProvider === "volcengine" ? (
                  <>
                    <Field label="Access Key（AK，留空不修改）">
                      <input value={imgKey} onChange={e => setImgKey(e.target.value)} placeholder={cfg.image_gen?.api_key ? "已设置" : "未设置"} className={inputCls} />
                    </Field>
                    <Field label="Secret Key（SK，留空不修改）">
                      <input type="password" value={imgSecret} onChange={e => setImgSecret(e.target.value)} placeholder={cfg.image_gen?.api_secret ? "已设置" : "未设置"} className={inputCls} />
                    </Field>
                  </>
                ) : (
                  <Field label="API Key（留空不修改）">
                    <input value={imgKey} onChange={e => setImgKey(e.target.value)} placeholder={cfg.image_gen?.api_key ? "已设置" : "未设置"} className={inputCls} />
                  </Field>
                )}
                <Field label="背景去除模型" hint="birefnet-general 质量最高但慢；birefnet-lite 快一倍；u2net 最快（适合 CPU）">
                  <select
                    value={cfg.image_gen?.rembg_model || "birefnet-general"}
                    onChange={e => set(["image_gen", "rembg_model"], e.target.value)}
                    className={selectCls}
                  >
                    <option value="birefnet-general">birefnet-general（最高质量）</option>
                    <option value="birefnet-general-lite">birefnet-general-lite（质量/速度均衡）</option>
                    <option value="isnet-general-use">isnet-general-use（通用）</option>
                    <option value="u2net">u2net（最快，适合无 GPU）</option>
                  </select>
                </Field>
                <Field label="并发生图数量" hint="1=串行（推荐，避免 API 限流）；提高可加速但易触发并发限制">
                  <input
                    type="number" min={1} max={4}
                    value={cfg.image_gen?.concurrency ?? 1}
                    onChange={e => set(["image_gen", "concurrency"], parseInt(e.target.value) || 1)}
                    className={inputCls}
                  />
                </Field>
              </SGroup>

              <button
                onClick={save}
                disabled={saving}
                className="w-full py-2.5 rounded-lg bg-amber-500 text-white font-bold text-sm hover:bg-amber-600 disabled:opacity-40 transition-colors"
              >
                {saving ? "保存中…" : "保存设置"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
