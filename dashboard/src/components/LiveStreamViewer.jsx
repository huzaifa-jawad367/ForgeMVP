import React, { useState, useEffect } from 'react';
import { API_BASE, startPipeline, stopPipeline } from '../hooks/useForgeApi';

export default function LiveStreamViewer({ pipeline, latestMetrics, pipelineStatus }) {
  const [streamError, setStreamError] = useState(false);
  const [retryNonce, setRetryNonce] = useState(0);
  const [actionLoading, setActionLoading] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const isRunning = pipelineStatus?.is_running || pipelineStatus?.status === 'running';
  const hasAnomaly = latestMetrics?.has_anomaly || false;
  const fps = latestMetrics?.fps ?? 0;
  const latency = latestMetrics?.inference_time_ms ?? 0;
  const confidence = latestMetrics?.mean_confidence ?? 0;
  const noiseLevel = latestMetrics?.noise_level ?? 0;

  // Stream URL with nonce for cache-busting during reconnects
  const streamUrl = `${API_BASE}/api/stream/live?t=${retryNonce}`;

  const handleStartPipeline = async () => {
    setActionLoading(true);
    try {
      const source = pipeline?.source || 'visa:pcb1';
      await startPipeline({ input: source, fps: 10, loop: true, model: 'efficientad' });
      setStreamError(false);
      setRetryNonce(Date.now());
    } catch (err) {
      console.error('Failed to start pipeline:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleStopPipeline = async () => {
    setActionLoading(true);
    try {
      await stopPipeline();
    } catch (err) {
      console.error('Failed to stop pipeline:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSnapshot = () => {
    window.open(`${API_BASE}/api/stream/frame`, '_blank');
  };

  return (
    <div className={`live-stream-card ${hasAnomaly ? 'live-stream-card--alert' : ''} ${isFullscreen ? 'live-stream-card--fullscreen' : ''} fade-in`}>
      {/* ── Header ── */}
      <div className="live-stream-card__header">
        <div className="live-stream-card__title-group">
          <span className={`live-stream-card__dot ${isRunning ? 'live-stream-card__dot--active' : ''}`} />
          <h3 className="live-stream-card__title">Live Inference Stream</h3>
          <span className="live-stream-card__model-tag mono">
            {pipeline?.model || 'EfficientAD Medium · PCB1'}
          </span>
          {latestMetrics?.edge_id && (
            <span className="live-stream-card__edge-tag mono" title="Inference running on Edge Node">
              EDGE: {latestMetrics.edge_id}
            </span>
          )}
        </div>

        <div className="live-stream-card__actions">
          <span className={`stream-status-pill ${hasAnomaly ? 'stream-status-pill--defect' : isRunning ? 'stream-status-pill--ok' : 'stream-status-pill--idle'}`}>
            {hasAnomaly ? '⚠ DEFECT / ANOMALY DETECTED' : isRunning ? '● INSPECTION OK' : '○ IDLE'}
          </span>

          <button
            className="btn btn--icon"
            onClick={handleSnapshot}
            title="Open JPEG Snapshot"
            disabled={!isRunning}
          >
            📷 Snapshot
          </button>

          {isRunning ? (
            <button
              className="btn btn--danger-sm"
              onClick={handleStopPipeline}
              disabled={actionLoading}
            >
              {actionLoading ? '…' : '■ Stop'}
            </button>
          ) : (
            <button
              className="btn btn--primary-sm"
              onClick={handleStartPipeline}
              disabled={actionLoading}
            >
              {actionLoading ? '…' : '▶ Start Conveyor'}
            </button>
          )}

          <button
            className="btn btn--icon"
            onClick={() => setIsFullscreen((f) => !f)}
            title={isFullscreen ? 'Exit Fullscreen' : 'Expand Stream'}
          >
            {isFullscreen ? '✕' : '⤢'}
          </button>
        </div>
      </div>

      {/* ── Video Viewport ── */}
      <div className="live-stream-card__viewport">
        {isRunning && !streamError ? (
          <img
            src={streamUrl}
            alt="Live Model Inference Stream"
            className="live-stream-card__img"
            onError={() => {
              setStreamError(true);
            }}
          />
        ) : (
          <div className="live-stream-card__placeholder">
            <div className="live-stream-card__placeholder-icon">📡</div>
            <h4 className="live-stream-card__placeholder-title">
              {isRunning ? 'Connecting to Live Video Feed…' : 'Inspection Stream Paused'}
            </h4>
            <p className="live-stream-card__placeholder-sub">
              {isRunning
                ? 'Waiting for frames from conveyor pipeline...'
                : 'Start the VisA PCB-1 dataset conveyor stream to observe live real-time defect inference.'}
            </p>
            {!isRunning && (
              <button
                className="btn btn--primary"
                onClick={handleStartPipeline}
                disabled={actionLoading}
                style={{ marginTop: 14 }}
              >
                {actionLoading ? 'Launching…' : '▶ Start PCB1 Conveyor Belt'}
              </button>
            )}
            {streamError && isRunning && (
              <button
                className="btn btn--reset"
                onClick={() => {
                  setStreamError(false);
                  setRetryNonce(Date.now());
                }}
                style={{ marginTop: 10 }}
              >
                ↻ Retry Stream Connection
              </button>
            )}
          </div>
        )}

        {/* ── Real-Time HUD Overlay ── */}
        {isRunning && !streamError && (
          <div className="live-stream-card__hud">
            <div className="hud-metric">
              <span className="hud-metric__label">RATE</span>
              <span className="hud-metric__val mono">{fps.toFixed(1)} FPS</span>
            </div>
            <div className="hud-metric">
              <span className="hud-metric__label">LATENCY</span>
              <span className="hud-metric__val mono">{latency.toFixed(1)} ms</span>
            </div>
            <div className="hud-metric">
              <span className="hud-metric__label">ANOMALY CONF</span>
              <span className="hud-metric__val mono" style={{ color: confidence >= 0.5 ? 'var(--red)' : 'var(--green)' }}>
                {confidence.toFixed(3)}
              </span>
            </div>
            {noiseLevel > 0 && (
              <div className="hud-metric hud-metric--noise">
                <span className="hud-metric__label">SENSOR NOISE</span>
                <span className="hud-metric__val mono" style={{ color: 'var(--amber)' }}>
                  {noiseLevel.toFixed(0)}%
                </span>
              </div>
            )}
            {latestMetrics?.edge_id && (
              <div className="hud-metric hud-metric--edge">
                <span className="hud-metric__label">EDGE NODE</span>
                <span className="hud-metric__val mono" style={{ color: 'var(--cyan)' }}>
                  {latestMetrics.edge_id}
                </span>
              </div>
            )}
            {latestMetrics?.edge_buffer_size !== undefined && (
              <div className="hud-metric hud-metric--buffer">
                <span className="hud-metric__label">EDGE QUEUE</span>
                <span className="hud-metric__val mono" style={{ color: latestMetrics.edge_buffer_size > 15 ? 'var(--amber)' : 'var(--text-bright)' }}>
                  {latestMetrics.edge_buffer_size}
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
