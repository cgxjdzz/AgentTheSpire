export interface StageStatusVisibilityInput {
  current: string | null;
  history: string[];
  isComplete?: boolean;
}

export function shouldShowStageStatus({ current, history, isComplete = false }: StageStatusVisibilityInput): boolean {
  if (isComplete) return false;
  return Boolean(current || history.length > 0);
}
