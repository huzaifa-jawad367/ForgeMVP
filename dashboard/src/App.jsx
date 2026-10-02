import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import DiagnosticPage from './pages/DiagnosticPage';
import './App.css';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/diagnostics/:pipelineId" element={<DiagnosticPage />} />
    </Routes>
  );
}
