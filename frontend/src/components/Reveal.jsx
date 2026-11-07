import { useLayoutEffect, useRef } from 'react';
import { gsap, EASE, prefersReducedMotion } from '../lib/motion';

// Fades and lifts children into view once, using the site's expo.inOut and
// the 30% rise it uses for its team cards.
export default function Reveal({
  as: Tag = 'div',
  children,
  className = '',
  stagger = 0.1,
  delay = 0,
  self = false,
  y = 40,
  ...rest
}) {
  const ref = useRef(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion()) return undefined;
    const ctx = gsap.context(() => {
      gsap.from(self ? el : el.children, {
        yPercent: self ? 0 : 30,
        y: self ? y : 0,
        autoAlpha: 0,
        duration: 1,
        ease: EASE,
        stagger,
        delay,
        scrollTrigger: { trigger: el, start: 'top 85%', once: true },
      });
    }, el);
    return () => ctx.revert();
  }, [stagger, delay, self, y]);

  return <Tag ref={ref} className={className} {...rest}>{children}</Tag>;
}
