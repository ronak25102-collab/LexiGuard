import { useEffect, useLayoutEffect, useRef } from 'react';
import BrandMark from './BrandMark';
import { gsap, EASE } from '../lib/motion';
import { useSite } from '../lib/SiteContext';

const FONT_WAIT_CAP_MS = 1500;
const HERO_START = 3.05; // seconds into the preloader timeline

// Start once the web font is ready (so the hero never reflows mid-reveal),
// but never hold the visitor for more than 1.5s.
function whenFontsReady() {
  const fonts = document.fonts?.ready ?? Promise.resolve();
  return Promise.race([fonts, new Promise(resolve => setTimeout(resolve, FONT_WAIT_CAP_MS))]);
}

export default function Preloader({ onReveal, onComplete }) {
  const root = useRef(null);
  const tlRef = useRef(null);
  const { stopScroll, startScroll } = useSite();

  useEffect(() => {
    stopScroll();
    const skip = event => { if (event.key === 'Escape') tlRef.current?.timeScale(4); };
    window.addEventListener('keydown', skip);
    return () => {
      window.removeEventListener('keydown', skip);
      startScroll();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useLayoutEffect(() => {
    const el = root.current;
    const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    const d = 8.3 * rem;
    let cancelled = false;

    const ctx = gsap.context(() => {
      // Bolts start gathered in the centre; the signet waits below its mask.
      gsap.set('.preloader_01', { x: d, y: d });
      gsap.set('.preloader_02', { x: -d, y: d });
      gsap.set('.preloader_03', { x: d, y: -d });
      gsap.set('.preloader_04', { x: -d, y: -d });
      gsap.set('.preloader_signet', { yPercent: 105 });

      const tl = gsap.timeline({ paused: true, onComplete: () => onComplete?.() });
      tl.to('.preloader_layout .bolt', { x: 0, y: 0, duration: 1.3, ease: EASE }, 0.2)
        .to('.preloader_signet', { yPercent: 0, duration: 1.3, ease: EASE }, 1.1)
        .to(el, { yPercent: -100, duration: 1.1, ease: EASE }, 2.4)
        .call(() => onReveal?.(), null, HERO_START);
      tlRef.current = tl;
    }, el);

    whenFontsReady().then(() => { if (!cancelled) tlRef.current?.play(); });

    return () => {
      cancelled = true;
      ctx.revert();
    };
  }, [onComplete, onReveal]);

  return (
    <div ref={root} className="preloader" role="status" aria-label="Loading LexiGuard">
      <div className="preloader_layout" aria-hidden="true">
        <div className="bolt preloader_01" />
        <div className="bolt preloader_02" />
        <div className="bolt preloader_03" />
        <div className="bolt preloader_04" />
        <div className="preloader_logo">
          <BrandMark className="preloader_signet" strokeWidth={3.2} />
        </div>
      </div>
      <button type="button" className="preloader__skip" onClick={() => tlRef.current?.timeScale(4)}>
        Skip intro
      </button>
    </div>
  );
}
