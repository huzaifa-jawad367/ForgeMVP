import React from 'react';
import { useNavigate } from 'react-router-dom';

/* ── Status → colour mapping ── */
const STATUS_COLORS = {
  healthy:  'var(--green)',
  warning:  'var(--amber)',
  critical: 'var(--red)',
  stopped:  'var(--text-dim)',
};

const STATUS_BG = {
  healthy:  'rgba(0,255,136,0.08)',
  warning:  'rgba(255,184,0,0.08)',
  critical: 'rgba(255,45,85,0.08)',
  stopped:  'rgba(255,255,255,0.04)',
};

const STATUS_BORDER = {
  healthy:  'rgba(0,255,136,0.20)',
  warning:  'rgba(255,184,0,0.20)',
  critical: 'rgba(255,45,85,0.20)',
  stopped:  'rgba(255,255,255,0.06)',
};

const SOURCE_TYPE_ICON = {
  video:     '🎬',
  directory: '📁',
  rtsp:      '📡',
  webcam:    '📷',
  stream:    '📡',
};

export default function PipelineCard({ pipeline }) {
  const navigate = useNavigate();
  const {
    id, name, site, status, sourceType, source,
    model, modelVersion, fps, meanConfidence, incidents, lastSeen,
  } = pipeline;

  const color  = STATUS_COLORS[status] || 'var(--text-dim)';
  const bg     = STATUS_BG[status]     || STATUS_BG.stopped;
  const border = STATUS_BORDER[status] || STATUS_BORDER.stopped;

  return (
    <button
      className="pipeline-card fade-in"
      onClick={() => navigate(`/diagnostics/${id}`)}
      style={{ '--card-accent': color, '--card-accent-bg': bg, '--card-accent-border': border }}
    >
      {/* ── Header row ── */}
      <div className="pipeline-card__header">
        <div className="pipeline-card__name-group">
          <h3 className="pipeline-card__name">{name}</h3>
          <span className="pipeline-card__site">{site}</span>
        </div>
        <span className="pipeline-card__status-badge" style={{ background: bg, color, borderColor: border }}>
          <span className="pipeline-card__status-dot" style={{ background: color }} />
          {status}
        </span>
      </div>

      {/* ── Source row ── */}
      <div className="pipeline-card__row">
        <span className="pipeline-card__label">SOURCE</span>
        <span className="pipeline-card__value">
          <span className="pipeline-card__source-icon">{SOURCE_TYPE_ICON[sourceType] || '📄'}</span>
          <span className="pipeline-card__source-type">{sourceType}</span>
          <span className="pipeline-card__source-path mono">{source}</span>
        </span>
      </div>

      {/* ── Model row ── */}
      <div className="pipeline-card__row">
        <span className="pipeline-card__label">MODEL</span>
        <span className="pipeline-card__value">
          {model} <span className="pipeline-card__version mono">{modelVersion}</span>
        </span>
      </div>

      {/* ── Telemetry chips ── */}
      <div className="pipeline-card__metrics">
        <div className="pipeline-card__metric">
          <span className="pipeline-card__metric-label">FPS</span>
          <span className="pipeline-card__metric-value mono" style={{ color: fps > 0 ? 'var(--cyan)' : 'var(--text-dim)' }}>
            {fps.toFixed(1)}
          </span>
        </div>
        <div className="pipeline-card__metric">
          <span className="pipeline-card__metric-label">CONFIDENCE</span>
          <span
            className="pipeline-card__metric-value mono"
            style={{ color: meanConfidence >= 0.7 ? 'var(--green)' : meanConfidence > 0 ? 'var(--amber)' : 'var(--text-dim)' }}
          >
            {meanConfidence.toFixed(2)}
          </span>
        </div>
        <div className="pipeline-card__metric">
          <span className="pipeline-card__metric-label">INCIDENTS</span>
          <span
            className="pipeline-card__metric-value mono"
            style={{ color: incidents > 0 ? 'var(--red)' : 'var(--green)' }}
          >
            {incidents}
          </span>
        </div>
        <div className="pipeline-card__metric">
          <span className="pipeline-card__metric-label">STATUS</span>
          <span className="pipeline-card__metric-value mono" style={{ color }}>
            {lastSeen}
          </span>
        </div>
      </div>
    </button>
  );
}
