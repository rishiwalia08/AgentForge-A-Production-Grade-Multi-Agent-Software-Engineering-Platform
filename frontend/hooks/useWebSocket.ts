'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { WS_BASE_URL } from '../lib/api';
import { useAuth } from '../lib/auth';

export interface WSEvent {
  type: string;
  agent?: string;
  content?: string;
  payload?: any;
  [key: string]: any;
}

export function useWebSocket(runId: string | null) {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<WSEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const { token } = useAuth();

  const connect = useCallback(() => {
    if (!runId || !token) return;

    // Disconnect old socket if any
    if (socketRef.current) {
      socketRef.current.close();
    }

    const wsUrl = `${WS_BASE_URL}/runs/${runId}/stream?token=${token}`;
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setError(null);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WSEvent;
        setEvents((prev) => [...prev, data]);
      } catch (err) {
        console.error('Failed to parse WebSocket message', err);
      }
    };

    ws.onerror = (err) => {
      console.error('WebSocket Error', err);
      setError('WebSocket connection error');
    };

    ws.onclose = () => {
      setConnected(false);
    };
  }, [runId, token]);

  useEffect(() => {
    connect();

    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [runId, connect]);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  return { connected, events, error, clearEvents };
}
