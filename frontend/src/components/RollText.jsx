// Splits a label into characters that roll upward on hover of the nearest
// `.roll-trigger` ancestor. Screen readers get the plain label once.
export default function RollText({ children, stagger = 0.012, className = '' }) {
  const text = String(children);
  return (
    <span className={`roll ${className}`}>
      <span className="sr-only">{text}</span>
      <span aria-hidden="true" className="contents">
        {[...text].map((char, index) => (
          <span key={index} className="roll__char" style={{ transitionDelay: `${index * stagger}s` }}>
            {char}
          </span>
        ))}
      </span>
    </span>
  );
}
