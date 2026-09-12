// API-backed search and departure joins, independent of DOM rendering.
export function searchNetwork(network, query) {
  const term = query.trim().toLocaleLowerCase();
  if (!term) return [];
  return [
    ...network.lines.filter(line => `${line.number} ${line.name}`.toLocaleLowerCase().includes(term))
      .map(line => ({ type: 'line', id: line.id, name: line.name, lines: [line.id] })),
    ...Object.entries(network.stations).filter(([, station]) => station.name.toLocaleLowerCase().includes(term))
      .map(([id, station]) => ({ type: 'station', id, name: station.name, lines: station.lines }))
  ].slice(0, 20);
}

export function stationDepartures(result, network, lineId, stationId, direction) {
  return (Array.isArray(result?.matches) ? result.matches : []).filter(record => {
    const platform = network.platforms?.[record?.payload?.stop_id];
    return platform?.station === stationId && platform.line === lineId
      && (direction == null || Number(record.payload.direction_id) === direction);
  });
}

export function remainingSeconds(record, result, now = Date.now()) {
  if (!Number.isFinite(record?.deltaSeconds)) return null;
  const requested = Date.parse(result?.requestedAt);
  const age = Number.isFinite(requested) ? Math.max(0, Math.floor((now - requested) / 1000)) : 0;
  return record.deltaSeconds - age;
}

export function sourceDescription(state, lineId) {
  if (!state) return 'Data unavailable';
  const info = state.lineSources[lineId];
  if (!info) return 'Source unavailable';
  if (info.source === 'ntas') return 'Live observations';
  if (info.source === 'schedule') return info.reason === 'realtime_not_enabled'
    ? 'Scheduled estimates' : 'Scheduled estimates · live unavailable';
  return 'Data unavailable';
}
