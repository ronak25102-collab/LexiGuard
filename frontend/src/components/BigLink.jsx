import { Link } from 'react-router-dom';
import RollText from './RollText';

// Large underlined text link with the character roll (footer__link on the
// reference site).
export default function BigLink({ to, children, className = '' }) {
  return (
    <Link to={to} className={`big-link roll-trigger ${className}`}>
      <RollText stagger={0.01}>{children}</RollText>
    </Link>
  );
}
