// Four "bolts" lighting in sequence, matching the preloader frame.
export default function LoadingSpinner({ text = 'Loading…' }) {
  return (
    <div className="loader" role="status">
      <span className="loader__bolts" aria-hidden="true"><i /><i /><i /><i /></span>
      {text && <span>{text}</span>}
    </div>
  );
}
