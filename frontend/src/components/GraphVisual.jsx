import { forwardRef, useState } from 'react';
import { prefersReducedMotion } from '../lib/motion';

const MINT = '#b1f9e1';
const WHITE = '#ffffff';

// A small, plausible contract graph. Coordinates are in a 600×400 viewBox,
// which matches the 3:2 hero frame so nothing is cropped.
const CONTRACT = { x: 292, y: 196, label: 'Services Agreement' };
const PARTIES = [
  { x: 130, y: 96, label: 'Licensor', anchor: 'middle', dy: -16 },
  { x: 452, y: 82, label: 'Licensee', anchor: 'middle', dy: -16 },
];
const LAW = { x: 486, y: 318, label: 'New York law' };
const CLAUSES = [
  { x: 88, y: 214, label: '§ 2 Term' },
  { x: 150, y: 284, label: '§ 4.1 Fees' },
  { x: 240, y: 308 },
  { x: 354, y: 344, label: '§ 9 Liability cap' },
  { x: 432, y: 214, label: '§ 12.1 Governing law', key: true },
  { x: 528, y: 146 },
  { x: 340, y: 92 },
  { x: 214, y: 150 },
  { x: 64, y: 290 },
  { x: 386, y: 282 },
];
// Clause-to-clause cross-references (dashed).
const CROSS_REFS = [[0, 1], [2, 3], [3, 9], [7, 6], [1, 8]];
// The path a cited answer traces: contract → § 12.1 → governing law.
const ANSWER_PATH = `M${CONTRACT.x} ${CONTRACT.y} L${CLAUSES[4].x} ${CLAUSES[4].y} L${LAW.x} ${LAW.y}`;

const labelStyle = { fill: 'rgba(177,249,225,0.72)', fontSize: 11, fontWeight: 500, letterSpacing: 0 };

// The hero "image": a contract knowledge graph with the evidence path for one
// answer highlighted, plus a caption showing the question it answers.
const GraphVisual = forwardRef(function GraphVisual(_props, ref) {
  const [animate] = useState(() => !prefersReducedMotion());

  return (
    <div ref={ref} className="graph-visual" aria-hidden="true">
      <svg viewBox="0 0 600 400" preserveAspectRatio="xMidYMid slice">
        <defs>
          <radialGradient id="gv-glow" cx="48%" cy="48%" r="62%">
            <stop offset="0%" stopColor="#0f5f50" />
            <stop offset="55%" stopColor="#063a32" />
            <stop offset="100%" stopColor="#021d1a" />
          </radialGradient>
          <pattern id="gv-dots" width="20" height="20" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="0.8" fill="rgba(177,249,225,0.09)" />
          </pattern>
          <filter id="gv-soft" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="6" />
          </filter>
        </defs>

        <rect width="600" height="400" fill="url(#gv-glow)" />
        <rect width="600" height="400" fill="url(#gv-dots)" />

        {/* Edges from the contract */}
        <g stroke="rgba(177,249,225,0.16)" strokeWidth="1" fill="none">
          {[...PARTIES, LAW, ...CLAUSES].map((node, i) => (
            <line key={i} x1={CONTRACT.x} y1={CONTRACT.y} x2={node.x} y2={node.y} />
          ))}
        </g>

        {/* Cross-references between clauses */}
        <g stroke="rgba(177,249,225,0.42)" strokeWidth="1" strokeDasharray="3 5" fill="none">
          {CROSS_REFS.map(([a, b]) => (
            <line key={`${a}-${b}`} className={animate ? 'graph-flow' : undefined}
              x1={CLAUSES[a].x} y1={CLAUSES[a].y} x2={CLAUSES[b].x} y2={CLAUSES[b].y} />
          ))}
        </g>

        {/* Answer path: soft glow underneath, crisp line on top, and a pulse travelling along it */}
        <path d={ANSWER_PATH} stroke={MINT} strokeWidth="6" opacity="0.35" fill="none" filter="url(#gv-soft)" />
        <path d={ANSWER_PATH} stroke={MINT} strokeWidth="1.6" fill="none" strokeLinejoin="round" />
        {animate && (
          <circle r="3.2" fill={WHITE}>
            <animateMotion dur="3.4s" repeatCount="indefinite" path={ANSWER_PATH} keyPoints="0;1" keyTimes="0;1" calcMode="spline" keySplines="0.65 0 0.35 1" />
          </circle>
        )}

        {/* Clauses */}
        {CLAUSES.map((node, i) => (
          <g key={i}>
            {node.key && <rect x={node.x - 11} y={node.y - 11} width="22" height="22" fill="none" stroke={MINT} strokeOpacity="0.5" />}
            <rect x={node.x - 4} y={node.y - 4} width="8" height="8" fill={node.key ? WHITE : MINT} opacity={node.key ? 1 : 0.85} />
            {node.label && (
              <text x={node.x + (node.key ? 16 : 10)} y={node.y + 4} {...labelStyle}
                fill={node.key ? WHITE : labelStyle.fill}>{node.label}</text>
            )}
          </g>
        ))}

        {/* Parties */}
        {PARTIES.map(node => (
          <g key={node.label}>
            {animate && <rect className="graph-pulse" x={node.x - 8} y={node.y - 8} width="16" height="16" fill={MINT} />}
            <rect x={node.x - 7} y={node.y - 7} width="14" height="14" fill={MINT} />
            <text x={node.x} y={node.y + node.dy} textAnchor={node.anchor} {...labelStyle}>{node.label}</text>
          </g>
        ))}

        {/* Governing law */}
        <rect x={LAW.x - 6} y={LAW.y - 6} width="12" height="12" fill="#021d1a" stroke={MINT} strokeWidth="1.5" />
        <text x={LAW.x + 14} y={LAW.y + 4} {...labelStyle}>{LAW.label}</text>

        {/* Contract */}
        {animate && <rect className="graph-pulse" x={CONTRACT.x - 15} y={CONTRACT.y - 15} width="30" height="30" fill={WHITE} />}
        <rect x={CONTRACT.x - 14} y={CONTRACT.y - 14} width="28" height="28" fill={WHITE} />
        <rect x={CONTRACT.x - 4} y={CONTRACT.y - 4} width="8" height="8" fill="#052824" />
        <text x={CONTRACT.x} y={CONTRACT.y + 30} textAnchor="middle" {...labelStyle} fill={WHITE}>{CONTRACT.label}</text>

        {/* Corner bolts, as on the preloader frame */}
        {[[14, 14], [579, 14], [14, 379], [579, 379]].map(([x, y]) => (
          <rect key={`${x}-${y}`} x={x} y={y} width="7" height="7" fill={MINT} />
        ))}
      </svg>

      <div className="graph-visual__answer">
        <span className="graph-visual__q">Which law governs this agreement?</span>
        <span className="graph-visual__a">New York law <em>· cited § 12.1</em></span>
      </div>
    </div>
  );
});

export default GraphVisual;
