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
