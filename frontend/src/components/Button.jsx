import { Link } from 'react-router-dom';
import RollText from './RollText';

// The reference site's character-roll button: mint block, letters roll up on
// hover and the background insets by 0.125em. Variants: solid, outline.
export default function Button({
  to,
  href,
  variant = 'solid',
  size = 'md',
  icon: Icon,
  className = '',
  children,
  ...rest
}) {
  const classes = `btn ${variant === 'outline' ? 'btn--outline' : ''} ${size === 'sm' ? 'btn--sm' : ''} roll-trigger ${className}`;
  const body = (
    <>
      <span className="btn__bg" aria-hidden="true" />
      <RollText stagger={0.01}>{children}</RollText>
      {Icon && <Icon size={size === 'sm' ? 13 : 15} strokeWidth={2} aria-hidden="true" />}
    </>
  );
  if (to) return <Link to={to} className={classes} {...rest}>{body}</Link>;
  if (href) return <a href={href} className={classes} {...rest}>{body}</a>;
  return <button type="button" className={classes} {...rest}>{body}</button>;
}
