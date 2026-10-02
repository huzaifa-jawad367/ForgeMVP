import React, { useState } from 'react';
import { postDegrade, postReset } from '../hooks/useForgeApi';

const SLIDERS = [
  { key: 'blur',       label: 'Blur Injection',           unit: '%',  min: 0, max: 100 },
  { key: 'brightness', label: 'Brightness Reduction',     unit: '%',  min: 0, max: 100 },
  { key: 'confidence', label: 'Confidence Degradation',   unit: '%',  min: 0, max: 100 },
  { key: 'latency',    label: 'Latency Injection',        unit: 'ms', min: 0, max: 100 },
];

export default function DemoControls() {
  const [collapsed, setCollapsed] = useState(true);
  const [values, setValues] = useState({ blur: 0, brightness: 0, confidence: 0, latency: 0 });
  const [sending, setSending] = useState(false);

  const handleChange = (key, val) => {
    setValues((prev) => ({ ...prev, [key]: Number(val) }));
  };

  const handleApply = async () => {
    setSending(true);
    try {
      await postDegrade(values);
    } catch (e) {
      console.error('Degrade failed:', e);
    } finally {
      setSending(false);
    }
  };

  const handleReset = async () => {
    setSending(true);
    try {
      await postReset();
      setValues({ blur: 0, brightness: 0, confidence: 0, latency: 0 });
    } catch (e) {
      console.error('Reset failed:', e);
    } finally {
      setSending(false);
    }
  };

  const anyActive = Object.values(values).some((v) => v > 0);

  return (
    <section className={`demo-controls ${collapsed ? 'demo-controls--collapsed' : ''}`}>
      <button
        className="demo-controls__toggle"
        onClick={() => setCollapsed((c) => !c)}
      >
        <span className="demo-controls__toggle-icon">{collapsed ? '▲' : '▼'}</span>
        <span className="demo-controls__toggle-title">Failure Injection Controls</span>
        {anyActive && <span className="demo-controls__toggle-badge">ACTIVE</span>}
      </button>

      {!collapsed && (
        <div className="demo-controls__body fade-in">
          <div className="demo-controls__sliders">
            {SLIDERS.map(({ key, label, unit, min, max }) => {
              const val = values[key];
              const pct = ((val - min) / (max - min)) * 100;
              const isActive = val > 0;

              return (
                <div key={key} className={`slider-group ${isActive ? 'slider-group--active' : ''}`}>
                  <div className="slider-group__header">
                    <label className="slider-group__label">{label}</label>
                    <span className="slider-group__value mono">
                      {val}{unit}
                    </span>
                  </div>
                  <div className="slider-group__track-wrapper">
                    <input
                      type="range"
                      className="slider-group__input"
                      min={min}
                      max={max}
                      value={val}
                      onChange={(e) => handleChange(key, e.target.value)}
                      style={{
                        '--slider-pct': `${pct}%`,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          <div className="demo-controls__actions">
            <button
              className="btn btn--apply"
              onClick={handleApply}
              disabled={sending}
            >
              {sending ? 'Applying…' : '⚡ Apply'}
            </button>
            <button
              className="btn btn--reset"
              onClick={handleReset}
              disabled={sending}
            >
              ↻ Reset All
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
