import type { ApprovalRequest } from "./approvals";

/**
 * WebSocket client for the AgentTheSpire workflow.
 */

export type WsEvent =
  | { event: "stage_update";  scope: "project" | "text" | "image" | "agent" | "build"; stage: string; message: string }
  | { event: "progress";       message: string }
  | { event: "prompt_preview"; prompt: string; negative_prompt: string; fallback_warning?: string }
  | { event: "image_ready";    image: string; index: number; prompt: string }
  | { event: "agent_stream";   chunk: string }
  | { event: "approval_pending"; summary: string; requests: ApprovalRequest[] }
  | { event: "done";           success: boolean; image_paths: string[]; agent_output: string }
  | { event: "error";          message: string };

export class WorkflowSocket {
  private ws: WebSocket;
  private listeners = new Map<string, ((data: WsEvent) => void)[]>();

  constructor() {
    this.ws = new WebSocket(`ws://${location.host}/api/ws/create`);
    this.ws.onmessage = (e) => {
      const data: WsEvent = JSON.parse(e.data);
      const handlers = this.listeners.get(data.event) ?? [];
      handlers.forEach((h) => h(data));
    };
  }

  on(event: WsEvent["event"], handler: (data: WsEvent) => void) {
    const list = this.listeners.get(event) ?? [];
    this.listeners.set(event, [...list, handler]);
    return this;
  }

  send(data: object) {
    this.ws.send(JSON.stringify(data));
  }

  waitOpen(): Promise<void> {
    if (this.ws.readyState === WebSocket.OPEN) return Promise.resolve();
    return new Promise((res, rej) => {
      const cleanup = () => {
        this.ws.onopen = null;
        this.ws.onerror = null;
        this.ws.onclose = null;
      };

      const timer = setTimeout(() => {
        cleanup();
        rej(new Error("WebSocket connection timed out"));
      }, 5000);

      this.ws.onopen = () => {
        clearTimeout(timer);
        cleanup();
        res();
      };
      this.ws.onerror = () => {
        clearTimeout(timer);
        cleanup();
        rej(new Error("WebSocket connection failed"));
      };
      this.ws.onclose = () => {
        clearTimeout(timer);
        cleanup();
        rej(new Error("WebSocket connection closed"));
      };
    });
  }

  close() {
    this.ws.close();
  }
}
