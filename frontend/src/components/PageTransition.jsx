import { useEffect, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

// expo.inOut, the reference site's ease, as a cubic-bezier.
const ease = [0.87, 0, 0.13, 1];
let hasNavigated = false;

// Route change: a green panel wipes up over the old page (same clip-path
// motion as the menu tile), then lifts off the new one.
export default function PageTransition({ children }) {
  const reducedMotion = useReducedMotion();
  const [isRouteChange] = useState(() => hasNavigated);
  useEffect(() => { hasNavigated = true; }, []);

  if (reducedMotion) {
    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
        {children}
      </motion.div>
    );
  }

  return (
    <motion.div initial={{ opacity: 1 }} animate={{ opacity: 1 }} exit={{ opacity: 1, transition: { duration: 0.8 } }}>
      {children}
      {isRouteChange && (
        <motion.div
          className="curtain"
          aria-hidden="true"
          initial={{ clipPath: 'polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)' }}
          animate={{ clipPath: 'polygon(0% 0%, 100% 0%, 100% 0%, 0% 0%)' }}
          transition={{ duration: 1, ease, delay: 0.05 }}
        />
      )}
      <motion.div
        className="curtain"
        aria-hidden="true"
        initial={{ clipPath: 'polygon(0% 100%, 100% 100%, 100% 100%, 0% 100%)' }}
        animate={{ clipPath: 'polygon(0% 100%, 100% 100%, 100% 100%, 0% 100%)' }}
        exit={{ clipPath: 'polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)' }}
        transition={{ duration: 0.8, ease }}
      />
    </motion.div>
  );
}
