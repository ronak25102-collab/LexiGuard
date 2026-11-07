import { createElement, useLayoutEffect, useRef } from 'react';
import { gsap, SplitText, EASE, TYPO, prefersReducedMotion } from '../lib/motion';

// The reference site's "typo" reveal: split into masked lines, each line rises
// from 100% below. 1.2s, 0.08s stagger, expo.inOut, when the top reaches 80%
// of the viewport. `trigger="mount"` plays straight away instead.
export default function SplitHeading({
  as = 'h2',
  className = '',
  trigger = 'scroll',
  delay = 0,
  children,
  ...rest
}) {
  const ref = useRef(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    if (prefersReducedMotion()) {
      el.classList.add('is-split');
      return undefined;
    }
    let split;
    const ctx = gsap.context(() => {
      split = SplitText.create(el, {
        type: 'lines',
        mask: 'lines',
        linesClass: 'split-line',
        autoSplit: true,
        onSplit(self) {
          el.classList.add('is-split');
          return gsap.from(self.lines, {
            yPercent: 100,
            duration: TYPO.duration,
            stagger: TYPO.stagger,
            ease: EASE,
            delay,
            scrollTrigger: trigger === 'scroll'
              ? { trigger: el, start: TYPO.start, once: true }
              : undefined,
          });
        },
      });
    }, el);
    return () => {
      ctx.revert();
      split?.revert();
    };
  }, [trigger, delay]);

  return createElement(as, { ref, className, 'data-split': '', ...rest }, children);
}
