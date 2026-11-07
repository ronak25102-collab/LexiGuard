import { useCallback, useState } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import PageTransition from './components/PageTransition';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import Cursor from './components/Cursor';
import Preloader from './components/Preloader';
import Dashboard from './pages/Dashboard';
import ContractDetail from './pages/ContractDetail';
import QueryInterface from './pages/QueryInterface';
import EvaluationDashboard from './pages/EvaluationDashboard';
import Upload from './pages/Upload';
import { SiteProvider, useSite } from './lib/SiteContext';
import { ScrollTrigger, prefersReducedMotion } from './lib/motion';

const INTRO_KEY = 'lexiguard:intro-seen';

// The intro plays on the home page once per browser session. Deep links and
// reduced-motion visitors go straight to content.
function shouldPlayIntro() {
  if (typeof window === 'undefined' || prefersReducedMotion()) return false;
  if (window.location.pathname !== '/') return false;
  try { return sessionStorage.getItem(INTRO_KEY) !== '1'; } catch { return true; }
}

function Shell({ playIntro }) {
  const location = useLocation();
  const { lenis, setIntroDone } = useSite();
  const [showPreloader, setShowPreloader] = useState(playIntro);

  const revealPage = useCallback(() => setIntroDone(true), [setIntroDone]);
  const finishPreloader = useCallback(() => {
    try { sessionStorage.setItem(INTRO_KEY, '1'); } catch { /* private mode */ }
    setIntroDone(true);
    setShowPreloader(false);
  }, [setIntroDone]);

  // The old page is fully covered by the curtain at this point: jump to the
  // top, then let scroll triggers re-measure the new page.
  const onPageSwap = useCallback(() => {
    lenis?.scrollTo(0, { immediate: true, force: true });
    window.scrollTo(0, 0);
    requestAnimationFrame(() => ScrollTrigger.refresh());
  }, [lenis]);

  return (
    <>
      {showPreloader && <Preloader onReveal={revealPage} onComplete={finishPreloader} />}
      <Cursor />
      <Navbar />
      <div inert={showPreloader}>
        <AnimatePresence mode="wait" onExitComplete={onPageSwap}>
          <Routes location={location} key={location.pathname}>
            <Route path="/" element={<PageTransition><Dashboard /></PageTransition>} />
            <Route path="/contract/:id" element={<PageTransition><ContractDetail /></PageTransition>} />
            <Route path="/query" element={<PageTransition><QueryInterface /></PageTransition>} />
            <Route path="/evaluation" element={<PageTransition><EvaluationDashboard /></PageTransition>} />
            <Route path="/upload" element={<PageTransition><Upload /></PageTransition>} />
          </Routes>
        </AnimatePresence>
        <Footer />
      </div>
    </>
  );
}

export default function App() {
  const [playIntro] = useState(shouldPlayIntro);
  return (
    <SiteProvider introInitiallyDone={!playIntro}>
      <Shell playIntro={playIntro} />
    </SiteProvider>
  );
}
