import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import Lenis from 'lenis';
import { gsap, ScrollTrigger, prefersReducedMotion } from './motion';

const SiteContext = createContext({
  lenis: null,
  introDone: true,
  setIntroDone: () => {},
  stopScroll: () => {},
  startScroll: () => {},
});

export function SiteProvider({ children, introInitiallyDone }) {
  const lenisRef = useRef(null);
  const [lenis, setLenis] = useState(null);
  const [introDone, setIntroDone] = useState(introInitiallyDone);

  // Lenis with its default settings, driven by the GSAP ticker, as on the
  // reference site.
  useEffect(() => {
    if (prefersReducedMotion()) return undefined;
    // allowNestedScroll: a scrollable panel (chat, clause list, modal list)
    // takes the wheel only while it can still scroll that way; at its ends the
    // page scrolls. data-lenis-prevent is avoided because it traps the wheel.
    const instance = new Lenis({ allowNestedScroll: true });
    lenisRef.current = instance;
    setLenis(instance);
    instance.on('scroll', ScrollTrigger.update);
    const tick = time => instance.raf(time * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    return () => {
      gsap.ticker.remove(tick);
      instance.destroy();
      lenisRef.current = null;
    };
  }, []);

  const value = useMemo(() => ({
    lenis,
    introDone,
    setIntroDone,
    stopScroll: () => {
      lenisRef.current?.stop();
      document.documentElement.classList.add('is-scroll-locked');
    },
    startScroll: () => {
      lenisRef.current?.start();
      document.documentElement.classList.remove('is-scroll-locked');
    },
  }), [lenis, introDone]);

  return <SiteContext.Provider value={value}>{children}</SiteContext.Provider>;
}

export const useSite = () => useContext(SiteContext);
