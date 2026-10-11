const fs = require('fs');

const modalPath = 'dashboard/src/components/IncidentModal.jsx';
let content = fs.readFileSync(modalPath, 'utf8');

// Replace the waterfall variables
let oldWaterfallBar = `<div className="waterfall-segment segment-capture" style={{ width: pct(captureMs) }} title={\`Inference: \${captureMs.toFixed(1)}ms\`}></div>
                <div className="waterfall-segment segment-queue" style={{ width: pct(queueMs) }} title={\`Queue: \${queueMs.toFixed(1)}ms\`}></div>
                <div className="waterfall-segment segment-transport" style={{ width: pct(transportMs) }} title={\`Transport: \${transportMs.toFixed(1)}ms\`}></div>
                <div className="waterfall-segment segment-persist" style={{ width: pct(persistMs) }} title={\`Persist: \${persistMs.toFixed(1)}ms\`}></div>`;

let newWaterfallBar = `<div className="waterfall-segment segment-capture" style={{ width: pct(prepMs) }} title={\`Prep: \${prepMs.toFixed(1)}ms\`}></div>
                <div className="waterfall-segment segment-queue" style={{ width: pct(inferMs) }} title={\`Inference: \${inferMs.toFixed(1)}ms\`}></div>
                <div className="waterfall-segment segment-transport" style={{ width: pct(queueDwellMs) }} title={\`Buffer Dwell: \${queueDwellMs.toFixed(1)}ms\`}></div>
                <div className="waterfall-segment segment-persist" style={{ width: pct(persistMs) }} title={\`Persist: \${persistMs.toFixed(1)}ms\`}></div>`;

content = content.replace(oldWaterfallBar, newWaterfallBar);

let oldLegend = `<span><span className="legend-dot dot-capture"></span> Inf: {captureMs.toFixed(1)}ms</span>
                <span><span className="legend-dot dot-queue"></span> Que: {queueMs.toFixed(1)}ms</span>
                <span><span className="legend-dot dot-transport"></span> Net: {transportMs.toFixed(1)}ms</span>
                <span><span className="legend-dot dot-persist"></span> DB: {persistMs.toFixed(1)}ms</span>`;

let newLegend = `<span><span className="legend-dot dot-capture"></span> Prep: {prepMs.toFixed(1)}ms</span>
                <span><span className="legend-dot dot-queue"></span> Inf: {inferMs.toFixed(1)}ms</span>
                <span><span className="legend-dot dot-transport"></span> Buf: {queueDwellMs.toFixed(1)}ms</span>
                <span><span className="legend-dot dot-persist"></span> DB: {persistMs.toFixed(1)}ms</span>`;

content = content.replace(oldLegend, newLegend);

fs.writeFileSync(modalPath, content);
