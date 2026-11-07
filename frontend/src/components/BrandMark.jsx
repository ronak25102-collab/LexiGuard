// Line-art version of the LexiGuard scale-and-laurel logo. Drawn with strokes
// so the preloader can trace it; every path carries the `mark-path` class.
export default function BrandMark({ className = '', strokeWidth = 2.4, title }) {
  return (
    <svg
      className={className}
      viewBox="0 0 64 60"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={title ? 'img' : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      {/* Finial and pillar */}
      <path className="mark-path" d="M32 3.5 L34.2 7.5 L32 11 L29.8 7.5 Z" />
      <path className="mark-path" d="M32 11 V44" />
      {/* Beam */}
      <path className="mark-path" d="M11 15.5 Q32 9.5 53 15.5" />
      {/* Left pan */}
      <path className="mark-path" d="M12 15.5 L6 29 M12 15.5 L18 29" />
      <path className="mark-path" d="M4.5 29 Q12 36 19.5 29 Z" />
      {/* Right pan */}
      <path className="mark-path" d="M52 15.5 L46 29 M52 15.5 L58 29" />
      <path className="mark-path" d="M44.5 29 Q52 36 59.5 29 Z" />
      {/* Base */}
      <path className="mark-path" d="M27 44 Q32 41 37 44 L40 47.5 H24 Z" />
      {/* Laurel */}
      <path className="mark-path" d="M27 56.5 Q11 55 6 41" />
      <path className="mark-path" d="M37 56.5 Q53 55 58 41" />
      <path className="mark-path" d="M12.5 51 l-4.5 0.8 M9 46.5 l-4 -0.6 M18 54.3 l-3.6 2.2" />
      <path className="mark-path" d="M51.5 51 l4.5 0.8 M55 46.5 l4 -0.6 M46 54.3 l3.6 2.2" />
      <path className="mark-path" d="M29 56.5 H35" />
    </svg>
  );
}
