import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, CalendarDays, FileText, MapPin, MessageSquare, Plus } from 'lucide-react';
import ForceGraph2D from 'react-force-graph-2d';
import { getContractDetail } from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';
import PageHeader from '../components/PageHeader';
import Reveal from '../components/Reveal';
import Button from '../components/Button';

const COLORS = {
  Contract: '#ffffff',
  Party: '#b1f9e1',
  Clause: '#4fd1a9',
  Law: '#818180',
  link: 'rgba(177, 249, 225, 0.2)',
  crossRef: 'rgba(177, 249, 225, 0.75)',
};

const cleanTitle = title => String(title || 'Untitled contract').replace(/^#+\s*/, '').trim();

// Keeps the force graph the size of its panel instead of a fixed 800×600.
// Returns a callback ref: the panel only mounts after the contract loads, so
// measuring has to start when the element appears, not when the page mounts.
function useElementSize() {
  const [size, setSize] = useState({ width: 0, height: 0 });
  const observerRef = useRef(null);
  const ref = useCallback(el => {
    observerRef.current?.disconnect();
    observerRef.current = null;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ width: Math.floor(width), height: Math.floor(height) });
    });
    observer.observe(el);
    observerRef.current = observer;
  }, []);
  useEffect(() => () => observerRef.current?.disconnect(), []);
  return [ref, size];
}

