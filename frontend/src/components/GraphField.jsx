import { useMemo } from 'react';
import BrandMark from './BrandMark';

// Small seeded random generator so the field looks the same on every render.
function seeded(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

// Full-bleed background for the parallax sections: a wide knowledge graph
// fading into the dark green, with the LexiGuard mark as a large watermark.
export default function GraphField({ seed = 7, nodes = 46, mark = true }) {
  const { points, links } = useMemo(() => {
    const rand = seeded(seed);
    const points = Array.from({ length: nodes }, () => ({
      x: 40 + rand() * 1420,
      y: 40 + rand() * 920,
      big: rand() > 0.86,
    }));
    const links = [];
    points.forEach((p, i) => {
      const nearest = points
        .map((q, j) => ({ j, d: (p.x - q.x) ** 2 + (p.y - q.y) ** 2 }))
        .filter(({ j }) => j !== i)
        .sort((a, b) => a.d - b.d)
        .slice(0, 2);
      nearest.forEach(({ j }) => { if (i < j) links.push([i, j]); });
    });
    return { points, links };
  }, [seed, nodes]);

  return (
    <div className="graph-field" aria-hidden="true">
      <svg viewBox="0 0 1500 1000" preserveAspectRatio="xMidYMid slice">
        <g stroke="rgba(177,249,225,0.16)" strokeWidth="1">
          {links.map(([a, b]) => (
            <line key={`${a}-${b}`} x1={points[a].x} y1={points[a].y} x2={points[b].x} y2={points[b].y} />
          ))}
        </g>
        {points.map((p, i) => (
          <rect key={i} x={p.x - (p.big ? 6 : 3)} y={p.y - (p.big ? 6 : 3)}
            width={p.big ? 12 : 6} height={p.big ? 12 : 6}
            fill={p.big ? '#b1f9e1' : 'rgba(177,249,225,0.45)'} />
        ))}
      </svg>
      {mark && (
        <BrandMark
          className="absolute right-[6%] top-1/2 w-[38%] -translate-y-1/2 text-[var(--color-mint)] opacity-[0.07]"
          strokeWidth={1.4}
        />
      )}
    </div>
  );
}
