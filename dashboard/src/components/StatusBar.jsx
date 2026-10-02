import React, { useState, useEffect } from 'react';

export default function StatusBar({ status, pipeline }) {
  const [elapsed, setElapsed] = useState('00:00:00');

  /* Compute uptime from status.started_at */
  useEffect(() => {
    if (!status?.started_at) return;
    const tick = () => {
      const start = new Date(status.started_at).getTime();
      const diff = Math.max(0, Date.now() - start);
      const h = String(Math.floor(diff / 3600000)).padStart(2, '0');
      const m = String(Math.floor((diff % 3600000) / 60000)).padStart(2, '0');
      const s = String(Math.floor((diff % 60000) / 1000)).padStart(2, '0');
      setElapsed(`${h}:${m}:${s}`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [status?.started_at]);

  const isRunning = status?.status === 'running';

  /* Prefer pipeline metadata when available, fall back to API status */
  const sourceName = pipeline?.source || status?.source_name || '—';
  const sourceType = pipeline?.sourceType || status?.source_type || '—';
  const framesProcessed = status?.frames_processed ?? 0;
  const totalIncidents = status?.total_incidents ?? 0;

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
