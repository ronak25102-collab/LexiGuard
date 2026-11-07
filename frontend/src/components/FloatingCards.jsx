import { useLayoutEffect, useMemo, useRef } from 'react';
import BrandMark from './BrandMark';
import { gsap, EASE, prefersReducedMotion } from '../lib/motion';

const MINT = '#b1f9e1';

// Small patterned faces for the decorative cards, in the site's greens.
function Pattern({ type }) {
  if (type === 'mark') {
    return (
      <div className="fcard__mark">
        <BrandMark strokeWidth={2.6} />
      </div>
    );
  }
  return (
    <svg viewBox="0 0 30 40" preserveAspectRatio="xMidYMid slice">
      {type === 'checker' && Array.from({ length: 40 }, (_, i) => {
        const x = (i % 5) * 6;
        const y = Math.floor(i / 5) * 5;
        return (i + Math.floor(i / 5)) % 2 === 0
          ? <rect key={i} x={x} y={y} width="6" height="5" fill={MINT} opacity="0.85" />
          : null;
      })}
      {type === 'stripes' && Array.from({ length: 14 }, (_, i) => (
        <line key={i} x1={i * 5 - 30} y1="40" x2={i * 5} y2="0" stroke={MINT} strokeWidth="1.6" opacity="0.8" />
      ))}
      {type === 'dots' && Array.from({ length: 48 }, (_, i) => (
        <rect key={i} x={(i % 6) * 5 + 1.5} y={Math.floor(i / 6) * 5 + 1.5} width="2" height="2" fill={MINT} opacity={i % 7 === 0 ? 1 : 0.45} />
      ))}
      {type === 'waves' && Array.from({ length: 6 }, (_, i) => (
        <path key={i} d={`M-2 ${4 + i * 7} q 4 -4 8 0 t 8 0 t 8 0 t 8 0`} fill="none" stroke={MINT} strokeWidth="1.8" opacity="0.8" />
      ))}
    </svg>
  );
}

function CardFace({ card }) {
  switch (card.kind) {
    case 'clause':
      return (
        <>
          <span className="fcard__num">{card.num}</span>
          <strong className="fcard__title">{card.title}</strong>
          <p className="fcard__text">{card.text}</p>
          <span className="fcard__meta">{card.meta}</span>
        </>
      );
    case 'party':
    case 'law':
      return (
        <>
          <span className="fcard__top"><span className="fcard__label">{card.label}</span><span className="fcard__bolt" /></span>
          <span>
            <strong className="fcard__big">{card.title}</strong>
            {card.meta && <span className="fcard__sub">{card.meta}</span>}
          </span>
        </>
      );
    case 'answer':
      return (
        <>
          <span className="fcard__label">Question</span>
          <strong className="fcard__q">{card.q}</strong>
          <span className="fcard__label mt-auto">Answer</span>
          <p className="fcard__a">{card.a}</p>
          <span className="fcard__cite">{card.cite}</span>
        </>
      );
    default:
      return <Pattern type={card.pattern} />;
  }
}

// A field of contract "cards" floating in depth behind a full-screen section,
// after grail-app.com: each card drifts up and turns as the section scrolls
// past, nearer cards travelling further, and the set fades in from random order.
// `cards` items: { kind, x, y (percent), z (px, negative = further), ry, rz (deg), w (rem), desktopOnly }.
export default function FloatingCards({ cards: input }) {
  const ref = useRef(null);
  // Far cards first, so nearer cards paint on top of them.
  const cards = useMemo(() => [...input].sort((a, b) => a.z - b.z), [input]);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion()) return undefined;
    const section = el.closest('.parallax-fullscreen') || el.parentElement;
    const ctx = gsap.context(() => {
      gsap.utils.toArray('.fcard', el).forEach((item, i) => {
        const card = cards[i];
        const depth = Math.min(1, Math.max(0, (card.z + 600) / 800)); // 0 far … 1 near
        const travel = 120 + depth * 280;
        const turn = card.ry >= 0 ? 16 : -16;
        gsap.fromTo(item,
          { y: travel, z: card.z - 140, rotationY: card.ry - turn, rotationZ: card.rz },
          {
            y: -travel,
            z: card.z + 160,
            rotationY: card.ry + turn,
            rotationZ: -card.rz * 0.5,
            ease: 'none',
            scrollTrigger: { trigger: section, start: 'top bottom', end: 'bottom top', scrub: true },
          });
      });
      gsap.from(gsap.utils.toArray('.fcard__inner', el), {
        autoAlpha: 0,
        scale: 0.8,
        duration: 1.4,
        ease: EASE,
        stagger: { each: 0.05, from: 'random' },
        scrollTrigger: { trigger: section, start: 'top 75%', once: true },
      });
    }, el);
    return () => ctx.revert();
  }, [cards]);

  return (
    <div ref={ref} className="fcards" aria-hidden="true">
      {cards.map((card, i) => {
        const depth = Math.min(1, Math.max(0, (card.z + 600) / 800));
        return (
          <div
            key={i}
            className={`fcard ${card.desktopOnly ? 'is-desktop' : ''}`}
            style={{
              left: `${card.x}%`,
              top: `${card.y}%`,
              '--w': `${card.w ?? 12}rem`,
              transform: `translate3d(0, 0, ${card.z}px) rotateY(${card.ry}deg) rotateZ(${card.rz}deg)`,
            }}
          >
            {/* Further cards are darker (not transparent), which reads as depth without see-through overlaps. */}
            <div className={`fcard__inner fcard--${card.kind}`} style={{ filter: `brightness(${(0.55 + depth * 0.45).toFixed(2)})` }}>
              <CardFace card={card} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
