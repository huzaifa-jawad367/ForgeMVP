import { useEffect, useRef, useState } from 'react';
import { EDGE_API, request } from '../hooks/useDemoApi';
import { PageHeading, Stat, number } from '../components/DemoUi';
import { createPrivacySample } from '../data/privacySample';
const MAX_BYTES = 5 * 1024 * 1024;
export default function PrivacyLab() {
  const [file, setFile] = useState(null);
  const [original, setOriginal] = useState(null);
  const [result, setResult] = useState(null);
  const [mode, setMode] = useState('blur');
  const [overlay, setOverlay] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const input = useRef(null);
  const operation = useRef(null);
  useEffect(() => () => { operation.current?.abort(); }, []);
  useEffect(() => {
    if (!file) { setOriginal(null); return; }
    const url = URL.createObjectURL(file);
    setOriginal(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  const clear = () => {
    operation.current?.abort(); operation.current = null;
    setFile(null); setResult(null); setError(null); setBusy(false);
    if (input.current) input.current.value = '';
  };
  const choose = (event) => {
    const selected = event.target.files?.[0];
    operation.current?.abort(); operation.current = null;
    setResult(null); setBusy(false); setError(null); setFile(null);
    if (!selected) return;
    if (!['image/jpeg', 'image/png'].includes(selected.type)) { setError('Choose a JPEG or PNG image.'); return; }
    if (selected.size > MAX_BYTES) { setError('The image must be 5 MB or smaller.'); return; }
    setFile(selected);
  };
  const process = async () => {
    const controller = new AbortController();
    operation.current?.abort(); operation.current = controller;
    setBusy(true); setError(null); setResult(null);
    try {
      const response = await request(`${EDGE_API}/api/demo/privacy?mode=${mode}`, { method: 'POST', headers: { 'Content-Type': file.type }, body: file, signal: AbortSignal.any([controller.signal, AbortSignal.timeout(30000)]) });
      if (operation.current === controller) setResult(response);
    } catch (failure) { if (operation.current === controller && !controller.signal.aborted) setError(failure.message); }
    finally { if (operation.current === controller) setBusy(false); }
  };
  const useSample = () => {
    clear();
    setFile(createPrivacySample());
  };
  return <>
    <PageHeading eyebrow="PRIVACY LAB / REDACTION PREVIEW" title="Privacy starts at the edge.">Inspect the shared redaction method on your own image. Review what it changes, and what it may miss.</PageHeading>
    <div className="notice"><strong>Preview, with a clear boundary</strong><p>The original travels directly from this browser to the local edge for in-memory processing. This preview does not archive either image. Redaction alone does not establish GDPR compliance.</p></div>
    <section className="panel"><div className="section-heading"><div><h2>Select an image</h2><p className="small muted">JPEG or PNG · up to 5 MB · processed on the local edge</p></div>{file && <button className="button button--small" onClick={clear}>Clear images</button>}</div><div className="upload-controls"><label className="file-selector"><span>Choose image</span><input ref={input} type="file" accept="image/jpeg,image/png" onChange={choose} /><span className="file-name">{file?.name || 'No image selected'}</span></label><button className="button button--small" onClick={useSample} disabled={busy}>Use synthetic sample</button><fieldset className="mode-selector"><legend>Redaction mode</legend><label><input type="radio" name="mode" value="blur" checked={mode === 'blur'} onChange={() => setMode('blur')} disabled={busy} /> Gaussian blur</label><label><input type="radio" name="mode" value="mask" checked={mode === 'mask'} onChange={() => setMode('mask')} disabled={busy} /> Solid mask</label></fieldset><button className="button button--primary" disabled={!file || busy} onClick={process}>{busy ? 'Processing at the edge…' : 'Process image →'}</button></div>{file?.name === 'synthetic-skin-sample.png' && <p className="small muted">This drawn skin-colour sample exercises the real redaction path. It is not a face-detector accuracy test.</p>}{error && <div className="notice notice--warning" role="alert">Preview unavailable: {error}</div>}</section>
    <div className="section-heading"><h2>Original & processed</h2><label className="checkbox-label"><input type="checkbox" checked={overlay} onChange={event => setOverlay(event.target.checked)} /> Show detected regions</label></div>
    <div className="image-comparison"><section className="panel image-panel"><div className="section-heading"><h3>Original</h3><span className="tag">Browser-local preview</span></div><div className="image-stage">{original ? <img src={original} alt="Your original image before redaction" /> : <div className="image-empty"><span>01</span><h3>Your image starts here</h3><p>Select an image to compare the original with the actual processed output.</p></div>}</div></section><section className="panel image-panel"><div className="section-heading"><h3>Processed output</h3><span className="tag">{result ? result.mode === 'mask' ? 'Solid mask' : 'Gaussian blur' : 'Awaiting processing'}</span></div><div className="image-stage">{result ? <div className="processed-image"><img src={`data:${result.mime_type};base64,${result.image_base64}`} alt={`Processed image with ${result.region_count} automatically redacted regions`} />{overlay && result.regions?.map((region, index) => <span className="region-overlay" key={index} aria-label={`Region ${index + 1}: ${region.source}`} style={{ left: `${region.x / result.width * 100}%`, top: `${region.y / result.height * 100}%`, width: `${region.width / result.width * 100}%`, height: `${region.height / result.height * 100}%` }} />)}</div> : <div className="image-empty"><span>02</span><h3>{busy ? 'Processing your image' : 'See what the pipeline changes'}</h3><p>Run processing to see measured results. No simulated redaction is shown.</p></div>}</div></section></div>
    {result && <><div className={`notice ${result.region_count === 0 ? 'notice--warning' : ''}`} role="status"><strong>{result.region_count === 0 ? 'No regions detected; review the output.' : `${number(result.region_count)} region${result.region_count === 1 ? '' : 's'} changed. Review the entire output.`}</strong><p>Automatic detection may miss people or redact non-person areas. A processed image is not proof that every face has been anonymized.</p>{result.warnings?.map((warning, index) => <p key={index}>{warning}</p>)}</div><div className="stats-grid"><Stat label="Regions changed" value={number(result.region_count)} detail="Automatic detections from the shared method" /><Stat label="Processing time" value={`${number(result.processing_ms, 1)} ms`} detail="Measured on this edge request" /><Stat label="Image dimensions" value={`${number(result.width)} × ${number(result.height)}`} detail="Pixels · same scale in both previews" /><Stat label="Archived by preview" value={result.persisted === false ? 'No' : 'Unknown'} detail="Reported by the edge endpoint" /></div><section className="panel"><h2>Method & detected regions</h2><p className="method-name mono">{result.method}</p><p className="muted">The preview uses the same redaction implementation as the inspection pipeline. The current method combines an OpenCV frontal-face cascade with a skin-colour heuristic. It has not been validated as a guarantee of complete anonymization.</p>{result.regions?.length > 0 && <div className="table-scroll"><table className="data-table"><thead><tr><th>Region</th><th>Position</th><th>Size</th><th>Source</th></tr></thead><tbody>{result.regions.map((region, index) => <tr key={index}><th>{index + 1}</th><td>{region.x}, {region.y}</td><td>{region.width} × {region.height}</td><td>{region.source}</td></tr>)}</tbody></table></div>}</section></>}
    <section className="panel"><div className="eyebrow">THE PERSISTENCE BOUNDARY</div><h2>Original bytes stop before storage.</h2><div className="privacy-flow"><span>Browser original</span><b>→</b><span>Edge RAM · redaction</span><b>→</b><span>Processed output</span><b>→</b><span className="muted">Eligible for buffering & sync</span></div><p className="small muted">This preview returns the processed image to your browser. It does not enqueue or sync the preview.</p></section>
  </>;
}

