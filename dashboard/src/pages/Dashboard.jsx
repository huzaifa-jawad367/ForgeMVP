import React from 'react';
import { Link } from 'react-router-dom';
import PipelineCard from '../components/PipelineCard';
import pipelines from '../data/mockPipelines';

/* ── Summary counters ── */
function useSummary() {
  const total    = pipelines.length;
  const active   = pipelines.filter((p) => p.status !== 'stopped').length;
  const degraded = pipelines.filter((p) => p.status === 'warning' || p.status === 'critical').length;
  const totalInc = pipelines.reduce((sum, p) => sum + p.incidents, 0);
  return { total, active, degraded, totalInc };
}

export default function Dashboard() {
  const { total, active, degraded, totalInc } = useSummary();

  return (
    <div className="dashboard">
      {/* Background grid */}
      <div className="app__bg" />

      {/* ── Top header ── */}
      <header className="dashboard__header">
        <div className="dashboard__header-left">
          <div className="forge-logo">
            <span className="forge-logo__icon">⬡</span>
            <span className="forge-logo__text">FORGE</span>
          </div>
          <div className="status-bar__divider" />
          <h1 className="dashboard__title">Fleet Dashboard</h1>
        </div>

        <div className="dashboard__counters">
          <CounterChip label="Pipelines" value={total} color="var(--cyan)" />
          <CounterChip label="Active" value={active} color="var(--green)" />
          <CounterChip label="Degraded" value={degraded} color={degraded > 0 ? 'var(--amber)' : 'var(--text-dim)'} />
          <CounterChip label="Incidents" value={totalInc} color={totalInc > 0 ? 'var(--red)' : 'var(--green)'} glow={totalInc > 0} />
        </div>
      </header>

      {/* ── Pipeline grid ── */}
      <main className="dashboard__grid">
        {pipelines.map((p, i) => (
          <PipelineCard key={p.id} pipeline={p} />
        ))}
      </main>
    </div>
  );
}

/* ── Small counter chip ── */
function CounterChip({ label, value, color, glow }) {
  return (
    <div className={`counter-chip ${glow ? 'counter-chip--glow' : ''}`}>
      <span className="counter-chip__value mono" style={{ color }}>{value}</span>
      <span className="counter-chip__label">{label}</span>
    </div>
  );
}
