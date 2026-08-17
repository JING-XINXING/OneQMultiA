import { useCallback, useRef, useState } from "react";

/** 服务端推送的事件结构（与 FastAPI ws_routes 一致） */
export type WsEvent =
  | { type: "qa_pair"; qa_pair_id: string; question: string }
  | { type: "platform_start"; platform_id: string; platform_name: string }
  | { type: "answer_delta"; platform_id: string; platform_name?: string; preview: string }
  | {
      type: "platform_done";
      platform_id: string;
      platform_name: string;
      platform_url: string;
      status: string;
      answer_text: string;
      error_message: string;
      request_sent_at: string | null;
      first_token_at: string | null;
      completed_at: string | null;
      response_duration_ms: number | null;
    }
  | { type: "complete"; summary: Record<string, unknown> }
  | { type: "error"; message: string };

function wsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/ws/ask`;
}

const MAX_RECONNECT = 3;
const RECONNECT_MS = 2000;

export function useWebSocketAsk() {
  const [events, setEvents] = useState<WsEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [asking, setAsking] = useState(false);
  const [lastSummary, setLastSummary] = useState<Record<string, unknown> | null>(null);
  const [lastQaPairId, setLastQaPairId] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const payloadRef = useRef<{ session_id: string; question: string; platform_ids: string[] | null } | null>(null);
  const reconnectCount = useRef(0);
  const userStoppedRef = useRef(false);
  const lastSummaryRef = useRef<Record<string, unknown> | null>(null);

  const clear = useCallback(() => {
    setEvents([]);
    setLastSummary(null);
    lastSummaryRef.current = null;
    setLastQaPairId(null);
  }, []);

  const finishAsk = useCallback(() => {
    setAsking(false);
    setConnected(false);
  }, []);

  const connectAndSend = useCallback(() => {
    const payload = payloadRef.current;
    if (!payload || userStoppedRef.current) return;

    const ws = new WebSocket(wsUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      reconnectCount.current = 0;
      ws.send(
        JSON.stringify({
          action: "ask",
          session_id: payload.session_id,
          question: payload.question,
          platform_ids: payload.platform_ids,
        })
      );
    };

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string) as WsEvent;
        setEvents((prev) => [...prev, msg]);
        if (msg.type === "qa_pair") setLastQaPairId(msg.qa_pair_id);
        if (msg.type === "complete") {
          setLastSummary(msg.summary);
          lastSummaryRef.current = msg.summary;
          ws.close();
          finishAsk();
        }
        if (msg.type === "error") {
          ws.close();
          finishAsk();
        }
      } catch {
        /* ignore */
      }
    };

    ws.onerror = () => setConnected(false);

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
      // 用户主动停止或已完成时不再重连，避免把终止变成死循环
      if (userStoppedRef.current || lastSummaryRef.current) {
        finishAsk();
        return;
      }
      if (payloadRef.current && reconnectCount.current < MAX_RECONNECT) {
        reconnectCount.current += 1;
        setTimeout(connectAndSend, RECONNECT_MS);
      } else {
        finishAsk();
      }
    };
  }, [finishAsk]);

  const runAsk = useCallback(
    (payload: { session_id: string; question: string; platform_ids: string[] | null }) => {
      clear();
      userStoppedRef.current = false;
      payloadRef.current = payload;
      reconnectCount.current = 0;
      setAsking(true);
      connectAndSend();
    },
    [clear, connectAndSend]
  );

  const cancelAsk = useCallback((platformId?: string) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action: "cancel", platform_id: platformId || null }));
    }
    if (!platformId) {
      userStoppedRef.current = true;
      payloadRef.current = null;
      finishAsk();
    }
  }, [finishAsk]);

  return { events, connected, asking, lastSummary, lastQaPairId, runAsk, cancelAsk, clear };
}
