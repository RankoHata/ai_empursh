import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = 'ws://127.0.0.1:8765/ws';
const INITIAL_RECONNECT_MS = 1000;
const MAX_RECONNECT_MS = 30000;

/**
 * useWebSocket — manages a persistent WebSocket connection to the backend.
 *
 * @param {Object} handlers — { onMessage(type, payload) } called for each server message
 * @returns {{ connectionStatus, send }}
 *   connectionStatus: "disconnected" | "connecting" | "connected"
 *   send(type, payload): send a JSON message to the server
 */
export default function useWebSocket(handlers = {}) {
  const { onMessage } = handlers;

  const [connectionStatus, setConnectionStatus] = useState('disconnected');

  // Mutable refs so the reconnect logic always sees latest values
  const wsRef = useRef(null);
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_MS);
  const reconnectTimerRef = useRef(null);
  const mountedRef = useRef(true);
  const onMessageRef = useRef(onMessage);

  // Keep handler ref fresh without re-triggering the connection effect
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return;
    setConnectionStatus('connecting');

    const delay = reconnectDelayRef.current;
    reconnectTimerRef.current = setTimeout(() => {
      if (mountedRef.current) {
        connect();
      }
    }, delay);

    // Exponential backoff
    reconnectDelayRef.current = Math.min(delay * 2, MAX_RECONNECT_MS);
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      setConnectionStatus('connected');
      reconnectDelayRef.current = INITIAL_RECONNECT_MS;
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      try {
        const msg = JSON.parse(event.data);
        if (onMessageRef.current) {
          onMessageRef.current(msg.type, msg.payload);
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      wsRef.current = null;
      scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose will fire after onerror, reconnect there
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [scheduleReconnect]);

  // Start connection on mount, clean up on unmount
  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const send = useCallback((type, payload = {}) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload }));
      return true;
    }
    return false;
  }, []);

  return { connectionStatus, send };
}
