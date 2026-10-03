import React, { useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import StatusBar from '../components/StatusBar';
import MetricsPanel from '../components/MetricsPanel';
import IncidentFeed from '../components/IncidentFeed';
import IncidentModal from '../components/IncidentModal';
import LiveStreamViewer from '../components/LiveStreamViewer';
import DemoControls from '../components/DemoControls';
import { usePipelineStatus } from '../hooks/useForgeApi';
import { useTelemetryStream } from '../hooks/useTelemetry';
import pipelines from '../data/mockPipelines';

export default function DiagnosticPage() {
  const { pipelineId } = useParams();

  /* ── Find the mock pipeline matching the route param ── */
  const pipeline = pipelines.find((p) => p.id === pipelineId) || null;

  /* ── Real-time Telemetry Stream ── */
  const { latestMetrics, metricsHistory, incidents } = useTelemetryStream(pipelineId);

  /* ── API hooks ── */
  const { data: pipelineStatus } = usePipelineStatus();

  /* ── Incident modal ── */
  const [selectedIncident, setSelectedIncident] = useState(null);

  const handleIncidentResolved = useCallback(() => {
    setSelectedIncident(null);
  }, []);

  /* ── Derive incident list ── */
  const incidentList = incidents || [];

  return (
    <div className="app">
      {/* Grid / scanline background */}
      <div className="app__bg" />

      {/* Back link */}
      <div className="diag-back-bar">
        <Link to="/dashboard" className="diag-back-link">
          <span className="diag-back-link__arrow">←</span>
          Back to Dashboard
        </Link>
        {pipeline && (
          <span className="diag-back-bar__pipeline mono">
            {pipeline.name}
          </span>
        )}
      </div>

      {/* Top status bar — enriched with pipeline metadata */}
      <StatusBar status={pipelineStatus} pipeline={pipeline} />

      {/* Main content area */}
      <main className="app__main">
        <div className="app__stream-and-metrics">
          <LiveStreamViewer
            pipeline={pipeline}
            latestMetrics={latestMetrics}
            pipelineStatus={pipelineStatus}
          />
          <MetricsPanel
            metricsHistory={metricsHistory}
            latestMetrics={latestMetrics}
          />
        </div>
        <IncidentFeed
          incidents={incidentList}
          onSelect={setSelectedIncident}
        />
      </main>

      {/* Bottom demo controls */}
      <DemoControls />

      {/* Incident detail modal */}
      {selectedIncident && (
        <IncidentModal
          incident={selectedIncident}
          onClose={() => setSelectedIncident(null)}
          onResolved={handleIncidentResolved}
        />
      )}
    </div>
  );
}
