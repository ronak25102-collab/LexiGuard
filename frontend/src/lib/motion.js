import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { SplitText } from 'gsap/SplitText';

gsap.registerPlugin(ScrollTrigger, SplitText);

// Motion values read from the reference site's interaction data.
// Webflow ease index 27 is expo.inOut and index 9 is power3.inOut.
export const EASE = 'expo.inOut';
export const EASE_IMAGE = 'power3.inOut';

// Line reveal used for every heading and paragraph marked "typo".
export const TYPO = { duration: 1.2, stagger: 0.08, start: 'top 80%' };

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export const isFinePointer = () =>
  typeof window !== 'undefined' &&
  window.matchMedia('(hover: hover) and (pointer: fine)').matches;

export { gsap, ScrollTrigger, SplitText };
