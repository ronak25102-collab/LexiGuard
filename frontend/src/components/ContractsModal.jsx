import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { ArrowUpRight, Search, X } from 'lucide-react';
import { useSite } from '../lib/SiteContext';

// expo.inOut, the site's ease.
const ease = [0.87, 0, 0.13, 1];
const cleanTitle = title => String(title || 'Untitled contract').replace(/^#+\s*/, '').trim();

// Full contract list in a floating panel. Rendered into <body> through a
// portal, because the home sections are transformed while scrolling and a
// transformed ancestor would trap a fixed-position panel inside it.
export default function ContractsModal({ open, onClose, contracts, returnFocusRef }) {
  const reducedMotion = useReducedMotion();
  const { stopScroll, startScroll } = useSite();
  const [query, setQuery] = useState('');
  const searchRef = useRef(null);
  const panelRef = useRef(null);

  // While open: stop page scrolling, focus the search box, close on Escape,
  // and keep Tab inside the panel. Focus returns to the opener on close.
  useEffect(() => {
    if (!open) return undefined;
    // Some browsers don't focus a button on click, so prefer the given opener.
    const opener = returnFocusRef?.current || document.activeElement;
    stopScroll();
    const focusTimer = setTimeout(() => searchRef.current?.focus({ preventScroll: true }), 350);
    const onKey = event => {
      if (event.key === 'Escape') { onClose(); return; }
      if (event.key !== 'Tab' || !panelRef.current) return;
      const focusable = panelRef.current.querySelectorAll('a[href], button, input');
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      clearTimeout(focusTimer);
      window.removeEventListener('keydown', onKey);
      startScroll();
      opener?.focus?.({ preventScroll: true });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => { if (!open) setQuery(''); }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return contracts;
    return contracts.filter(c => [c.title, c.contract_type, c.governing_law, ...(c.parties || [])]
      .filter(Boolean).join(' ').toLowerCase().includes(q));
  }, [contracts, query]);

  const tile = reducedMotion
    ? { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: { duration: 0.15 } }
    : {
      // Same top-down clip reveal as the menu tile.
      // The clip is removed once open: Chrome can skip repainting a clipped
      // layer over a backdrop blur, which would leave the panel invisible.
      initial: { clipPath: 'polygon(0% 0%, 100% 0%, 100% 0%, 0% 0%)' },
      animate: { clipPath: 'polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)', transitionEnd: { clipPath: 'none' } },
      exit: { clipPath: ['polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)', 'polygon(0% 100%, 100% 100%, 100% 100%, 0% 100%)'] },
      transition: { duration: 0.9, ease },
    };

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="cmodal"
          key="contracts-modal"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.4, delay: reducedMotion ? 0 : 0.5 } }}
          transition={{ duration: 0.4 }}
          onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}
        >
          <motion.div
            ref={panelRef}
            className="cmodal__panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="cmodal-title"
            {...tile}
          >
            <span className="cmodal__bolt cmodal__bolt--tl" aria-hidden="true" />
            <span className="cmodal__bolt cmodal__bolt--tr" aria-hidden="true" />
            <span className="cmodal__bolt cmodal__bolt--bl" aria-hidden="true" />
            <span className="cmodal__bolt cmodal__bolt--br" aria-hidden="true" />

            <header className="cmodal__head">
              <div>
                <span className="eyebrow">Repository</span>
                <h2 id="cmodal-title" className="cmodal__title">All contracts <span>{contracts.length}</span></h2>
              </div>
              <button type="button" className="cmodal__close" onClick={onClose} aria-label="Close">
                <X size={20} aria-hidden="true" />
              </button>
            </header>

            <label className="cmodal__search">
              <Search size={16} aria-hidden="true" />
              <span className="sr-only">Search contracts</span>
              <input
                ref={searchRef}
                type="search"
                value={query}
                onChange={event => setQuery(event.target.value)}
                placeholder="Search by title, party, type or law"
              />
              <span className="cmodal__count" aria-live="polite">{filtered.length} shown</span>
            </label>

            <div className="cmodal__list">
              {filtered.length === 0 ? (
                <p className="cmodal__empty">No contracts match “{query}”.</p>
              ) : (
                <ul>
                  {filtered.map((contract, index) => {
                    const id = encodeURIComponent(contract.contract_id);
                    return (
                      <motion.li
                        key={contract.contract_id}
                        className="cmodal__row"
                        initial={reducedMotion ? false : { opacity: 0, y: 18 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6, ease, delay: reducedMotion ? 0 : 0.35 + Math.min(index, 12) * 0.035 }}
                      >
                        <span className="cmodal__index">{String(index + 1).padStart(2, '0')}</span>
                        <div className="cmodal__main">
                          <Link to={`/contract/${id}`} className="cmodal__name" onClick={onClose}>{cleanTitle(contract.title)}</Link>
                          {contract.parties?.length > 0 && <span className="cmodal__parties">{contract.parties.join(', ')}</span>}
                        </div>
                        <span className="cmodal__tags">
                          <span className="blog_item-tag">{contract.contract_type || 'Contract'}</span>
                          <span className="blog_item-tag">{contract.governing_law || 'Law not stated'}</span>
                        </span>
                        <span className="cmodal__clauses">{contract.clause_count || 0} clauses</span>
                        <span className="cmodal__actions">
                          <Link to={`/query?contractId=${id}`} className="text-link" onClick={onClose}>Ask</Link>
                          <Link to={`/contract/${id}`} className="cmodal__open" onClick={onClose} aria-label={`Open ${cleanTitle(contract.title)}`}>
                            <ArrowUpRight size={16} aria-hidden="true" />
                          </Link>
                        </span>
                      </motion.li>
                    );
                  })}
                </ul>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
