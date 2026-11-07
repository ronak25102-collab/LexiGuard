import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { getContracts, getGraphStats } from '../api/client';
import Button from '../components/Button';
import BigLink from '../components/BigLink';
import GraphVisual from '../components/GraphVisual';
import GraphField from '../components/GraphField';
import FloatingCards from '../components/FloatingCards';
import ContractsModal from '../components/ContractsModal';

// The home page previews this many contracts; the rest open in the modal.
const HOME_LIMIT = 6;
import Parallax from '../components/Parallax';
import Reveal from '../components/Reveal';
import SplitHeading from '../components/SplitHeading';
import { useSite } from '../lib/SiteContext';
import { gsap, ScrollTrigger, EASE, EASE_IMAGE, prefersReducedMotion } from '../lib/motion';

const STEPS = [
  { title: 'Parse', items: ['PDF to clean Markdown', 'Numbered sections kept', 'Exhibits and recitals kept', 'Sub-clauses kept verbatim'] },
  { title: 'Extract', items: ['Parties and aliases resolved', '41 CUAD clause categories', 'Governing law captured', 'Locations captured'] },
  { title: 'Connect', items: ['One Neo4j knowledge graph', 'References and overrides', 'Supersedes and excludes', 'Semantic index per chunk'] },
  { title: 'Answer', items: ['Graph and vector evidence', 'Relevance check first', 'Abstains, never guesses', 'Cites every clause used'] },
];

const ArrowIcon = () => (
  <svg viewBox="0 0 36 36" fill="none" aria-hidden="true">
    <path d="M36 36H29V12.0195L5.5 36H0.101562V31L23.5244 7H0V0H36V36Z" fill="currentColor" />
  </svg>
);

// Floating cards for the two full-screen sections. x/y are percentages of the
// section, z is depth in px (more negative = further away), ry/rz are degrees.
const STATEMENT_CARDS = [
  { kind: 'clause', x: 5, y: 5, z: -200, ry: 18, rz: -4, num: '§ 7.2', title: 'Limitation of liability', text: 'Neither party is liable for indirect or consequential loss.', meta: 'References § 12.1' },
  { kind: 'pattern', pattern: 'checker', x: 24, y: 17, z: -450, ry: 10, rz: 6, w: 9 },
  { kind: 'party', x: 37, y: 3, z: -100, ry: -6, rz: 2, w: 11, label: 'Party', title: 'Licensor', meta: '4 obligations' },
  { kind: 'pattern', pattern: 'mark', x: 54, y: 22, z: -350, ry: -12, rz: -3, w: 10 },
  { kind: 'clause', x: 64, y: 6, z: -50, ry: -16, rz: 3, num: '§ 4.1', title: 'Fees and payment', text: 'Invoices are due within 30 days of receipt.', meta: 'Modified by § 4.3' },
  { kind: 'law', x: 84, y: 14, z: -300, ry: -20, rz: -5, w: 10, label: 'Governed by', title: 'New York', meta: '§ 12.1' },
  { kind: 'pattern', pattern: 'stripes', x: 77, y: 44, z: -500, ry: -22, rz: 5, w: 8, desktopOnly: true },
  { kind: 'pattern', pattern: 'waves', x: 13, y: 40, z: -560, ry: 24, rz: 3, w: 8, desktopOnly: true },
  { kind: 'pattern', pattern: 'dots', x: 66, y: 44, z: -620, ry: -8, rz: -4, w: 7, desktopOnly: true },
];
const ANSWER_CARDS = [
  { kind: 'answer', x: 58, y: 8, z: -60, ry: -14, rz: 2, w: 14, q: 'Can either party terminate early?', a: "Yes, with 60 days' written notice.", cite: '§ 9.2 · Termination' },
  { kind: 'clause', x: 7, y: 7, z: -260, ry: 18, rz: -3, num: '§ 9.2', title: 'Termination for convenience', text: "Either party may end this agreement with 60 days' notice.", meta: 'Excluded by § 9.4' },
  { kind: 'pattern', pattern: 'checker', x: 32, y: 2, z: -480, ry: 8, rz: 5, w: 9 },
  { kind: 'party', x: 84, y: 34, z: -380, ry: -20, rz: -4, w: 10, label: 'Party', title: 'Licensee', meta: '3 obligations', desktopOnly: true },
  { kind: 'pattern', pattern: 'mark', x: 25, y: 33, z: -420, ry: 14, rz: -2, w: 10, desktopOnly: true },
  { kind: 'pattern', pattern: 'waves', x: 87, y: 3, z: -560, ry: -24, rz: 4, w: 8 },
  { kind: 'law', x: 43, y: 28, z: -620, ry: 0, rz: 3, w: 9, label: 'Jurisdiction', title: 'Maryland', meta: '§ 15' },
];

