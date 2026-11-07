import { useLayoutEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import BrandMark from './BrandMark';
import RollText from './RollText';
import { NAV_LINKS, STATUS_LABEL } from './Navbar';
import { useApiStatus } from '../lib/useApiStatus';
import { gsap, EASE, prefersReducedMotion } from '../lib/motion';

const WORD = 'LexiGuard';

// Scales the wordmark until it spans its parent exactly (text fit to width).
function useFitToWidth(textRef) {
  useLayoutEffect(() => {
    const el = textRef.current;
    const parent = el?.parentElement;
    if (!el || !parent) return undefined;
    let frame = 0;
    const fit = () => {
      const cs = getComputedStyle(parent);
      const available = parent.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      if (available <= 0) return;
      let size = parseFloat(getComputedStyle(el).fontSize) || 16;
      for (let i = 0; i < 5; i++) {
        const width = el.getBoundingClientRect().width;
        if (width <= 0) break;
        const ratio = available / width;
        if (Math.abs(ratio - 1) < 0.002) break;
        size *= ratio;
        el.style.fontSize = `${size}px`;
      }
    };
    const schedule = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => { frame = 0; fit(); });
    };
    const observer = new ResizeObserver(schedule);
    observer.observe(parent);
    fit();
    document.fonts?.ready.then(fit);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [textRef]);
}

export default function Footer() {
  const footerRef = useRef(null);
  const textRef = useRef(null);
  const apiState = useApiStatus();
  useFitToWidth(textRef);

  useLayoutEffect(() => {
    if (prefersReducedMotion()) return undefined;
    const ctx = gsap.context(() => {
      gsap.from('.footer-text-display .char', {
        yPercent: 100,
        duration: 1.7,
        stagger: 0.06,
        ease: EASE,
        scrollTrigger: { trigger: footerRef.current, start: 'top 70%', once: true },
      });
    }, footerRef);
    return () => ctx.revert();
  }, []);

  return (
    <footer ref={footerRef} className="footer">
      <div className="footer-layout">
        <div className="container-x">
          <div className="footer-grid">
            <Link to="/" className="footer-full__logo" aria-label="LexiGuard home">
              <BrandMark strokeWidth={3} />
            </Link>
            <div className="footer-col-links">
              <ul className="footer__ul">
                {NAV_LINKS.map(link => (
                  <li className="footer__li" key={link.path}>
                    <Link to={link.path} className="footer__link roll-trigger"><RollText stagger={0.01}>{link.name}</RollText></Link>
                  </li>
                ))}
              </ul>
            </div>
            <div className="footer-col-last">
              <div className="col_contact">
                <p>Status:</p>
                <p className="status-dot mt-6" data-state={apiState}>{STATUS_LABEL[apiState]}</p>
                <p className="mt-6 max-w-[22ch] text-[var(--muted)]">Answers come from your documents. Verify anything important.</p>
              </div>
              <div className="bolt" aria-hidden="true" />
            </div>
          </div>

          <div className="footer-middle" aria-hidden="true">
            <div ref={textRef} className="footer-text-display">
              {[...WORD].map((char, index) => (
                <span key={index} className="char-mask"><span className="char">{char}</span></span>
              ))}
            </div>
          </div>

          <div className="footer-base">
            <span className="footer-link">Built on Neo4j · ChromaDB · LangGraph</span>
            <span className="footer-link">Not legal advice</span>
            <span className="footer-link"><span>Every clause, made clear</span><span>{new Date().getFullYear()}</span></span>
          </div>
        </div>
      </div>
      <div className="footer-bg" aria-hidden="true" />
    </footer>
  );
}
