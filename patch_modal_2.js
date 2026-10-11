const fs = require('fs');

const modalPath = 'dashboard/src/components/IncidentModal.jsx';
let content = fs.readFileSync(modalPath, 'utf8');

// The original logic might look something like this:
// const captureMs = (ts.inference_completed_at_ns - ts.captured_at_ns) / 1e6;
// const queueMs = (ts.queued_at_ns - ts.inference_completed_at_ns) / 1e6;
// const transportMs = (ts.transmitted_at_ns - ts.queued_at_ns) / 1e6;
// const persistMs = (ts.persisted_at_ns - ts.received_at_ns) / 1e6;

// Let's replace the whole duration calculation block using BigInt

let blockToReplace = `          const captureMs = (ts.inference_completed_at_ns - ts.captured_at_ns) / 1e6;
          const queueMs = (ts.queued_at_ns - ts.inference_completed_at_ns) / 1e6;
          const transportMs = (ts.transmitted_at_ns - ts.queued_at_ns) / 1e6;
          const persistMs = (ts.persisted_at_ns - ts.received_at_ns) / 1e6;`;

let newBlock = `          const toMs = (start, end) => Number(BigInt(end) - BigInt(start)) / 1e6;
          const prepMs = toMs(ts.captured_at_ns, ts.inference_started_at_ns);
          const inferMs = toMs(ts.inference_started_at_ns, ts.inference_completed_at_ns);
          const queueDwellMs = toMs(ts.queued_at_ns, ts.transmitted_at_ns);
          const persistMs = toMs(ts.received_at_ns, ts.persisted_at_ns);`;

content = content.replace(blockToReplace, newBlock);

// We also need to update the JSX where these are rendered.
// Let's look for where they are rendered.
// Probably:
// <div style={{ width: \`\${(captureMs / totalMs) * 100}%\` }} title={\`Inf: \${captureMs.toFixed(1)}ms\`} />
// <div style={{ width: \`\${(queueMs / totalMs) * 100}%\` }} title={\`Que: \${queueMs.toFixed(1)}ms\`} />
// <div style={{ width: \`\${(transportMs / totalMs) * 100}%\` }} title={\`Net: \${transportMs.toFixed(1)}ms\`} />
// <div style={{ width: \`\${(persistMs / totalMs) * 100}%\` }} title={\`DB: \${persistMs.toFixed(1)}ms\`} />

let jsxToReplace = `<div className="bg-blue-500 h-full" style={{ width: \`\${(captureMs / totalMs) * 100}%\` }} title={\`Inf: \${captureMs.toFixed(1)}ms\`} />
                  <div className="bg-yellow-500 h-full" style={{ width: \`\${(queueMs / totalMs) * 100}%\` }} title={\`Que: \${queueMs.toFixed(1)}ms\`} />
                  <div className="bg-orange-500 h-full" style={{ width: \`\${(transportMs / totalMs) * 100}%\` }} title={\`Net: \${transportMs.toFixed(1)}ms\`} />
                  <div className="bg-green-500 h-full" style={{ width: \`\${(persistMs / totalMs) * 100}%\` }} title={\`DB: \${persistMs.toFixed(1)}ms\`} />`;

let newJsx = `<div className="bg-blue-400 h-full" style={{ width: \`\${(prepMs / totalMs) * 100}%\` }} title={\`Prep: \${prepMs.toFixed(1)}ms\`} />
                  <div className="bg-blue-600 h-full" style={{ width: \`\${(inferMs / totalMs) * 100}%\` }} title={\`Inf: \${inferMs.toFixed(1)}ms\`} />
                  <div className="bg-yellow-500 h-full" style={{ width: \`\${(queueDwellMs / totalMs) * 100}%\` }} title={\`Queue: \${queueDwellMs.toFixed(1)}ms\`} />
                  <div className="bg-green-500 h-full" style={{ width: \`\${(persistMs / totalMs) * 100}%\` }} title={\`DB: \${persistMs.toFixed(1)}ms\`} />`;

content = content.replace(jsxToReplace, newJsx);

// Wait, the totalMs is probably calculated as `captureMs + queueMs + transportMs + persistMs`
// We need to fix that as well
let totalMsToReplace = `const totalMs = captureMs + queueMs + transportMs + persistMs;`;
let newTotalMs = `const totalMs = prepMs + inferMs + queueDwellMs + persistMs;`;
content = content.replace(totalMsToReplace, newTotalMs);

fs.writeFileSync(modalPath, content);
