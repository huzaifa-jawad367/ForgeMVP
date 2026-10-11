const fs = require('fs');

const modalPath = 'dashboard/src/components/IncidentModal.jsx';
let content = fs.readFileSync(modalPath, 'utf8');

// Fix 1: Cross-node monotonic clock subtraction
// Original code probably calculates:
// const captureMs = ...
// const queueMs = ...
// const transportMs = (ts.transmitted_at_ns - ts.queued_at_ns) / 1e6;
// const persistMs = (ts.persisted_at_ns - ts.transmitted_at_ns) / 1e6;
// We need to change to:
// Backend Total: (persisted_at_ns - received_at_ns) / 1e6

content = content.replace(
  /const persistMs = \(ts\.persisted_at_ns - ts\.transmitted_at_ns\) \/ 1e6;/g,
  'const persistMs = (ts.persisted_at_ns - ts.received_at_ns) / 1e6;'
);

// Fix 2: Property Mismatch Breaks Evidence Rendering
// const evidenceFiles = evidence?.evidence_files || evidence?.frames || [];
// Change to:
// const evidenceFiles = evidence?.images || evidence?.evidence_files || evidence?.frames || [];

content = content.replace(
  /const evidenceFiles = evidence\?\.evidence_files \|\| evidence\?\.frames \|\| \[\];/g,
  'const evidenceFiles = evidence?.images || evidence?.evidence_files || evidence?.frames || [];'
);

fs.writeFileSync(modalPath, content);
