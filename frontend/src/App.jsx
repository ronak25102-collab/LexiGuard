import React, { useEffect, useRef } from 'react';
import { Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import ContractDetail from './pages/ContractDetail';
import QueryInterface from './pages/QueryInterface';
import EvaluationDashboard from './pages/EvaluationDashboard';
import Upload from './pages/Upload';

function App() {
  const vantaRef = useRef(null);

  useEffect(() => {
    let vantaEffect;
    if (window.VANTA) {
      vantaEffect = window.VANTA.FOG({
        el: vantaRef.current,
        mouseControls: true,
        touchControls: true,
        gyroControls: false,
        minHeight: 200.00,
        minWidth: 200.00,
        highlightColor: 0xbae6fd,
        midtoneColor: 0x38bdf8,
        lowlightColor: 0x0284c7,
        baseColor: 0xf0f9ff,
        blurFactor: 0.60,
        speed: 1.00,
        zoom: 1.00
      });
    }
    return () => {
      if (vantaEffect) vantaEffect.destroy();
    };
  }, []);

  return (
    <div className="app-shell min-h-screen text-slate-50 flex flex-col relative">
      {/* Vanta Global Background */}
      <div className="fixed inset-0 z-[-1] pointer-events-none" aria-hidden="true">
        <div ref={vantaRef} className="w-full h-full" />
      </div>
      
      <Navbar />
      <main className="app-main flex-grow container mx-auto px-4 py-8 max-w-7xl relative z-10">
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
