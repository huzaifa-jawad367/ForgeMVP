import React from 'react';

const TYPE_ICONS = {
  confidence_drop: '🔴',
  blur_detected: '🌫️',
  fps_drop: '⚡',
  camera_error: '📷',
  temperature: '🌡️',
};

function timeAgo(isoStr) {
  if (!isoStr) return '—';
  const diff = Math.max(0, Date.now() - new Date(isoStr).getTime());
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ${mins % 60}m ago`;
}

function formatTime(isoStr) {
  if (!isoStr) return '—';
  return new Date(isoStr).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}


function formatSubsystemPill(subsystem) {
  if (!subsystem) return '';
  const map = {
    'FAILURE_OPTICAL_DEFOCUS': '[OPTICAL: DEFOCUS]',
    'FAILURE_OPTICAL_SENSOR_NOISE': '[OPTICAL: NOISE]',
    'FAILURE_ENVIRONMENTAL_LIGHTING': '[OPTICAL: LIGHTING]',
    'FAILURE_SUBSYSTEM_CAMERA': '[HARDWARE: CAMERA]',
    'FAILURE_HARDWARE_GPU_EXHAUSTION': '[HARDWARE: GPU]',
    'FAILURE_NETWORK_PARTITION': '[NETWORK: PARTITION]',
    'FAILURE_MODEL_INFERENCE_STALL': '[MODEL: STALL]'
  };
  return map[subsystem] || `[${subsystem.replace('FAILURE_', '').replace(/_/g, ' ')}]`;
}

export default function IncidentFeed({ incidents, onSelect }) {
  const list = incidents || [];

  return (
    <aside className="incident-feed">
      <div className="incident-feed__header">
        <h2 className="incident-feed__title">
          <span className="incident-feed__icon">⚠</span>
          Incident Feed
        </h2>
        <span className="incident-feed__count mono">{list.length}</span>
      </div>

      <div className="incident-feed__list">
        {list.length === 0 && (
          <div className="incident-feed__empty">
            <span className="incident-feed__empty-icon">✓</span>
            <p>No incidents detected</p>
            <p className="incident-feed__empty-sub">System operating normally</p>
          </div>
        )}

        {list.map((inc, i) => {
          const isActive = inc.status === 'active';
          const isCritical = inc.severity === 'critical';
          const icon = TYPE_ICONS[inc.incident_type] || '⚠️';

          return (
            <button
              key={inc.id || i}
              className={`incident-card fade-in ${isActive ? 'incident-card--active' : 'incident-card--resolved'}`}
              style={{ animationDelay: `${i * 0.04}s` }}
              onClick={() => onSelect(inc)}
            >
              <div className="incident-card__top">
                <span className="incident-card__icon">{icon}</span>
                <span className="incident-card__type">
                  {(inc.incident_type || 'unknown').replace(/_/g, ' ')}
                </span>
                {inc.subsystem_attribution && (
                  <span className="incident-card__subsystem">
                    {formatSubsystemPill(inc.subsystem_attribution)}
                  </span>
                )}
                <span
                  className={`incident-card__severity ${isCritical ? 'incident-card__severity--critical' : 'incident-card__severity--warning'}`}
                >
                  {inc.severity || 'warning'}
                </span>
              </div>

              <div className="incident-card__bottom">
                <span className="incident-card__time mono">{formatTime(inc.started_at)}</span>
                <span className="incident-card__ago">{timeAgo(inc.started_at)}</span>
                <span className={`incident-card__status ${isActive ? 'incident-card__status--active' : 'incident-card__status--resolved'}`}>
                  {isActive ? 'ACTIVE' : 'RESOLVED'}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
