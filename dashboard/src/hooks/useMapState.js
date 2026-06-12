import { useEffect, useState } from 'react';

const REFRESH_MS = 15_000;
const FALLBACK_TRAINS = 97;

// Live train count from the existing map-state API; the response is
// untrusted input, so only a validated number ever leaves this hook.
export const useMapState = () => {
  const [trainCount, setTrainCount] = useState(FALLBACK_TRAINS);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    const refresh = async () => {
      try {
        const response = await fetch('/api/v1/map-state');
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        const count = Number(data?.trainCount);
        if (!Number.isFinite(count) || count < 0) {
          throw new Error('malformed response');
        }
        if (!cancelled) {
          setTrainCount(Math.floor(count));
          setError(null);
        }
      } catch {
        if (!cancelled) {
          setError('Update / Load failed');
        }
      }
    };

    refresh();
    const timer = setInterval(refresh, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  return { trainCount, error };
};
