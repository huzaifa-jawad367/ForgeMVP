import { useEffect, useState } from 'react';
import { AreaChart, Area, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { useDemoStatus, useBackendObservation, edgeCommand, reconcileRun } from '../hooks/useDemoApi';
import { PageHeading, Stat, Signal, ErrorNotice, number, seconds, bytes } from '../components/DemoUi';
export default function ReliabilityLab() {
  const edge = useDemoStatus();
  const backend = useBackendObservation('/api/pipeline/status');
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [reconciliation, setReconciliation] = useState(null);
  const [reconcileError, setReconcileError] = useState(null);
  const data = edge.data;
  const run = data?.run;
  const buffer = data?.buffer || {};
  const sync = data?.sync || {};
  const active = run && ['offline', 'recovering'].includes(run.phase);
  const available = !!data && !edge.error;
  const runId = run?.id;
  const closed = run?.capture_closed;
  const identities = run?.payload_ids?.join(',') || '';
  useEffect(() => {
    setReconciliation(null);
    setReconcileError(null);
    if (!runId || !closed) return;
    let cancelled = false;
    let timer;
    const check = async () => {
      try {
        const result = await reconcileRun(data.edge_id, identities ? identities.split(',') : []);
        if (!cancelled) { setReconciliation({ ...result, runId }); setReconcileError(null); }
      } catch (error) { if (!cancelled) setReconcileError(error.message); }
      if (!cancelled) timer = setTimeout(check, 2000);
    };
    check();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [runId, closed, identities, data?.edge_id]);
  const command = async (path, body) => {
    setBusy(true); setActionError(null);
    try { await edgeCommand(path, body); await edge.refresh(); }
    catch (error) { setActionError(error.message); }
    finally { setBusy(false); }
  };
  const verified = available && run?.phase === 'complete' && run.capture_closed && run.admitted_count > 0 && run.captured_count === run.admitted_count && run.acknowledged_count === run.admitted_count && run.rejected_count === 0 && run.evicted_count === 0 && run.persistence_errors === 0 && !reconcileError && reconciliation?.runId === run.id && reconciliation?.requested_count === run.admitted_count && reconciliation?.committed_count === run.admitted_count && reconciliation?.missing_payload_ids?.length === 0;
  const samples = (data?.samples || []).map(sample => ({ ...sample, time: new Date(sample.at).toLocaleTimeString([], { hour12: false }) }));
  const markers = samples.filter((sample, index) => index > 0 && sample.paused !== samples[index - 1].paused);
  const outcomeTitle = verified ? 'Delivery verified'
    : !run ? 'Ready when you are'
    : edge.error ? 'Waiting for fresh edge telemetry'
    : run.phase === 'offline' ? `Sync paused · ${number(run.remaining_offline_seconds)} s remaining`
    : run.phase === 'recovering' ? 'Reconnected. Draining the cohort.'
    : run.phase === 'complete' && run.admitted_count === 0 ? 'Inconclusive: no frames admitted'
    : run.phase === 'complete' && (run.rejected_count || run.evicted_count || run.persistence_errors) ? 'Delivery needs review: losses or persistence errors'
    : run.phase === 'complete' && reconciliation && !reconcileError ? 'Delivery needs review: cohort did not reconcile'
    : run.phase === 'complete' ? 'Checking the database reconciliation'
    : `Run ${run.phase}`;
  return <>
    <PageHeading eyebrow="RELIABILITY LAB / EXPERIMENT 01" title="Connection lost. Work preserved." action={<button className="button button--primary" disabled={!available || busy || active} onClick={() => command('run', { offline_seconds: 10 })}>Run guided demo <span>↗</span></button>}>Disconnect sync for 10 seconds. Follow each payload from the edge queue to a confirmed database record.</PageHeading>
    <div className="signal-row"><Signal poll={edge} label="Edge observation" /><Signal poll={backend} label="Backend API" /><span className="muted">The observation channel stays connected during a sync outage.</span></div>
    <ErrorNotice error={edge.error} />{actionError && <div className="notice notice--warning" role="alert">Control failed: {actionError}</div>}
    <section className="panel experiment-panel"><div className="section-heading"><div><div className="eyebrow">THE DELIVERY PATH</div><h2>Four stages. One durable handoff.</h2></div><span className="tag">Injected sync outage</span></div><div className="flow-grid">{[['01', 'Camera & inference', edge.error ? 'Unknown' : data?.capture_alive && data?.inference_alive && data?.capture_age_seconds <= 5 ? 'Processing frames' : 'Awaiting capture'], ['02', 'Durable edge queue', `${number(buffer.queue_size)} pending locally`], ['03', 'Sync transport', edge.error ? 'Unknown' : sync.paused ? 'Paused · capture continues' : sync.connected ? 'Connected' : 'Waiting / retrying'], ['04', 'Backend database', backend.error ? 'Unreachable' : backend.loading ? 'Checking connection' : 'API reachable']].map(([index, title, value]) => <div className={`flow-step ${index === '03' && sync.paused ? 'flow-step--paused' : ''}`} key={index}><span className="flow-index">{index}</span><h3>{title}</h3><p>{value}</p></div>)}</div><div className="control-row"><div className="button-group"><button className="button" disabled={!available || busy || sync.paused || active} onClick={() => command('sync', { paused: true })}>Disconnect sync</button><button className="button" disabled={!available || busy || !sync.paused} onClick={() => command('sync', { paused: false })}>Reconnect sync</button></div><p>{sync.paused ? 'Payloads stay in SQLite until a valid backend acknowledgement. Auto reconnect protects abandoned demos.' : 'Inference continues during the experiment. Only payload delivery is paused.'}</p></div></section>
    <div className="stats-grid"><Stat label="Captured in this run" value={number(run?.captured_count)} detail={run ? `Bounded cohort · ${run.phase}` : 'Start a guided demo to measure a cohort'} /><Stat label="Pending in this run" value={number(run?.pending_count)} detail="Admitted payloads awaiting acknowledgement" accent /><Stat label="Committed remotely" value={number(reconciliation?.committed_count)} detail="Queried from actual backend database" /><Stat label="Rejected / evicted" value={run ? `${number(run.rejected_count)} / ${number(run.evicted_count)}` : '—'} detail="Actual cohort admission and eviction accounting" /></div>
    <div className="chart-detail-grid"><section className="panel"><div className="section-heading"><div><h2>Queue depth over time</h2><p className="small muted">Actual edge samples · pending payloads</p></div><span className="legend"><i /> Edge queue</span></div><div className="chart-container" role="img" aria-label={`Queue chart, current depth ${number(buffer.queue_size)} payloads`}>{samples.length ? <ResponsiveContainer width="100%" height={260}><AreaChart data={samples} margin={{ top: 15, right: 12, bottom: 0, left: -12 }}><CartesianGrid vertical={false} stroke="#29383b" /><XAxis dataKey="time" minTickGap={65} tick={{ fill: '#a4b5b8', fontSize: 12 }} /><YAxis allowDecimals={false} tick={{ fill: '#a4b5b8', fontSize: 12 }} /><Tooltip contentStyle={{ background: '#182528', border: '1px solid #405458', borderRadius: 8 }} /><Area dataKey="queue_size" name="Pending" stroke="#62d5bf" fill="#62d5bf" fillOpacity={0.12} strokeWidth={2} isAnimationActive={false} />{markers.map((marker, index) => <ReferenceLine key={index} x={marker.time} stroke={marker.paused ? "#e8bb77" : "#a6b7e8"} strokeDasharray="4 4" label={{ value: marker.paused ? "Paused" : "Resumed", fill: marker.paused ? "#e8bb77" : "#a6b7e8", fontSize: 11, position: "insideTopRight" }} />)}</AreaChart></ResponsiveContainer> : <div className="empty-state">Waiting for measured queue samples.</div>}</div><p className="small muted">{edge.error ? 'Chart stopped: observation is stale.' : 'Samples and experiment events are held by the edge, so reloading this page keeps the current run.'}</p></section><section className="panel"><h2>Delivery & storage</h2><dl className="detail-list"><div><dt>Persisted SQLite rows</dt><dd>{number(buffer.persisted_rows)}</dd></div><div><dt>Storage used</dt><dd>{bytes(buffer.storage_used_bytes)}</dd></div><div><dt>Queue capacity</dt><dd>{number(buffer.capacity ?? buffer.max_size)}</dd></div><div><dt>Oldest pending</dt><dd>{seconds(buffer.oldest_pending_age_seconds)}</dd></div><div><dt>Last ACK age</dt><dd>{seconds(sync.last_ack_age_seconds)}</dd></div><div><dt>HTTP round trip</dt><dd>{sync.round_trip_ms == null ? '—' : `${number(sync.round_trip_ms, 1)} ms`}</dd></div><div><dt>Retries / deduplicated</dt><dd>{number(sync.total_retries)} / {number(sync.total_deduplicated)}</dd></div><div><dt>Next retry</dt><dd>{seconds(sync.next_retry_seconds)}</dd></div></dl>{sync.last_error && <p className="warning-text">Last sync error: {sync.last_error}</p>}{buffer.last_persistence_error && <p className="warning-text">Persistence error: {buffer.last_persistence_error}</p>}</section></div>
    <div className="two-column"><section className="panel"><div className="section-heading"><h2>Run outcome</h2>{run && <button className="button button--small" disabled={!available || busy} onClick={() => command('reset', {})}>{active ? 'Cancel & reconnect' : 'Reset run'}</button>}</div><div className={`outcome ${verified ? 'outcome--verified' : ''}`} role="status"><span className="outcome-icon">{verified ? '\u2713' : run?.phase === 'failed' ? '!' : '\u2194'}</span><div><h3>{outcomeTitle}</h3><p>{verified ? `${number(reconciliation.committed_count)} of ${number(run.admitted_count)} admitted payloads confirmed in the database and acknowledged at the edge.` : 'A successful result requires a nonempty closed cohort, confirmed commits, acknowledgements, and no rejected, evicted, or persistence errors.'}</p></div></div>{run && <dl className="detail-list"><div><dt>Elapsed / recovery</dt><dd>{seconds(run.elapsed_seconds)} / {seconds(run.recovery_seconds)}</dd></div><div><dt>Acknowledged in cohort</dt><dd>{number(run.acknowledged_count)}</dd></div><div><dt>Run ID</dt><dd className="small mono">{run.id}</dd></div></dl>}{reconcileError && <p className="warning-text" role="alert">Database verification unavailable: {reconcileError}</p>}</section><section className="panel"><h2>Priority accounting</h2><p className="small muted">Live queue occupancy and cumulative drops by tier</p><table className="data-table"><thead><tr><th>Tier</th><th>Pending</th><th>Dropped</th></tr></thead><tbody>{['P0', 'P1', 'P2', 'P3'].map(tier => <tr key={tier}><th>{tier}</th><td>{number(buffer[`${tier.toLowerCase()}_count`])}</td><td>{number(buffer.drops_by_tier?.[tier])}</td></tr>)}</tbody></table></section></div>
    <section className="panel"><div className="section-heading"><h2>Experiment events</h2><span className="muted small">Newest first · edge timestamps</span></div><ol className="event-list">{(data?.events || []).slice().reverse().slice(0, 20).map(event => <li key={event.id}><time>{new Date(event.at).toLocaleTimeString()}</time><span>{event.message}</span></li>)}</ol>{!data?.events?.length && <p className="empty-state">Control actions and delivery milestones will appear here.</p>}</section>
    <section><div className="section-heading"><h2>More resilience scenarios</h2><span className="muted small">Instrumentation required</span></div><div className="scenario-grid">{[['Lost acknowledgement', 'Requires a controlled ACK-loss injector and retry accounting.'], ['Edge restart', 'Requires a local supervisor and replay verification.'], ['Storage pressure', 'Requires an isolated limited-capacity queue.']].map(([name, reason]) => <div className="panel scenario" key={name}><h3>{name}</h3><p>{reason}</p><button className="button button--small" disabled>Not yet available</button></div>)}</div></section>
  </>;
}

