import { useEffect, useState } from 'react';
import { healthCheck } from '../api/client';

let cached = null;
let pending = null;

// Shared, once-per-page-load health check so the menu and footer agree.
function checkOnce() {
  if (cached) return Promise.resolve(cached);
  if (!pending) {
    pending = healthCheck()
      .then(data => {
        // The API answered; the graph may still be down ("degraded").
        cached = data?.neo4j_connected ? 'online' : 'degraded';
        return cached;
      })
      .catch(() => {
        cached = 'offline';
        return cached;
      });
  }
  return pending;
}

export function useApiStatus() {
  const [state, setState] = useState(cached || 'checking');
  useEffect(() => {
    let alive = true;
    checkOnce().then(value => { if (alive) setState(value); });
    return () => { alive = false; };
  }, []);
  return state;
}
