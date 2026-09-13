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
  if (state.source === 'mixed') {
    return 'live + scheduled';
  }
  if (state.source === 'ntas') {
    return 'live';
  }
  return state.fallback ? 'schedule (realtime unavailable)' : 'schedule';
};

export const lineSourceLabel = (info) => {
  if (!info) return '';
  if (info.source === 'ntas') return 'live';
  if (info.source === null) return 'not included';
  return ['realtime_not_enabled', 'forced_schedule'].includes(info.reason)
    ? 'scheduled' : 'scheduled (live predictions unavailable)';
};