const cleanTitle = title => String(title || 'Untitled contract').replace(/^#+\s*/, '').trim();
const initialsOf = title => cleanTitle(title)
  .split(/\s+/).map(w => w.replace(/[^A-Za-z]/g, '')).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase() || 'LG';

function CountUp({ value, loading, unavailable }) {
  const ref = useRef(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || loading || unavailable) return undefined;
    const target = Number(value) || 0;
    if (prefersReducedMotion()) { el.textContent = target.toLocaleString(); return undefined; }
    // Count up when the number is actually on screen. An IntersectionObserver
    // is used instead of a ScrollTrigger because this sits inside a section
    // that is itself moving (the tilted sheet), which skewed the trigger point.
    const counter = { n: 0 };
    let tween;
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      observer.disconnect();
      tween = gsap.to(counter, {
        n: target,
        duration: 1.6,
        ease: EASE,
        onUpdate: () => { el.textContent = Math.round(counter.n).toLocaleString(); },
      });
    }, { threshold: 0.4 });
    observer.observe(el);
    return () => { observer.disconnect(); tween?.kill(); };
  }, [value, loading, unavailable]);
  if (loading) return <span className="skeleton">000</span>;
  if (unavailable) return <span className="text-[var(--muted)]" aria-label="Not available">—</span>;
  return <span ref={ref}>0</span>;
}

// One card of the "areas of expertise" grid, with the reference site's hover
// timeline: overlay grows from the top right (0.7s), title turns dark at 0.1s,
// icon turns 180° at 0.2s, list rises in at 0.3s; leaving reverses at 1.5×.
function ExpertiseItem({ step, index }) {
  const ref = useRef(null);
  const tlRef = useRef(null);
  const [open, setOpen] = useState(false);

  useLayoutEffect(() => {
    const el = ref.current;
    const ctx = gsap.context(() => {
      gsap.set('.expertise_overlay', { scaleX: 0, scaleY: 0, transformOrigin: 'top right' });
      gsap.set('.expertise_list-item', { y: '1em', opacity: 0 });
      tlRef.current = gsap.timeline({ paused: true })
        .to('.expertise_overlay', { scaleX: 1, scaleY: 1, duration: 0.7, ease: EASE }, 0)
        .to(['.expertise_title', '.expertise_caption'], { color: '#052824', duration: 0.5, ease: EASE }, 0.1)
        .to('.expertise_icon', { rotation: 180, duration: 0.7, ease: EASE }, 0.2)
        .to('.expertise_list-item', { y: '0em', opacity: 1, duration: 0.5, ease: EASE, stagger: 0.06 }, 0.3);
    }, el);
    return () => ctx.revert();
  }, []);

  const play = () => { tlRef.current?.timeScale(1).play(); setOpen(true); };
  const reverse = () => { tlRef.current?.timeScale(1.5).reverse(); setOpen(false); };

  return (
      <div
        ref={ref}
        className="expertise_item"
        role="button"
        tabIndex={0}
        aria-expanded={open}
        aria-label={`${step.title}: ${step.items.join(', ')}`}
        onMouseEnter={play}
        onMouseLeave={reverse}
        onFocus={play}
        onBlur={reverse}
        onClick={() => (open ? reverse() : play())}
        onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); open ? reverse() : play(); } }}
      >
        <span className="expertise_overlay" aria-hidden="true" />
        <div className="expertise_item-top">
          <span>0{index + 1}</span>
          <span className="expertise_icon"><ArrowIcon /></span>
        </div>
        <ul className="expertise_item-left" aria-hidden="true">
          {step.items.map(item => <li key={item} className="expertise_list-item">{item}</li>)}
        </ul>
        <div>
          <h3 className="expertise_title">{step.title}</h3>
        </div>
      </div>
  );
}

