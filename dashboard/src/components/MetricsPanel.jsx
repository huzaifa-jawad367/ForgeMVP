import React, { useMemo } from 'react';
import {
  AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import CircularGauge from './CircularGauge';

/* ── Custom tooltip ── */
function CyberTooltip({ active, payload, label, suffix = '' }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="cyber-tooltip">
      <p className="cyber-tooltip__label">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="cyber-tooltip__value" style={{ color: p.color }}>
          {p.name}: <span className="mono">{Number(p.value).toFixed(2)}{suffix}</span>
        </p>
      ))}
    </div>
  );
}

export default function MetricsPanel({ metricsHistory, latestMetrics }) {
  /* Derive chart data from history array */
  const fpsData = useMemo(() =>
    (metricsHistory || []).map((m, i) => ({
      time: i,
      fps: m?.fps ?? 0,
    })).slice(-60),
  [metricsHistory]);

  const confidenceData = useMemo(() =>
    (metricsHistory || []).map((m, i) => ({
      time: i,
      confidence: m?.mean_confidence ?? 0,
    })).slice(-60),
  [metricsHistory]);

  const noiseData = useMemo(() =>
    (metricsHistory || []).map((m, i) => ({
      time: i,
      noise_level: m?.noise_level ?? 0,
      noise_score: m?.noise_score ?? 0,
    })).slice(-60),
  [metricsHistory]);

  const latest = latestMetrics || {};
  const sys = latest.system || {};

  return (
    <section className="metrics-panel">
      {/* ── FPS Chart ── */}
      <div className="chart-card chart-card--fps fade-in">
        <div className="chart-card__header">
          <h3 className="chart-card__title">
            <span className="chart-card__dot" style={{ background: 'var(--cyan)' }} />
            Streaming Throughput (FPS)
          </h3>
          <span className="chart-card__live mono">
            {(latest.fps ?? 0).toFixed(1)} FPS
          </span>
        </div>
        <div className="chart-card__body">
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={fpsData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="fpsGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00f0ff" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#00f0ff" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="time" tick={false} axisLine={false} />
              <YAxis
                domain={[0, 'auto']}
                tick={{ fill: '#555770', fontSize: 10, fontFamily: 'var(--font-mono)' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<CyberTooltip suffix=" fps" />} />
              <Area
                type="monotone"
                dataKey="fps"
                name="FPS"
                stroke="#00f0ff"
                strokeWidth={2}
                fill="url(#fpsGrad)"
                animationDuration={300}
                dot={false}
                activeDot={{ r: 4, stroke: '#00f0ff', strokeWidth: 2, fill: '#0a0a0f' }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Confidence Chart ── */}
      <div className="chart-card chart-card--conf fade-in" style={{ animationDelay: '0.1s' }}>
        <div className="chart-card__header">
          <h3 className="chart-card__title">
            <span className="chart-card__dot" style={{ background: 'var(--green)' }} />
            Anomaly Score / Detection Confidence
          </h3>
          <span className="chart-card__live mono" style={{ color: (latest.mean_confidence ?? 0) >= 0.5 ? 'var(--red)' : 'var(--green)' }}>
            {(latest.mean_confidence ?? 0).toFixed(3)}
          </span>
        </div>
        <div className="chart-card__body">
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={confidenceData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="confGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00ff88" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#00ff88" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="time" tick={false} axisLine={false} />
              <YAxis
                domain={[0, 1]}
                tick={{ fill: '#555770', fontSize: 10, fontFamily: 'var(--font-mono)' }}
                axisLine={false}
                tickLine={false}
                ticks={[0, 0.25, 0.5, 0.75, 1.0]}
              />
              <Tooltip content={<CyberTooltip />} />
              <ReferenceLine
                y={0.5}
                stroke="#ff2d55"
                strokeDasharray="6 4"
                strokeWidth={1.5}
                label={{
                  value: 'ANOMALY THRESHOLD (0.50)',
                  position: 'insideTopRight',
                  fill: '#ff2d55',
                  fontSize: 10,
                  fontFamily: 'var(--font-mono)',
                }}
              />
              <Line
                type="monotone"
                dataKey="confidence"
                name="Confidence"
                stroke={(latest.mean_confidence ?? 0) >= 0.5 ? '#ff2d55' : '#00ff88'}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, stroke: '#00ff88', strokeWidth: 2, fill: '#0a0a0f' }}
                animationDuration={300}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Sensor Noise Injection Real-Time Trend ── */}
      <div className="chart-card chart-card--noise fade-in" style={{ animationDelay: '0.15s' }}>
        <div className="chart-card__header">
          <h3 className="chart-card__title">
            <span className="chart-card__dot" style={{ background: 'var(--amber)' }} />
            Sensor Noise Injection Trend
          </h3>
          <span className="chart-card__live mono" style={{ color: 'var(--amber)' }}>
            {(latest.noise_level ?? 0).toFixed(0)}%
          </span>
        </div>
        <div className="chart-card__body">
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={noiseData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="noiseGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ffb800" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#ffb800" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="time" tick={false} axisLine={false} />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: '#555770', fontSize: 10, fontFamily: 'var(--font-mono)' }}
                axisLine={false}
                tickLine={false}
                ticks={[0, 25, 50, 75, 100]}
              />
              <Tooltip content={<CyberTooltip suffix="%" />} />
              <Area
                type="monotone"
                dataKey="noise_level"
                name="Noise Injection Level"
                stroke="#ffb800"
                strokeWidth={2}
                fill="url(#noiseGrad)"
                animationDuration={300}
                dot={false}
                activeDot={{ r: 4, stroke: '#ffb800', strokeWidth: 2, fill: '#0a0a0f' }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── System metrics row ── */}
      <div className="system-metrics fade-in" style={{ animationDelay: '0.2s' }}>
        <h3 className="system-metrics__title">System Resources</h3>
        <div className="system-metrics__gauges">
          <CircularGauge
            value={sys.cpu_percent ?? 0}
            label="CPU"
            color={getGaugeColor(sys.cpu_percent ?? 0)}
            glowing
          />
          <CircularGauge
            value={sys.memory_percent ?? 0}
            label="RAM"
            color={getGaugeColor(sys.memory_percent ?? 0)}
            glowing
          />
          <CircularGauge
            value={sys.gpu_percent ?? 0}
            label="GPU"
            color={getGaugeColor(sys.gpu_percent ?? 0)}
            glowing
          />
        </div>
      </div>

      {/* ── Image quality & Sensor metrics ── */}
      <div className="image-quality fade-in" style={{ animationDelay: '0.25s' }}>
        <h3 className="image-quality__title">Optical & Sensor Quality</h3>
        <div className="image-quality__gauges">
          <CircularGauge
            value={latest.brightness ?? 0}
            max={255}
            label="Brightness"
            unit=""
            color="var(--amber)"
            size={72}
            stroke={5}
            glowing
          />
          <CircularGauge
            value={latest.blur_score ?? 0}
            max={1000}
            label="Blur Score"
            unit=""
            color="var(--purple)"
            size={72}
            stroke={5}
            glowing
          />
          <CircularGauge
            value={latest.noise_level ?? 0}
            max={100}
            label="Noise Level"
            unit="%"
            color={latest.noise_level > 40 ? 'var(--red)' : latest.noise_level > 10 ? 'var(--amber)' : 'var(--cyan)'}
            size={72}
            stroke={5}
            glowing={latest.noise_level > 0}
          />
        </div>
      </div>

      {/* ── Edge Node & Buffer Resilience ── */}
      <div className="edge-metrics-card fade-in" style={{ animationDelay: '0.3s' }}>
        <div className="edge-metrics-card__header">
          <div className="edge-metrics-card__title-group">
            <span className={`edge-metrics-card__dot ${latest.edge_id ? 'edge-metrics-card__dot--active' : ''}`} />
            <h3 className="edge-metrics-card__title">Edge Buffer & Sync Health</h3>
          </div>
          <span className="edge-metrics-card__badge mono">
            {latest.edge_id ? `NODE: ${latest.edge_id}` : 'STANDBY'}
          </span>
        </div>
        <div className="edge-metrics-card__body">
          <div className="edge-metric-item">
            <span className="edge-metric-item__label">EDGE QUEUE</span>
            <span
              className="edge-metric-item__value mono"
              style={{ color: (latest.edge_buffer_size ?? 0) > 20 ? 'var(--amber)' : 'var(--cyan)' }}
            >
              {latest.edge_buffer_size ?? 0}
              <span className="edge-metric-item__unit"> frames</span>
            </span>
          </div>
          <div className="edge-metric-item">
            <span className="edge-metric-item__label">SYNCED TOTAL</span>
            <span className="edge-metric-item__value mono" style={{ color: 'var(--green)' }}>
              {(latest.edge_total_synced ?? 0).toLocaleString()}
              <span className="edge-metric-item__unit"> pkts</span>
            </span>
          </div>
          <div className="edge-metric-item">
            <span className="edge-metric-item__label">LATENCY</span>
            <span className="edge-metric-item__value mono">
              {(latest.inference_time_ms ?? 0).toFixed(1)}
              <span className="edge-metric-item__unit"> ms</span>
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

function getGaugeColor(pct) {
  if (pct > 85) return 'var(--red)';
  if (pct > 60) return 'var(--amber)';
  return 'var(--cyan)';
}
