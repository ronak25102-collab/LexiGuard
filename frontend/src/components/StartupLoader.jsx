import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Scale } from 'lucide-react';

const ease = [0.76, 0, 0.24, 1];

export default function StartupLoader({ onComplete }) {
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const timer = window.setTimeout(onComplete, 2400);
    const skipOnEscape = event => {
      if (event.key === 'Escape') onComplete();
    };
    window.addEventListener('keydown', skipOnEscape);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener('keydown', skipOnEscape);
      document.body.style.overflow = previousOverflow;
    };
  }, [onComplete]);

  return (
    <motion.section className="startup-loader" aria-label="Opening LexiGuard"
      initial={{ clipPath: 'inset(0% 0% 0% 0%)' }}
      exit={{ clipPath: 'inset(0% 0% 100% 0%)' }}
      transition={{ duration: 0.65, ease }}>
      <div className="startup-glow startup-glow-one" aria-hidden="true" />
      <div className="startup-glow startup-glow-two" aria-hidden="true" />

      <header className="startup-header">
        <span className="startup-identity"><img src="/logo.png" alt="" /> Legal intelligence</span>
        <button type="button" className="startup-skip" onClick={onComplete} autoFocus>
          Skip intro <ArrowRight size={14} aria-hidden="true" />
        </button>
      </header>

      <div className="startup-center">
        <motion.div className="startup-document-scene" aria-hidden="true"
          initial={{ opacity: 0, y: 45, scale: 0.8 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}>
          <motion.div className="startup-document startup-document-back"
            initial={{ x: 0, rotate: 0 }} animate={{ x: 35, rotate: 13 }}
            transition={{ delay: 0.25, duration: 1, ease }} />
          <motion.div className="startup-document startup-document-middle"
            initial={{ x: 0, rotate: 0 }} animate={{ x: -27, rotate: -12 }}
            transition={{ delay: 0.2, duration: 1, ease }} />
          <motion.div className="startup-document startup-document-front"
            initial={{ rotateY: -35, rotateX: 15, rotate: -8 }}
            animate={{ rotateY: -12, rotateX: 6, rotate: -3 }}
            transition={{ duration: 1.6, ease: [0.16, 1, 0.3, 1] }}>
            <div className="startup-document-top"><span /><span /><span /></div>
            <div className="startup-seal"><Scale size={44} strokeWidth={1.2} /></div>
            <div className="startup-document-lines"><i /><i /><i /><i /></div>
            <span className="startup-document-corner" />
          </motion.div>
        </motion.div>

        <div className="startup-wordmark" aria-hidden="true">
          {'LexiGuard'.split('').map((letter, index) => (
            <span className="startup-letter-mask" key={index}>
              <motion.span className={index >= 4 ? 'startup-letter startup-letter-light' : 'startup-letter'}
                initial={{ y: '115%', rotate: index % 2 ? 9 : -9, opacity: 0 }}
                animate={{ y: '0%', rotate: 0, opacity: 1 }}
                transition={{ delay: 0.18 + index * 0.045, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}>
                {letter}
              </motion.span>
            </span>
          ))}
        </div>
        <motion.p className="startup-tagline" initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.8, duration: 0.55 }}>
          Legal intelligence, made clear.
        </motion.p>
      </div>

      <footer className="startup-footer">
        <span role="status" className="startup-status">Opening your workspace</span>
        <div className="startup-track" aria-hidden="true">
          <motion.span initial={{ scaleX: 0 }} animate={{ scaleX: 1 }}
            transition={{ duration: 2.25, ease: [0.3, 0, 0.2, 1] }} />
        </div>
        <span className="startup-footer-note">Your contracts. Connected.</span>
      </footer>
    </motion.section>
  );
}
