import { Routes, Route, Navigate, NavLink } from 'react-router-dom';
import Overview from './pages/Overview';
import DiagnosticPage from './pages/DiagnosticPage';
import ReliabilityLab from './pages/ReliabilityLab';
import PrivacyLab from './pages/PrivacyLab';
import './App.css';
const destinations = [['/dashboard', 'Overview', '01'], ['/diagnostics/pcb1-visa', 'Live inspection', '02'], ['/reliability', 'Reliability Lab', '03'], ['/privacy', 'Privacy Lab', '04']];
export default function App() {
  return <div className="forge-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className="sidebar">
      <NavLink to="/dashboard" className="brand"><span className="brand-mark">F</span><span>FORGE<small>Inspection intelligence</small></span></NavLink>
      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="Main navigation">{destinations.map(([path, label, number]) => <NavLink key={path} to={path} className={({ isActive }) => `nav-item ${isActive ? 'is-active' : ''}`}><span>{number}</span>{label}</NavLink>)}</nav>
      <div className="sidebar-note"><span className="status-dot" />Local demonstration<p>Real edge telemetry.<br />Observable recovery.</p></div>
    </aside>
    <div className="workspace"><header className="workspace-header"><span>FORGE / DEMO WORKSPACE</span><span className="environment">Local environment</span></header>
      <main id="main-content" className="page-content"><Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Overview />} />
        <Route path="/diagnostics/:pipelineId" element={<DiagnosticPage />} />
        <Route path="/reliability" element={<ReliabilityLab />} />
        <Route path="/privacy" element={<PrivacyLab />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes></main>
    </div>
  </div>;
}
