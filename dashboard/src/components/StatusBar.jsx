import React, { useState, useEffect } from 'react';
import { useEdgeStatus } from '../hooks/useForgeApi';

export default function StatusBar({ status, pipeline }) {
  const [elapsed, setElapsed] = useState('00:00:00');
  const { data: edgeStatus } = useEdgeStatus();
  const isEdgeConnected = Boolean(edgeStatus?.is_connected);

  /* Compute uptime from status.start_time or status.started_at */
  useEffect(() => {
    const startTime = status?.start_time || status?.started_at;
    if (!startTime) {
      setElapsed('00:00:00');
      return;
    }
    const tick = () => {
      const start = new Date(startTime).getTime();
      const diff = Math.max(0, Date.now() - start);
      const h = String(Math.floor(diff / 3600000)).padStart(2, '0');
      const m = String(Math.floor((diff % 3600000) / 60000)).padStart(2, '0');
      const s = String(Math.floor((diff % 60000) / 1000)).padStart(2, '0');
      setElapsed(`${h}:${m}:${s}`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [status?.start_time, status?.started_at]);

  const isRunning = Boolean(status?.is_running ?? (status?.status === 'running'));

  /* Prefer pipeline metadata when available, fall back to API status */
  const sourceName = status?.source || pipeline?.source || status?.source_name || 'visa:pcb1';
  const sourceType = pipeline?.sourceType || (status?.source?.startsWith('visa') ? 'conveyor stream' : 'stream');
  const framesProcessed = status?.frames_processed ?? 0;
  const totalIncidents = status?.incidents_total ?? status?.total_incidents ?? 0;

  return (
    <header className="status-bar">
      {/* Left cluster */}
      <div className="status-bar__left">
        <div className="forge-logo">
          <span className="forge-logo__icon">⬡</span>
          <span className="forge-logo__text">FORGE</span>
        </div>

        <div className="status-bar__divider" />

        <div className={`pipeline-badge ${isRunning ? 'pipeline-badge--running' : 'pipeline-badge--stopped'}`}>
          <span className="pipeline-badge__dot" />
          <span className="pipeline-badge__label">
            {isRunning ? 'PIPELINE ACTIVE' : 'PIPELINE STOPPED'}
          </span>
        </div>

        <div className="status-bar__divider" />

        {/* Edge Node Status Badge */}
        <div className={`edge-badge ${isEdgeConnected ? 'edge-badge--online' : 'edge-badge--offline'}`}>
          <span className="edge-badge__dot" />
          <span className="edge-badge__label">
            {isEdgeConnected ? `EDGE: ${edgeStatus?.edge_id || 'ONLINE'}` : 'EDGE: OFFLINE'}
          </span>
          {isEdgeConnected && (
            <span
              className={`edge-badge__buffer mono ${(edgeStatus?.queue_size ?? 0) > 10 ? 'edge-badge__buffer--warning' : ''}`}
              title="Frames buffered at edge waiting to sync"
            >
              BUF: {edgeStatus?.queue_size ?? 0}
            </span>
          )}
        </div>

        <div className="status-bar__divider" />

        <div className="source-info">
          <span className="source-info__label">SOURCE</span>
          <span className="source-info__value">{sourceName}</span>
          <span className="source-info__type">{sourceType}</span>
        </div>

        {/* Show model info when pipeline metadata is available */}
        {pipeline?.model && (
          <>
            <div className="status-bar__divider" />
            <div className="source-info">
              <span className="source-info__label">MODEL</span>
              <span className="source-info__value">{pipeline.model}</span>
              <span className="source-info__type">{pipeline.modelVersion}</span>
            </div>
          </>
        )}
      </div>

      {/* Right cluster */}
      <div className="status-bar__right">
        {isEdgeConnected && (
          <div className="metric-chip">
            <span className="metric-chip__label">EDGE SYNCED</span>
            <span className="metric-chip__value mono">{(edgeStatus?.total_synced ?? 0).toLocaleString()}</span>
          </div>
        )}

        <div className="metric-chip">
          <span className="metric-chip__label">FRAMES</span>
          <span className="metric-chip__value mono">{framesProcessed.toLocaleString()}</span>
        </div>

        <div className="metric-chip">
          <span className="metric-chip__label">UPTIME</span>
          <span className="metric-chip__value mono">{elapsed}</span>
        </div>

        <div className={`incident-badge ${totalIncidents > 0 ? 'incident-badge--active' : ''}`}>
          <span className="incident-badge__count mono">{totalIncidents}</span>
          <span className="incident-badge__label">INCIDENTS</span>
        </div>
      </div>
    </header>
  );
}