export default function Dashboard() {
  const { introDone } = useSite();
  const [stats, setStats] = useState({ total_contracts: 0, total_parties: 0, total_clauses: 0, total_relationships: 0 });
  const [contracts, setContracts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showAll, setShowAll] = useState(false);
  const closeAll = useCallback(() => setShowAll(false), []);
  const viewAllRef = useRef(null);

  const heroRef = useRef(null);
  const imgRef = useRef(null);
  const firstParallaxRef = useRef(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsData, contractsData] = await Promise.all([getGraphStats(), getContracts()]);
      setStats(statsData);
      setContracts(contractsData);
    } catch {
      setError('Dashboard data could not be loaded. Check that the backend is running.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { if (!loading) requestAnimationFrame(() => ScrollTrigger.refresh()); }, [loading]);

  // Hero intro. The start state and the timeline share one context, so a
  // remount (React StrictMode, or a reload that skips the preloader) reverts
  // and rebuilds them together. Offsets match the reference, relative to its
  // 3.05s start: words 0s, rows close 2.01s, image opens 2.11s, tags 2.8s.
  useLayoutEffect(() => {
    if (prefersReducedMotion()) return undefined;
    const hero = heroRef.current;
    const ctx = gsap.context(() => {
      // y: 0 clears any pixel offset left in GSAP's transform cache.
      gsap.set(['.hero_word', '.hero_bottom-txt'], { y: 0, yPercent: 100 });
      gsap.set('.hero_heading-wrap', { width: '100%' });
      gsap.set('.hero_img-wrap', { width: '0%' });
      if (!introDone) return;

      const wraps = gsap.utils.toArray('.hero_heading-wrap', hero);
      const natural = wraps.map(wrap => {
        wrap.style.width = 'auto';
        const width = wrap.getBoundingClientRect().width;
        wrap.style.width = '100%';
        return width;
      });
      gsap.timeline()
        .to('.hero_word', { y: 0, yPercent: 0, duration: 1.2, stagger: { amount: 0.8 }, ease: EASE }, 0)
        .to(wraps, { width: i => natural[i], duration: 1.3, ease: EASE, clearProps: 'width' }, 2.01)
        .to('.hero_img-wrap', { width: '100%', duration: 1.2, ease: EASE_IMAGE }, 2.11)
        .to('.hero_bottom-txt', { y: 0, yPercent: 0, duration: 0.6, stagger: { amount: 0.35 }, ease: EASE }, 2.8);
    }, hero);
    return () => ctx.revert();
  }, [introDone]);

  // Sections marked .sheet rise over the one before as a tilted sheet and
  // settle flat as they reach the upper third of the screen (grail-app.com).
  useLayoutEffect(() => {
    if (prefersReducedMotion()) return undefined;
    const ctx = gsap.context(() => {
      gsap.utils.toArray('.sheet').forEach(sheet => {
        gsap.fromTo(sheet,
          { rotation: -3.5, yPercent: 6, scale: 0.94, transformOrigin: '50% 0%' },
          {
            rotation: 0,
            yPercent: 0,
            scale: 1,
            ease: 'none',
            scrollTrigger: { trigger: sheet, start: 'top bottom', end: 'top 30%', scrub: true },
          });
      });
    });
    return () => ctx.revert();
  }, []);

  // The hero is sticky, so it would show through the gaps around a tilted
  // sheet. Hide it once the first full-screen section fully covers it.
  useLayoutEffect(() => {
    const st = ScrollTrigger.create({
      trigger: firstParallaxRef.current,
      start: 'top top',
      onEnter: () => gsap.set(heroRef.current, { visibility: 'hidden' }),
      onLeaveBack: () => gsap.set(heroRef.current, { visibility: 'visible' }),
    });
    return () => st.kill();
  }, []);

  // The hero image zooms to 1.5× while the first full-screen section scrolls over it.
  useLayoutEffect(() => {
    if (prefersReducedMotion()) return undefined;
    const ctx = gsap.context(() => {
      gsap.to(imgRef.current, {
        scale: 1.5,
        ease: 'none',
        scrollTrigger: { trigger: firstParallaxRef.current, start: 'clamp(top bottom)', end: 'clamp(bottom top)', scrub: 1 },
      });
    });
    return () => ctx.revert();
  }, []);

  return (
    <div className="page">
      {/* Hero */}
      <section ref={heroRef} className="section is_hero">
        <div className="hero_spacer" />
        <div className="container-x">
          <h1 className="hero_layout" aria-label="Every clause, made clear.">
            <span className="hero_heading-wrap" aria-hidden="true">
              <span className="hero_heading hero_mask"><span className="hero_word">Every</span></span>
              <span className="hero_heading hero_mask"><span className="hero_word">clause</span></span>
            </span>
            <span className="hero_img-layout" aria-hidden="true">
              <span className="hero_img-wrap">
                <span className="hero_img">
                  <GraphVisual ref={imgRef} />
                </span>
              </span>
            </span>
            <span className="hero_heading-wrap" aria-hidden="true">
              <span className="hero_heading is_second hero_mask"><span className="hero_word">made</span></span>
              <span className="hero_heading is_second hero_mask"><span className="hero_word">clear.</span></span>
            </span>
          </h1>
        </div>
        <div className="container-x">
          <div className="hero_bottom">
            <span className="hero_bottom-txt">Knowledge graph</span>
            <span className="hero_bottom-txt">Semantic search</span>
            <span className="hero_bottom-txt">Corrective RAG</span>
            <span className="hero_bottom-txt">Cited answers</span>
          </div>
        </div>
      </section>

      {/* Full-screen statement */}
      <div ref={firstParallaxRef} className="parallax-fullscreen">
        <div className="parallax-top">
          <div className="container-x"><div className="bolt-wrap"><span className="bolt" /><span className="bolt" /></div></div>
        </div>
        <div className="parallax-bottom">
          <div className="container-x">
            <div className="max-width-78">
              <SplitHeading as="p" className="text-xlarge">
                Contracts should be clear, not complicated. LexiGuard reads every party, clause and cross-reference
                into one knowledge graph, checks its own evidence, and answers with the clause behind each claim.
              </SplitHeading>
            </div>
          </div>
        </div>
        <Parallax className="parallax-bg is_100" start={-8} end={8} scrub={1}>
          <GraphField seed={7} mark={false} />
          <div className="parallax-bg_overlay" />
        </Parallax>
        <FloatingCards cards={STATEMENT_CARDS} />
      </div>

      {/* How it works: the expertise grid */}
      <section className="section sheet">
        <div className="container-x">
          <div className="horizontal_flex-between">
            <SplitHeading className="max-w-[18ch]">How every contract is read</SplitHeading>
            <BigLink to="/query">Ask a question</BigLink>
          </div>
          {/* All four steps in one row so the whole process fits on one screen. */}
          <Reveal className="steps-grid">
            {STEPS.map((step, index) => <ExpertiseItem key={step.title} step={step} index={index} />)}
          </Reveal>
        </div>
      </section>

      {/* Second full-screen section */}
      <div className="parallax-fullscreen">
        <div className="parallax-top">
          <div className="container-x"><div className="bolt-wrap"><span className="bolt" /><span className="bolt" /></div></div>
        </div>
        <div className="parallax-bottom">
          <div className="container-x">
            <div className="horizontal_flex-between">
              <SplitHeading className="max-w-[20ch]">Every answer cites the clause behind it.</SplitHeading>
              <BigLink to="/evaluation">See the evaluation</BigLink>
            </div>
          </div>
        </div>
        <Parallax className="parallax-bg" start={-8} end={8} scrub={1}>
          <GraphField seed={23} nodes={60} mark={false} />
          <div className="parallax-bg_overlay" />
        </Parallax>
        <FloatingCards cards={ANSWER_CARDS} />
      </div>

      {/* Repository */}
      <section className="section sheet">
        <div className="container-x">
          <div className="horizontal_flex-between">
            <SplitHeading className="heading-extra">Contracts at a glance</SplitHeading>
            {error ? <Button size="sm" icon={RefreshCw} onClick={fetchData}>Retry</Button> : <BigLink to="/upload">Upload a contract</BigLink>}
          </div>

          {error && <div className="notice mt-10" role="alert">{error}</div>}

          <Reveal className="grid_12-col mt-14">
            {[
              ['Contracts', contracts.length],
              ['Parties', stats.total_parties],
              ['Clauses', stats.total_clauses],
              ['Relationships', stats.total_relationships],
            ].map(([label, value], index) => (
              <div className="stat-item span-3" key={label}>
                <div className="stat-item__label"><span>{label}</span><span>0{index + 1}</span></div>
                <div className="stat-item__value"><CountUp value={value} loading={loading} unavailable={!!error} /></div>
              </div>
            ))}
          </Reveal>

          <div className="mt-24">
            {loading ? (
              <div className="grid_12-col" aria-busy="true">
                {[0, 1, 2].map(key => (
                  <div key={key} className="blog_item span-4">
                    <div className="blog_item-img skeleton" />
                    <span className="skeleton h-5 w-1/2" />
                    <span className="skeleton h-7 w-4/5" />
                  </div>
                ))}
              </div>
            ) : contracts.length === 0 ? (
              <div className="panel flex flex-col items-start gap-6 p-8">
                <p className="text-large">{error ? 'Contracts appear here once the backend responds.' : 'No contracts in the graph yet.'}</p>
                <Button to="/upload">Upload the first contract</Button>
              </div>
            ) : (
              <Reveal className="grid_12-col">
                {contracts.slice(0, HOME_LIMIT).map(contract => {
                  const title = cleanTitle(contract.title);
                  return (
                    <article key={contract.contract_id} className="blog_item span-4" data-cursor-text="Open contract">
                      <div className="blog_item-img" aria-hidden="true">
                        <div>
                          <div className="thumb-lines"><i /><i /><i /></div>
                          <span className="bolt thumb-bolt" />
                          <span className="thumb-initials">{initialsOf(title)}</span>
                          <span className="thumb-meta">{contract.clause_count || 0} clauses</span>
                        </div>
                      </div>
                      <div className="blog_item-content">
                        <div className="blog_item-tag-wrap">
                          <span className="blog_item-tag">{contract.contract_type || 'Contract'}</span>
                          <span className="blog_item-tag">{contract.governing_law || 'Law not stated'}</span>
                        </div>
                        <h3 className="blog_item-title" title={title}>
                          <Link to={`/contract/${encodeURIComponent(contract.contract_id)}`}>{title}</Link>
                        </h3>
                        {contract.parties?.length > 0 && <p className="text-white">{contract.parties.join(', ')}</p>}
                        <div className="blog_item-foot">
                          <Link
                            to={`/query?contractId=${encodeURIComponent(contract.contract_id)}`}
                            className="text-link"
                            data-cursor-text="Ask about it"
                          >
                            Ask about this contract
                          </Link>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </Reveal>
            )}
            {!loading && contracts.length > HOME_LIMIT && (
              <div className="repo-more">
                <p>Showing {HOME_LIMIT} of {contracts.length} contracts.</p>
                <Button ref={viewAllRef} onClick={() => setShowAll(true)} aria-haspopup="dialog">
                  {`View all ${contracts.length} contracts`}
                </Button>
              </div>
            )}
          </div>
        </div>
      </section>
      <ContractsModal open={showAll} onClose={closeAll} contracts={contracts} returnFocusRef={viewAllRef} />
    </div>
  );
}
