import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import BrandMark from './BrandMark';
import RollText from './RollText';
import { useSite } from '../lib/SiteContext';
import { useApiStatus } from '../lib/useApiStatus';

export const NAV_LINKS = [
  { name: 'Dashboard', path: '/' },
  { name: 'Ask', path: '/query' },
  { name: 'Upload', path: '/upload' },
  { name: 'Evaluation', path: '/evaluation' },
];

export const STATUS_LABEL = {
  checking: 'Checking API',
  online: 'API and graph online',
  degraded: 'API online, graph unreachable',
  offline: 'API unreachable',
};

const isActivePath = (pathname, path) =>
  path === '/' ? pathname === '/' || pathname.startsWith('/contract/') : pathname.startsWith(path);

export default function Navbar() {
  const location = useLocation();
  const { stopScroll, startScroll } = useSite();
  const [open, setOpen] = useState(false);
  const [hidden, setHidden] = useState(false);
  const menuRef = useRef(null);
  const toggleRef = useRef(null);
  const apiState = useApiStatus();

  useEffect(() => { setOpen(false); }, [location.pathname]);

  // Fade the bar out once the page has scrolled a little, so it doesn't sit on
  // top of the content; bring it back as soon as the visitor scrolls up.
  useEffect(() => {
    const SHOW_ABOVE = 120; // px from the top where the bar always shows
    const TOLERANCE = 6;    // ignore tiny scroll jitter
    let lastY = window.scrollY;
    let frame = 0;
    const update = () => {
      frame = 0;
      const y = window.scrollY;
      if (y <= SHOW_ABOVE) setHidden(false);
      else if (y > lastY + TOLERANCE) setHidden(true);
      else if (y < lastY - TOLERANCE) setHidden(false);
      if (Math.abs(y - lastY) > TOLERANCE || y <= SHOW_ABOVE) lastY = y;
    };
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(update); };
    setHidden(false);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('scroll', onScroll);
    };
  }, [location.pathname]);

  // While open: stop Lenis, move focus into the menu, close on Escape.
  useEffect(() => {
    if (!open) return undefined;
    stopScroll();
    const focusTimer = setTimeout(() => menuRef.current?.querySelector('a')?.focus({ preventScroll: true }), 400);
    const onKey = event => {
      if (event.key === 'Escape') {
        setOpen(false);
        toggleRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      clearTimeout(focusTimer);
      window.removeEventListener('keydown', onKey);
      startScroll();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return (
    <nav
      className="nav-full"
      data-navigation-status={open ? 'active' : 'not-active'}
      data-hidden={hidden && !open ? 'true' : 'false'}
      aria-label="Primary"
    >
      <div className="nav-full__bar">
        <Link to="/" className="nav-full__wrap" aria-label="LexiGuard home">
          <span className="nav-full__logo"><BrandMark strokeWidth={3.2} /></span>
          <span className="nav-full__name">LexiGuard<br /><span className="nav-full__span">Contract AI</span></span>
        </Link>
        <div className="nav-actions">
          <button
            ref={toggleRef}
            type="button"
            className="btn-nav roll-trigger"
            aria-expanded={open}
            aria-controls="site-menu"
            onClick={() => setOpen(value => !value)}
          >
            <span className="btn__bg" aria-hidden="true" />
            <RollText stagger={0.01}>Menu</RollText>
            <span className="nav-full__hamburger" aria-hidden="true">
              <span className="nav-full__hamburger-bar" />
              <span className="nav-full__hamburger-bar" />
              <span className="nav-full__hamburger-bar" />
            </span>
          </button>
        </div>
      </div>

      <div id="site-menu" ref={menuRef} className="nav-full__tile" inert={!open} aria-hidden={!open}>
        <div className="nav-full__grid">
          <ul className="nav-full__ul">
            {NAV_LINKS.map(link => (
              <li className="nav-full__li" key={link.path}>
                <Link
                  to={link.path}
                  className={`nav-full__link roll-trigger ${isActivePath(location.pathname, link.path) ? 'is--current' : ''}`}
                  onClick={() => setOpen(false)}
                >
                  <span className="nav-full__link-text"><RollText stagger={0.01}>{link.name}</RollText></span>
                </Link>
              </li>
            ))}
          </ul>
          <p className="nav-full__aside">
            LexiGuard turns contracts into a knowledge graph of parties, clauses and cross-references, then
            answers with the clause behind every claim.
          </p>
        </div>
        <div className="nav__bottom">
          <p className="nav__word">Every clause, made clear.</p>
          <p className="nav__word status-dot" data-state={apiState}>{STATUS_LABEL[apiState]}</p>
        </div>
      </div>
    </nav>
  );
}
