import { forwardRef } from 'react';
import BrandMark from './BrandMark';

// The hero "photo": a LexiGuard business card lying on a wooden board and
// paper in hard afternoon light. Drawn in SVG (600×400, the 3:2 frame) so it
// is crisp at any size; the card itself is HTML so it can hold the logo.
const HeroCard = forwardRef(function HeroCard(_props, ref) {
  return (
    <div ref={ref} className="hero-card" aria-hidden="true">
      <svg className="hero-card__scene" viewBox="0 0 600 400" preserveAspectRatio="xMidYMid slice">
        <defs>
          <linearGradient id="hc-paper" x1="1" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ddd6c9" />
            <stop offset="100%" stopColor="#b8af9f" />
          </linearGradient>
          <linearGradient id="hc-wood" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#f2d5ab" />
            <stop offset="55%" stopColor="#e2bd8c" />
            <stop offset="100%" stopColor="#c79a68" />
          </linearGradient>
          {/* Long, stretched noise reads as wood grain once rotated along the board. */}
          <filter id="hc-grain" x="0" y="0" width="100%" height="100%">
            <feTurbulence type="fractalNoise" baseFrequency="0.004 0.11" numOctaves="3" seed="7" />
            <feColorMatrix type="matrix" values="0 0 0 0 0.42  0 0 0 0 0.26  0 0 0 0 0.11  1.6 0 0 0 -0.62" />
          </filter>
          <filter id="hc-paper-tex" x="0" y="0" width="100%" height="100%">
            <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="3" />
            <feColorMatrix type="matrix" values="0 0 0 0 0.2  0 0 0 0 0.18  0 0 0 0 0.15  0 0 0 0.9 -0.35" />
          </filter>
          <filter id="hc-soft" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="1.4" />
          </filter>
          <filter id="hc-softer" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="5" />
          </filter>
          <clipPath id="hc-board">
            <polygon points="-20,-20 430,-20 150,420 -20,420" />
          </clipPath>
          <radialGradient id="hc-vignette" cx="50%" cy="50%" r="75%">
            <stop offset="60%" stopColor="#000" stopOpacity="0" />
            <stop offset="100%" stopColor="#000" stopOpacity="0.35" />
          </radialGradient>
        </defs>

        {/* Paper surface */}
        <rect width="600" height="400" fill="url(#hc-paper)" />
        <rect width="600" height="400" filter="url(#hc-paper-tex)" opacity="0.5" />

        {/* The board casts a soft shadow onto the paper along its edge */}
        <polygon points="446,-20 488,-20 214,420 166,420" fill="#2b2118" opacity="0.32" filter="url(#hc-softer)" />

        {/* Wooden board, grain rotated along its length, and its lit edge */}
        <g clipPath="url(#hc-board)">
          <rect x="-20" y="-20" width="460" height="440" fill="url(#hc-wood)" />
          <rect x="-300" y="-300" width="1100" height="1100" filter="url(#hc-grain)" opacity="0.55"
            transform="rotate(-57 220 200)" />
        </g>
        <polygon points="430,-20 445,-20 165,420 150,420" fill="#a77c50" />

        {/* Hard sunlight: shadow wedges falling across the scene */}
        <g className="hero-card__shadows">
          <polygon points="352,-20 640,-20 640,300" fill="#0f0d0b" opacity="0.9" filter="url(#hc-soft)" />
          <polygon points="-40,236 -40,440 150,440" fill="#0f0d0b" opacity="0.88" filter="url(#hc-soft)" />
          {/* A faint band of brighter light across the board */}
          <polygon points="-20,70 250,-20 290,-20 -20,128" fill="#fff6e6" opacity="0.14" filter="url(#hc-softer)" />
        </g>

        {/* The card's own cast shadow, down and to the right of it */}
        <polygon points="370,161 396,193 396,283 256,283 230,249" fill="#14110e" opacity="0.78" filter="url(#hc-soft)" />

        <rect width="600" height="400" fill="url(#hc-vignette)" />
      </svg>

      <div className="hero-card__card">
        <div className="hero-card__face">
          <span className="hero-card__dot hero-card__dot--l" />
          <span className="hero-card__dot hero-card__dot--r" />
          <BrandMark className="hero-card__mark" strokeWidth={3} />
          <span className="hero-card__letters">L <i>·</i> G</span>
        </div>
      </div>
    </div>
  );
});

export default HeroCard;
