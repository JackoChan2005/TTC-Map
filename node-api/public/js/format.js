// Small display formatting helpers. Pure functions, no DOM.

export const formatClock = (isoString) => {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit' });
};

export const trainCountLabel = (count) =>
  `${count} train${count === 1 ? '' : 's'}`;

export const sourceLabel = (state) => {
  if (state.source === 'ntas') {
    return 'live';
  }
  return state.fallback ? 'schedule (realtime unavailable)' : 'schedule';
};
