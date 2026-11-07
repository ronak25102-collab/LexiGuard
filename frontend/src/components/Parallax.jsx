import { useLayoutEffect, useRef } from 'react';
import { gsap, prefersReducedMotion } from '../lib/motion';

// The reference site's global parallax: yPercent from `start` to `end` while
// the element crosses the viewport (top bottom → bottom top), scrubbed.
// `disableBelow` turns it off under a width, like data-parallax-disable.
export default function Parallax({
  as: Tag = 'div',
  start = 20,
  end = -20,
  scrub = true,
  disableBelow = 0,
  className = '',
  children,
  ...rest
}) {
  const ref = useRef(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion()) return undefined;
    const mm = gsap.matchMedia();
    mm.add(`(min-width: ${disableBelow}px)`, () => {
      gsap.fromTo(el, { yPercent: start }, {
        yPercent: end,
        ease: 'none',
        scrollTrigger: {
          trigger: el,
          start: 'clamp(top bottom)',
          end: 'clamp(bottom top)',
          scrub,
        },
      });
    });
    return () => mm.revert();
  }, [start, end, scrub, disableBelow]);

  return <Tag ref={ref} className={className} {...rest}>{children}</Tag>;
}
