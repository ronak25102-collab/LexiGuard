import React, { useEffect, useRef } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import PageTransition from './components/PageTransition';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import ContractDetail from './pages/ContractDetail';
import QueryInterface from './pages/QueryInterface';
import EvaluationDashboard from './pages/EvaluationDashboard';
import Upload from './pages/Upload';

function App() {
  const vantaRef = useRef(null);
  const location = useLocation();

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
                <AnimatePresence mode="wait">
          <Routes location={location} key={location.pathname}>
            <Route path="/" element={<PageTransition><Dashboard /></PageTransition>} />
            <Route path="/contract/:id" element={<PageTransition><ContractDetail /></PageTransition>} />
            <Route path="/query" element={<PageTransition><QueryInterface /></PageTransition>} />
            <Route path="/evaluation" element={<PageTransition><EvaluationDashboard /></PageTransition>} />
            <Route path="/upload" element={<PageTransition><Upload /></PageTransition>} />
          </Routes>
        </AnimatePresence>
      </main>
    </div>
  );
}

export default App;


