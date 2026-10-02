import React from 'react';

/**
 * CircularGauge — SVG-based circular progress indicator.
 *
 * Props:
 *   value     — 0-100  (current)
 *   max       — max value (default 100)
 *   size      — px diameter (default 72)
 *   stroke    — stroke width (default 5)
 *   color     — accent colour (default var(--cyan))
 *   label     — text inside the ring
 *   unit      — suffix like '%' or '°C'
 *   glowing   — apply glow shadow
 */
export default function CircularGauge({
  value = 0,
  max = 100,
  size = 72,
  stroke = 5,
  color = 'var(--cyan)',
  label = '',
  unit = '%',
  glowing = false,
}) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.min(Math.max(value / max, 0), 1);
  const offset = circumference * (1 - pct);

  return (
    <div className="circular-gauge" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Background track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={stroke}
        />
        {/* Foreground arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{
            transition: 'stroke-dashoffset 0.8s cubic-bezier(0.4,0,0.2,1)',
            filter: glowing ? `drop-shadow(0 0 6px ${color})` : 'none',
          }}
        />
      </svg>
      <div className="circular-gauge__inner">
        <span className="circular-gauge__value" style={{ color }}>
          {typeof value === 'number' ? Math.round(value) : value}
          <span className="circular-gauge__unit">{unit}</span>
        </span>
        {label && <span className="circular-gauge__label">{label}</span>}
      </div>
    </div>
  );
}
