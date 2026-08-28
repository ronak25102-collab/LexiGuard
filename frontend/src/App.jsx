import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { StructureFlowCollection } from '@designcodeio/threeui';
import '@designcodeio/threeui/style.css';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import ContractDetail from './pages/ContractDetail';
import QueryInterface from './pages/QueryInterface';
import EvaluationDashboard from './pages/EvaluationDashboard';
import Upload from './pages/Upload';

function App() {
  return (
    <div className="app-shell min-h-screen text-slate-50 flex flex-col">
      <div className="shader-frame" aria-hidden="true">
        <StructureFlowCollection
          variant="fluid-field"
          hue={0}
          saturation={1.00}
          brightness={1.00}
        />
      </div>
      <div className="app-atmosphere" aria-hidden="true" />
      <Navbar />
      <main className="app-main flex-grow container mx-auto px-4 py-8 max-w-7xl">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/contract/:id" element={<ContractDetail />} />
          <Route path="/query" element={<QueryInterface />} />
          <Route path="/evaluation" element={<EvaluationDashboard />} />
          <Route path="/upload" element={<Upload />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
