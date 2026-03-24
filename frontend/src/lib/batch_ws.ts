import type { ApprovalRequest } from "./approvals";

/**
 * WebSocket client for the AgentTheSpire batch workflow.
 */

export type BatchEvent =
  | { event: "planning" }
  | { event: "plan_ready"; plan: ModPlan }
  | { event: "stage_update"; scope: "project" | "text" | "image" | "agent" | "build"; stage: string; message: string; item_id?: string }
  | { event: "batch_progress"; message: string }
  | { event: "batch_started"; items: PlanItem[] }
  | { event: "item_started";      item_id: string; name: string; type: string }
  | { event: "item_progress";     item_id: string; message: string }
  | { event: "item_image_ready";  item_id: string; image: string; index: number; prompt: string }
  | { event: "item_agent_stream"; item_id: string; chunk: string }
  | { event: "item_approval_pending"; item_id: string; summary: string; requests: ApprovalRequest[] }
  | { event: "item_done";         item_id: string; success: boolean }
  | { event: "item_error";        item_id: string; message: string; traceback?: string }
  | { event: "batch_done";        success_count: number; error_count: number }
  | { event: "error";             message: string; traceback?: string };

export interface PlanItem {
  id: string;
  type: string;
  name: string;
  name_zhs: string;
  description: string;
  implementation_notes: string;
  needs_image: boolean;
  image_description: string;
  depends_on: string[];
  provided_image_b64?: string; // user-uploaded image; if set, skip AI generation
}

export interface ModPlan {
  mod_name: string;
  summary: string;
  items: PlanItem[];
}

export class BatchSocket {
  private ws: WebSocket;
  private listeners = new Map<string, ((data: BatchEvent) => void)[]>();

  constructor() {
    this.ws = new WebSocket(`ws://${location.host}/api/ws/batch`);
    this.ws.onmessage = (e) => {
      const data: BatchEvent = JSON.parse(e.data);
      const handlers = this.listeners.get(data.event) ?? [];
      handlers.forEach((h) => h(data));
    };
  }

  on<T extends BatchEvent["event"]>(
    event: T,
    handler: (data: Extract<BatchEvent, { event: T }>) => void
  ) {
    const list = this.listeners.get(event) ?? [];
    this.listeners.set(event, [...list, handler as (d: BatchEvent) => void]);
    return this;
  }

  send(data: object) {
    this.ws.send(JSON.stringify(data));
  }

  waitOpen(): Promise<void> {
    if (this.ws.readyState === WebSocket.OPEN) return Promise.resolve();
    return new Promise((res, rej) => {
      this.ws.onopen = () => res();
      this.ws.onerror = () => rej(new Error("WebSocket connection failed"));
    });
  }

  close() {
    this.ws.close();
  }
}
