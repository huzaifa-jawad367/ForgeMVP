export const number = (value, digits = 0) => typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: digits }) : '—';
export const seconds = (value) => value == null ? '—' : `${number(value, 1)} s`;
export const bytes = (value) => value == null ? '—' : value < 1048576 ? `${number(value / 1024, 1)} KB` : `${number(value / 1048576, 1)} MB`;
export function PageHeading({ eyebrow, title, children, action }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{children}</p></div>{action}</div>;
}
export function Stat({ label, value, detail, accent = false }) {
  return <div className={`stat-card ${accent ? 'stat-card--accent' : ''}`}><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-detail">{detail}</div></div>;
}
export function Signal({ poll, label }) {
  const state = poll.error ? poll.data ? 'Stale' : 'Unavailable' : poll.loading ? 'Connecting' : 'Fresh';
  return <span className={`signal signal--${state.toLowerCase()}`} title={poll.error || 'Successful observation'}><span className="status-dot" />{label}: {state}</span>;
}
export function ErrorNotice({ error, children }) {
  return error ? <div className="notice notice--warning" role="status"><strong>Observation unavailable</strong><p>{error}. {children || 'Values shown are last known; controls require a live connection.'}</p></div> : null;
}
