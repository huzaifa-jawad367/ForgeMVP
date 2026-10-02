import React, { useState, useEffect } from 'react';
import { useIncidentEvidence, resolveIncident, API_BASE } from '../hooks/useForgeApi';

const TYPE_ICONS = {
  confidence_drop: '🔴',
  blur_detected: '🌫️',
  fps_drop: '⚡',
  camera_error: '📷',
  temperature: '🌡️',
};

const EVIDENCE_LABELS = ['Pre-Incident', 'Incident', 'Post-Incident'];

export default function IncidentModal({ incident, onClose, onResolved }) {
  const { data: evidence } = useIncidentEvidence(incident?.id);
  const [carouselIdx, setCarouselIdx] = useState(0);
  const [resolving, setResolving] = useState(false);

  /* Reset carousel on incident change */
  useEffect(() => setCarouselIdx(0), [incident?.id]);

  if (!incident) return null;

  const icon = TYPE_ICONS[incident.incident_type] || '⚠️';
  const isActive = incident.status === 'active';
  const isCritical = incident.severity === 'critical';

  const evidenceFiles = evidence?.evidence_files || evidence?.frames || [];
  const hasEvidence = evidenceFiles.length > 0;

  const handleResolve = async () => {
    setResolving(true);
    try {
      await resolveIncident(incident.id);
      onResolved?.(incident.id);
    } catch (e) {
      console.error('Failed to resolve:', e);
    } finally {
      setResolving(false);
    }
  };

  const prevSlide = () => setCarouselIdx((p) => (p > 0 ? p - 1 : evidenceFiles.length - 1));
  const nextSlide = () => setCarouselIdx((p) => (p < evidenceFiles.length - 1 ? p + 1 : 0));

  /* Build evidence image URL */
  const evidenceUrl = (filename) =>
    `${API_BASE}/evidence/incidents/${incident.id}/${filename}`;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal fade-in" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal__header">
          <div className="modal__title-row">
            <span className="modal__icon">{icon}</span>
            <h2 className="modal__title">
              {(incident.incident_type || 'unknown').replace(/_/g, ' ')}
            </h2>
            <span className={`modal__severity ${isCritical ? 'modal__severity--critical' : 'modal__severity--warning'}`}>
              {incident.severity}
            </span>
            <span className={`modal__status ${isActive ? 'modal__status--active' : 'modal__status--resolved'}`}>
              {isActive ? 'ACTIVE' : 'RESOLVED'}
            </span>
          </div>
          <button className="modal__close" onClick={onClose}>✕</button>
        </div>

        {/* Metadata grid */}
        <div className="modal__meta">
          <MetaItem label="Incident ID" value={incident.id} mono />
          <MetaItem label="Started" value={formatDt(incident.started_at)} />
          <MetaItem label="Resolved" value={incident.resolved_at ? formatDt(incident.resolved_at) : '—'} />
          <MetaItem label="Duration" value={computeDuration(incident.started_at, incident.resolved_at)} mono />
        </div>

        {/* Evidence carousel */}
        {hasEvidence && (
          <div className="modal__evidence">
            <h3 className="modal__section-title">Evidence Frames</h3>
            <div className="carousel">
              <button className="carousel__btn carousel__btn--prev" onClick={prevSlide}>‹</button>
              <div className="carousel__frame">
                <img
                  className="carousel__img"
                  src={evidenceUrl(evidenceFiles[carouselIdx])}
                  alt={EVIDENCE_LABELS[carouselIdx] || `Frame ${carouselIdx + 1}`}
                  onError={(e) => { e.target.style.display = 'none'; }}
                />
                <span className="carousel__label mono">
                  {EVIDENCE_LABELS[carouselIdx] || `Frame ${carouselIdx + 1}`}
                </span>
              </div>
              <button className="carousel__btn carousel__btn--next" onClick={nextSlide}>›</button>
            </div>
            <div className="carousel__dots">
              {evidenceFiles.map((_, idx) => (
                <button
                  key={idx}
                  className={`carousel__dot ${idx === carouselIdx ? 'carousel__dot--active' : ''}`}
                  onClick={() => setCarouselIdx(idx)}
                />
              ))}
            </div>
          </div>
        )}

        {/* Metrics snapshot */}
        {incident.metrics_snapshot && (
          <div className="modal__snapshot">
            <h3 className="modal__section-title">Metrics Snapshot</h3>
            <div className="modal__snapshot-grid">
              {Object.entries(incident.metrics_snapshot).map(([k, v]) => (
                <div key={k} className="snapshot-chip">
                  <span className="snapshot-chip__label">{k.replace(/_/g, ' ')}</span>
                  <span className="snapshot-chip__value mono">
                    {typeof v === 'number' ? v.toFixed(2) : String(v)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="modal__actions">
          {isActive && (
            <button
              className="btn btn--resolve"
              onClick={handleResolve}
              disabled={resolving}
            >
              {resolving ? 'Resolving…' : '✓ Resolve Incident'}
            </button>
          )}
          <button className="btn btn--ghost" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

/* Helpers */
function MetaItem({ label, value, mono }) {
  return (
    <div className="meta-item">
      <span className="meta-item__label">{label}</span>
      <span className={`meta-item__value ${mono ? 'mono' : ''}`}>{value ?? '—'}</span>
    </div>
  );
}

function formatDt(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  });
}

function computeDuration(start, end) {
  if (!start) return '—';
  const s = new Date(start).getTime();
  const e = end ? new Date(end).getTime() : Date.now();
  const diff = Math.max(0, e - s);
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  return `${mins}m ${secs % 60}s`;
}