export default function ContractDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [contract, setContract] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedClauses, setExpandedClauses] = useState({});
  const graphRef = useRef();
  const [graphWrapRef, graphSize] = useElementSize();

  useEffect(() => {
    const fetchDetail = async () => {
      try {
        const data = await getContractDetail(id);
        // The API returns { contract, parties, clauses, cross_references }.
        const mergedContract = {
          ...data.contract,
          parties: data.parties ? data.parties.map(p => p.name) : [],
          clauses: data.clauses,
          crossReferences: data.cross_references || [],
          governingLaw: data.contract.governing_law,
          effectiveDate: data.contract.effective_date,
        };
        setContract(mergedContract);
        const initialExpanded = {};
        (mergedContract.clauses || []).forEach((_, idx) => { initialExpanded[idx] = false; });
        setExpandedClauses(initialExpanded);
      } catch {
        setError('Failed to load contract details.');
      } finally {
        setLoading(false);
      }
    };
    fetchDetail();
  }, [id]);

  const toggleClause = (idx) => setExpandedClauses(prev => ({ ...prev, [idx]: !prev[idx] }));

  const graphData = useMemo(() => {
    if (!contract) return { nodes: [], links: [] };
    const nodes = [];
    const links = [];
    const contractNodeId = `Contract_${contract.id}`;
    nodes.push({ id: contractNodeId, name: cleanTitle(contract.title), group: 'Contract', color: COLORS.Contract, val: 14 });

    if (contract.governingLaw) {
      const lawId = `Law_${contract.governingLaw}`;
      nodes.push({ id: lawId, name: contract.governingLaw, group: 'Law', color: COLORS.Law, val: 4 });
      links.push({ source: contractNodeId, target: lawId, name: 'GOVERNED_BY', color: COLORS.link });
    }
    (contract.parties || []).forEach((party, i) => {
      const partyId = `Party_${i}_${party}`;
      nodes.push({ id: partyId, name: party, group: 'Party', color: COLORS.Party, val: 5 });
      links.push({ source: contractNodeId, target: partyId, name: 'HAS_PARTY', color: COLORS.link });
    });
    (contract.clauses || []).forEach((clause, i) => {
      const clauseId = `Clause_${i}`;
      nodes.push({ id: clauseId, name: clause.title || `Clause ${i + 1}`, group: 'Clause', color: COLORS.Clause, val: 1.5 });
      links.push({ source: contractNodeId, target: clauseId, name: 'CONTAINS_CLAUSE', color: COLORS.link });
    });

    const clauseIds = new Map((contract.clauses || []).map((clause, i) => [clause.number, `Clause_${i}`]));
    (contract.crossReferences || []).forEach(ref => {
      const source = clauseIds.get(ref.source);
      const target = clauseIds.get(ref.target);
      if (source && target) links.push({ source, target, name: ref.relationship, color: COLORS.crossRef, dashed: true });
    });
    return { nodes, links };
  }, [contract]);

  // The library's defaults (links ~30px long, weak repulsion) pile every
  // clause into a tight ring around the contract. Scale the clause ring with
  // the number of clauses so each one gets room, and push nodes apart.
  const hasGraph = graphSize.width > 0;
  const fittedRef = useRef(false);
  useEffect(() => {
    const fg = graphRef.current;
    if (!fg || !hasGraph) return;
    const clauseCount = contract?.clauses?.length || 0;
    const ring = Math.max(70, Math.min(240, clauseCount * 2.4));
    fg.d3Force('charge')?.strength(-45).distanceMax(ring * 2.5);
    fg.d3Force('link')?.distance(link => {
      if (link.dashed) return 22;
      return link.name === 'CONTAINS_CLAUSE' ? ring : ring * 0.45;
    });
    fittedRef.current = false;
    fg.d3ReheatSimulation();
  }, [graphData, hasGraph, contract]);

  // Draws names under the contract, party and law nodes; clause names stay
  // on hover so 95 labels don't cover the graph.
  const drawLabel = useCallback((node, ctx, scale) => {
    if (node.group === 'Clause') return;
    const radius = Math.sqrt(node.val) * 4;
    const name = node.name.length > 30 ? `${node.name.slice(0, 29)}…` : node.name;
    ctx.font = `500 ${11 / scale}px Satoshi, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillStyle = node.group === 'Contract' ? '#ffffff' : 'rgba(177, 249, 225, 0.85)';
    ctx.fillText(name, node.x, node.y + radius + 3 / scale);
  }, []);

  if (loading) {
    return <div className="page grid place-items-center"><LoadingSpinner text="Loading contract…" /></div>;
  }
  if (error || !contract) {
    return (
      <div className="page">
        <PageHeader eyebrow="Contract" title="This contract could not be opened." description={error || 'It may have been removed from the graph.'}
          actions={<Button to="/" variant="outline" icon={ArrowLeft}>Back to the Dashboard</Button>} />
      </div>
    );
  }

  const title = cleanTitle(contract.title);
  const clauses = contract.clauses || [];

  return (
    <div className="page">
      <PageHeader
        eyebrow="Contract"
        title={title}
        actions={(
          <>
            <Button variant="outline" size="sm" icon={ArrowLeft} onClick={() => navigate(-1)}>Back</Button>
            <Button size="sm" icon={MessageSquare} to={`/query?contractId=${encodeURIComponent(contract.id || id)}`}>Ask about this contract</Button>
          </>
        )}
      >
        <Reveal className="mt-6 flex flex-wrap gap-2" delay={0.4}>
          <span className="chip"><FileText size={13} aria-hidden="true" /> {contract.type || 'Standard contract'}</span>
          <span className="chip"><MapPin size={13} aria-hidden="true" /> {contract.governingLaw || 'Jurisdiction not stated'}</span>
          {contract.effectiveDate && <span className="chip"><CalendarDays size={13} aria-hidden="true" /> Effective {contract.effectiveDate}</span>}
          {contract.parties?.length > 0 && <span className="chip">{contract.parties.length} parties</span>}
          <span className="chip">{clauses.length} clauses</span>
        </Reveal>
      </PageHeader>

      <section className="container-x grid gap-6 pb-24 pt-8 lg:grid-cols-2">
        <Reveal self y={40}>
          <div className="panel panel--dark flex h-[clamp(26rem,70vh,44rem)] flex-col overflow-hidden">
            <div className="panel__head">
              <h2 className="panel__title">Knowledge graph</h2>
              <div className="legend">
                {['Contract', 'Party', 'Clause', 'Law'].map(group => (
                  <span key={group}><i style={{ background: COLORS[group] }} />{group}</span>
                ))}
              </div>
            </div>
            <div ref={graphWrapRef} className="relative min-h-0 flex-1" data-cursor-text="Drag to explore · Ctrl + scroll to zoom">
              {graphSize.width > 0 && (
                <ForceGraph2D
                  ref={graphRef}
                  graphData={graphData}
                  width={graphSize.width}
                  height={graphSize.height}
                  nodeLabel="name"
                  nodeColor="color"
                  nodeVal="val"
                  linkColor="color"
                  linkLineDash={link => (link.dashed ? [4, 4] : null)}
                  linkDirectionalArrowLength={3.5}
                  linkDirectionalArrowRelPos={1}
                  linkDirectionalParticles={link => (link.dashed ? 2 : 0)}
                  linkDirectionalParticleColor={() => COLORS.Party}
                  nodeCanvasObjectMode={() => 'after'}
                  nodeCanvasObject={drawLabel}
                  cooldownTicks={200}
                  maxZoom={6}
                  // Plain wheel scrolls the page; Ctrl/⌘ + wheel (and touchpad pinch) zooms.
                  enableZoomInteraction={event => event.ctrlKey || event.metaKey}
                  onEngineStop={() => {
                    // Fit once per layout; refitting after every drag would yank the view.
                    if (fittedRef.current) return;
                    fittedRef.current = true;
                    const fg = graphRef.current;
                    if (!fg) return;
                    fg.zoomToFit(500, 40);
                    // Small contracts fit at a very high zoom; keep nodes a sensible size.
                    setTimeout(() => { if (fg.zoom() > 2.2) fg.zoom(2.2, 300); }, 520);
                  }}
                  backgroundColor="rgba(0,0,0,0)"
                />
              )}
            </div>
          </div>
        </Reveal>

        <Reveal self y={40} delay={0.1}>
          <div className="panel flex h-[clamp(26rem,70vh,44rem)] flex-col overflow-hidden">
            <div className="panel__head">
              <h2 className="panel__title">Clauses</h2>
              <span className="text-sm text-[var(--muted)]">{clauses.length} total</span>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-2">
              {clauses.length === 0 ? (
                <p className="text-body mt-10 text-center">No clauses found in this contract.</p>
              ) : clauses.map((clause, idx) => {
                const open = !!expandedClauses[idx];
                return (
                  <div key={idx} className="accordion__item" data-open={open}>
                    <button type="button" className="accordion__btn" aria-expanded={open} aria-controls={`clause-${idx}`} onClick={() => toggleClause(idx)}>
                      <span className="accordion__num">{clause.number || String(idx + 1).padStart(2, '0')}</span>
                      <span className="accordion__title">{clause.title || `Section ${idx + 1}`}</span>
                      <span className="accordion__icon" aria-hidden="true"><Plus size={14} /></span>
                    </button>
                    <div className="accordion__panel" id={`clause-${idx}`} role="region">
                      <div><p className="accordion__text">{clause.text}</p></div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </Reveal>
      </section>
    </div>
  );
}
