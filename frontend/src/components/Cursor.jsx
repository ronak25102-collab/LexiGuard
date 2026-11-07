import { useEffect, useRef, useState } from 'react';
import { gsap, isFinePointer, prefersReducedMotion } from '../lib/motion';

// The reference site's dynamic text cursor: a mint bubble follows the pointer
// (0.4s power3.out) over any element with `data-cursor-text`, and flips to the
// left of the pointer near the right edge.
export default function Cursor() {
  const ref = useRef(null);
  const [text, setText] = useState('');
  const [state, setState] = useState('');
  const [enabled] = useState(() => isFinePointer() && !prefersReducedMotion());

  useEffect(() => {
    if (!enabled || !ref.current) return undefined;
    const cursor = ref.current;
    const xTo = gsap.quickTo(cursor, 'x', { duration: 0.4, ease: 'power3.out' });
    const yTo = gsap.quickTo(cursor, 'y', { duration: 0.4, ease: 'power3.out' });
    let mouseX = 0;
    let mouseY = 0;
    let moved = false;

    const update = () => {
      const item = document.elementFromPoint(mouseX, mouseY)?.closest('[data-cursor-text]');
      const rect = cursor.getBoundingClientRect();
      const edge = rect.right >= window.innerWidth;
      setState(item ? (edge ? 'active-edge' : 'active') : '');
      const label = item?.getAttribute('data-cursor-text');
      if (label) setText(label);
    };
    const onMove = event => {
      mouseX = event.clientX;
      mouseY = event.clientY;
      moved = true;
      xTo(mouseX);
      yTo(mouseY);
      requestAnimationFrame(update);
    };
    const onScroll = () => { if (moved) requestAnimationFrame(update); };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('scroll', onScroll);
    };
  }, [enabled]);

  if (!enabled) return null;
  return (
    <div ref={ref} className="cursor" data-cursor={state} aria-hidden="true">
      <div className="cursor-bubble"><span className="cursor-bubble__text">{text}</span></div>
    </div>
  );
}
