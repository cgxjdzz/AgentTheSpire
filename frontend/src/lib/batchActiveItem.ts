export type BatchItemStatus =
  | "pending"
  | "img_generating"
  | "awaiting_selection"
  | "approval_pending"
  | "code_generating"
  | "done"
  | "error";

export type BatchItemStateSnapshot = Record<string, { status?: BatchItemStatus }>;

function needsAttention(status?: BatchItemStatus): boolean {
  return status === "awaiting_selection" || status === "approval_pending" || status === "img_generating" || status === "code_generating";
}

export function pickActiveItemOnStart(
  currentActiveId: string | null,
  itemStates: BatchItemStateSnapshot,
  startedItemId: string,
): string {
  if (!currentActiveId) return startedItemId;

  const currentStatus = itemStates[currentActiveId]?.status;
  if (currentStatus === "awaiting_selection") return currentActiveId;
  if (currentStatus === "done" || currentStatus === "error") return startedItemId;
  return currentActiveId;
}

export function pickActiveItemOnDone(
  currentActiveId: string | null,
  doneItemId: string,
  itemStates: BatchItemStateSnapshot,
): string | null {
  if (currentActiveId !== doneItemId) return currentActiveId;

  const next = Object.entries(itemStates).find(
    ([id, state]) => id !== doneItemId && needsAttention(state.status),
  );
  return next ? next[0] : currentActiveId;
}
