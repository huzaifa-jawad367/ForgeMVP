/**
 * Mock pipeline data for the Forge fleet dashboard.
 *
 * In a production build these would come from a real API endpoint;
 * for now the same array is shared between the Dashboard and
 * DiagnosticPage so both can resolve a pipeline by its `id`.
 */

const pipelines = [
  {
    id: 'bottle-line-01',
    name: 'Bottle Inspection Line 01',
    site: 'Factory A',
    sourceType: 'video',
    source: 'bottle_line_demo.mp4',
    model: 'YOLOv8 Defect Detector',
    modelVersion: 'v1.0.0',
    status: 'healthy',
    fps: 26.8,
    meanConfidence: 0.91,
    incidents: 0,
    lastSeen: 'Live',
  },
  {
    id: 'pcb-line-02',
    name: 'PCB Defect Line 02',
    site: 'Factory A',
    sourceType: 'directory',
    source: './videos/pcb_batch/',
    model: 'YOLOv8 PCB Detector',
    modelVersion: 'v0.4.2',
    status: 'warning',
    fps: 9.14,
    meanConfidence: 0.74,
    incidents: 1,
    lastSeen: 'Live',
  },
  {
    id: 'packaging-cam-03',
    name: 'Packaging Camera 03',
    site: 'Factory B',
    sourceType: 'rtsp',
    source: 'rtsp://camera-03',
    model: 'Package Presence Detector',
    modelVersion: 'v2.1.0',
    status: 'critical',
    fps: 18.2,
    meanConfidence: 0.42,
    incidents: 2,
    lastSeen: 'Live',
  },
  {
    id: 'webcam-demo',
    name: 'Webcam Demo Pipeline',
    site: 'Local Dev',
    sourceType: 'webcam',
    source: 'webcam',
    model: 'YOLOv8 General Detector',
    modelVersion: 'demo',
    status: 'stopped',
    fps: 0,
    meanConfidence: 0,
    incidents: 0,
    lastSeen: 'Stopped',
  },
];

export default pipelines;
