import { useState, useEffect, useRef } from 'react';
import { API_BASE } from './useForgeApi';

const MAX_HISTORY = 120;

const getWsUrl = (pipelineId) => {
  let base = API_BASE;
  if (!base.startsWith('http')) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    base = `${protocol}//${host}`;
  } else {
    base = base.replace(/^http/, 'ws');
  }
  return `${base}/ws/telemetry${pipelineId ? `?pipelineId=${pipelineId}` : ''}`;
};

export function useTelemetryStream(pipelineId) {
  const [latestMetrics, setLatestMetrics] = useState(null);
  const [metricsHistory, setMetricsHistory] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [isConnected, setIsConnected] = useState(false);

  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const latestMetricsRef = useRef(null);

  // Keep ref up-to-date so callbacks can access current state without stale closures
  useEffect(() => {
    latestMetricsRef.current = latestMetrics;
  }, [latestMetrics]);

  // Fetch initial history and active incidents on mount
  useEffect(() => {
    let cancelled = false;

    const fetchInitialData = async () => {
      try {
        // Fetch incidents
        const incRes = await fetch(`${API_BASE}/api/incidents?limit=30`);
        if (!incRes.ok) throw new Error(`HTTP ${incRes.status}`);
        const incJson = await incRes.json();
        
        // Fetch recent metrics history (limit 60)
        const metricsRes = await fetch(`${API_BASE}/api/metrics?source_id=1&limit=60`);
        if (!metricsRes.ok) throw new Error(`HTTP ${metricsRes.status}`);
        const metricsJson = await metricsRes.json();

        if (!cancelled) {
          setIncidents(incJson);
          
          // Map metrics from database rows to visual layout format
          const history = metricsJson
            .map((m) => ({
              fps: m.fps,
              mean_confidence: m.mean_confidence,
              brightness: m.brightness,
              blur_score: m.blur_score,
              timestamp: m.timestamp_ms,
              system: {
                cpu_percent: 0, // placeholders until real system metrics arrive
                memory_percent: 0,
                gpu_percent: 0,
              },
            }))
            .reverse(); // database query returned desc order; charts need asc
          setMetricsHistory(history);
          
          if (metricsJson.length > 0) {
            const lastRow = metricsJson[0];
            setLatestMetrics({
              fps: lastRow.fps,
              mean_confidence: lastRow.mean_confidence,
              brightness: lastRow.brightness,
              blur_score: lastRow.blur_score,
              timestamp: lastRow.timestamp_ms,
              system: {
                cpu_percent: 0,
                memory_percent: 0,
                gpu_percent: 0,
              },
            });
          }
        }
      } catch (err) {
        console.error('Failed to fetch initial telemetry data:', err);
      }
    };

    fetchInitialData();

    return () => {
      cancelled = true;
    };
  }, [pipelineId]);

  // Connect to WebSocket with auto-reconnection
  useEffect(() => {
    const connect = () => {
      if (wsRef.current) return;

      const wsUrl = getWsUrl(pipelineId);
      console.log(`Connecting to telemetry stream: ${wsUrl}`);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('Telemetry WebSocket connected.');
        setIsConnected(true);
        if (reconnectTimerRef.current) {
          clearTimeout(reconnectTimerRef.current);
          reconnectTimerRef.current = null;
        }
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          
          if (msg.type === 'frame_metrics') {
            const data = msg.data;
            
            setLatestMetrics((prev) => {
              const merged = {
                ...(prev || {}),
                fps: data.fps,
                mean_confidence: data.mean_confidence,
                brightness: data.brightness,
                blur_score: data.blur_score,
                timestamp: data.timestamp_ms,
              };
              if (!merged.system) {
                merged.system = { cpu_percent: 0, memory_percent: 0, gpu_percent: 0 };
              }
              return merged;
            });

            setMetricsHistory((prev) => {
              const currentLatest = latestMetricsRef.current;
              const newPoint = {
                fps: data.fps,
                mean_confidence: data.mean_confidence,
                brightness: data.brightness,
                blur_score: data.blur_score,
                timestamp: data.timestamp_ms,
                system: currentLatest?.system || { cpu_percent: 0, memory_percent: 0, gpu_percent: 0 },
              };
              
              // Prevent duplicate frames with same timestamp
              if (prev.length > 0 && prev[prev.length - 1].timestamp === newPoint.timestamp) {
                return prev;
              }
              
              const next = [...prev, newPoint];
              return next.length > MAX_HISTORY ? next.slice(-MAX_HISTORY) : next;
            });
            
          } else if (msg.type === 'system_metrics') {
            const data = msg.data;
            
            setLatestMetrics((prev) => {
              const merged = {
                ...(prev || {}),
                system: {
                  cpu_percent: data.cpu_percent,
                  memory_percent: data.memory_percent,
                  gpu_percent: data.gpu_utilization ?? 0,
                },
              };
              return merged;
            });
            
          } else if (msg.type === 'incident') {
            const incident = msg.data;
            
            setIncidents((prev) => {
              const idx = prev.findIndex((inc) => inc.id === incident.id);
              if (idx > -1) {
                // Update existing incident (e.g. marked as resolved)
                const updated = [...prev];
                updated[idx] = incident;
                return updated;
              } else {
                // Prepend new active incident to the top of the feed
                return [incident, ...prev];
              }
            });
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onclose = () => {
        console.log('Telemetry WebSocket disconnected. Reconnecting in 3s...');
        setIsConnected(false);
        wsRef.current = null;
        reconnectTimerRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = (err) => {
        console.error('Telemetry WebSocket error:', err);
        ws.close();
      };
    };

    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
    };
  }, [pipelineId]);

  return {
    latestMetrics,
    metricsHistory,
    incidents,
    isConnected,
  };
}
