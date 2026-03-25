import { Loader2 } from "lucide-react";
import { shouldShowStageStatus } from "../lib/stageStatusVisibility";

export function StageStatus({
  current,
  history,
  isComplete = false,
}: {
  current: string | null;
  history: string[];
  isComplete?: boolean;
}) {
  if (!shouldShowStageStatus({ current, history, isComplete })) return null;

  const recent = history.slice(-4);

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 space-y-2">
      <div className="flex items-center gap-2">
        <Loader2 size={13} className="text-amber-500 animate-spin" />
        <p className="text-sm font-medium text-amber-700">{current || recent[recent.length - 1]}</p>
      </div>
      {recent.length > 1 && (
        <div className="space-y-1">
          {recent.slice(0, -1).map((line, i) => (
            <p key={i} className="text-xs text-amber-700/80">
              {line}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
