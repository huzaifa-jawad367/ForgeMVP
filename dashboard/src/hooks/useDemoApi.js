import { useCallback, useEffect, useState } from 'react';
import { API_BASE } from './useForgeApi';
export const EDGE_API = import.meta.env.VITE_EDGE_API_URL || 'http://127.0.0.1:8001';
export async function request(url, options = {}) {
  const response = await fetch(url, { ...options, signal: options.signal || AbortSignal.timeout(5000) });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${response.status}`);
  }
  return response.json();
}
export function useObservation(url, interval = 1000, validate) {
  const [state, setState] = useState({ data: null, error: null, loading: true, receivedAt: null });
  const refresh = useCallback(async (cancellationSignal) => {
    const signal = cancellationSignal ? AbortSignal.any([cancellationSignal, AbortSignal.timeout(4000)]) : AbortSignal.timeout(4000);
    try {
      const data = await request(url, { signal });
      validate?.(data);
      if (!cancellationSignal?.aborted) setState({ data, error: null, loading: false, receivedAt: Date.now() });
      return data;
    } catch (error) {
      if (!cancellationSignal?.aborted) setState(previous => ({ ...previous, error: signal.aborted ? 'Request timed out' : error.message, loading: false }));
    }
  }, [url, validate]);
  useEffect(() => {
    const controller = new AbortController();
    let timer;
    const poll = async () => {
      await refresh(controller.signal);
      if (!controller.signal.aborted) timer = setTimeout(poll, interval);
    };
    poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [refresh, interval]);
  return { ...state, refresh };
}
function validateEdgeSnapshot(data) {
  if (typeof data?.edge_id !== 'string' || typeof data?.sync?.paused !== 'boolean' ||
      !Number.isFinite(data?.buffer?.queue_size) || !Array.isArray(data?.samples) ||
      !Array.isArray(data?.events) || !Number.isFinite(Date.parse(data?.observed_at))) {
    throw new Error('Edge returned an unsupported observation format');
  }
}
export const useDemoStatus = () => useObservation(`${EDGE_API}/api/demo/status`, 1000, validateEdgeSnapshot);
export const useBackendObservation = (path, interval = 2000) => useObservation(`${API_BASE}${path}`, interval);
export const edgeCommand = (path, body) => request(`${EDGE_API}/api/demo/${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
export const reconcileRun = (edgeId, payloadIds) => request(`${API_BASE}/api/demo/reconcile`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ edge_id: edgeId, payload_ids: payloadIds }) });
