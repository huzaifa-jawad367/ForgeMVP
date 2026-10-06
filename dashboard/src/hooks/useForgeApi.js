import { useState, useEffect, useRef, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Generic polling hook — fetches `url` every `intervalMs` milliseconds.
 * Returns { data, error, loading }.
 */
function usePolling(path, intervalMs, enabled = true) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;

    const fetchData = async () => {
      try {
        const res = await fetch(`${API_BASE}${path}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) {
          setData(json);
          setError(null);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
          setLoading(false);
        }
      }
    };

    fetchData();
    timerRef.current = setInterval(fetchData, intervalMs);

    return () => {
      cancelled = true;
      clearInterval(timerRef.current);
    };
  }, [path, intervalMs, enabled]);

  return { data, error, loading };
}

/* ── Exported hooks ── */

export function useLatestMetrics() {
  return usePolling('/api/metrics/latest', 1000);
}

export function useIncidents(limit = 20) {
  return usePolling(`/api/incidents?limit=${limit}`, 2000);
}

export function usePipelineStatus() {
  return usePolling('/api/pipeline/status', 2000);
}

export function useEdgeStatus() {
  return usePolling('/api/edge/status', 1000);
}

export function useIncidentEvidence(incidentId) {
  return usePolling(
    `/api/incidents/${incidentId}/evidence`,
    60000, // refresh evidence rarely
    !!incidentId
  );
}

/* ── One-shot POST helpers ── */

export async function postDegrade(params) {
  const res = await fetch(`${API_BASE}/api/demo/degrade`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function postReset() {
  const res = await fetch(`${API_BASE}/api/demo/reset`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function resolveIncident(id) {
  const res = await fetch(`${API_BASE}/api/incidents/${id}/resolve`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function startPipeline({ input = 'visa:pcb1', fps = 10, loop = true, model = 'efficientad' } = {}) {
  const res = await fetch(`${API_BASE}/api/pipeline/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input, fps, loop, model }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function stopPipeline() {
  const res = await fetch(`${API_BASE}/api/pipeline/stop`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function getEvidenceUrl(incidentId, filename) {
  return `${API_BASE}/evidence/incidents/${incidentId}/${filename}`;
}

export { API_BASE };
