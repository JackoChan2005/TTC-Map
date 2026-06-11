// Pure: turns TrainPosition[] from any source into a MapState frame.
// No database or HTTP imports — sources are injected by the caller.
//
// TrainPosition: { line, direction, from, to, progress, tripId? }
//   from/to are station ids; to=null means the train is at `from`.
// MapState.trains entry: { line, direction, at, between, progress, nearestStation }

const AT_STATION_THRESHOLD = 0.2;

const computeMapState = (topology, positions, { source, generatedAt } = {}) => {
  const trains = [];
  const stationsWithTrains = {};

  for (const pos of positions) {
    if (!topology.stations[pos.from]) {
      continue;
    }

    const hasSegment = pos.to && topology.stations[pos.to] && pos.to !== pos.from;
    const progress = hasSegment ? Math.min(Math.max(pos.progress ?? 0, 0), 1) : 0;

    let at = null;
    let between = null;
    if (!hasSegment || progress <= AT_STATION_THRESHOLD) {
      at = pos.from;
    } else if (progress >= 1 - AT_STATION_THRESHOLD) {
      at = pos.to;
    } else {
      between = [pos.from, pos.to];
    }

    const nearestStation = at ?? (progress < 0.5 ? pos.from : pos.to);
    stationsWithTrains[nearestStation] = (stationsWithTrains[nearestStation] || 0) + 1;

    trains.push({
      line: pos.line,
      direction: pos.direction,
      tripId: pos.tripId ?? null,
      at,
      between,
      progress,
      nearestStation,
      stationName: topology.stations[nearestStation].name
    });
  }

  return {
    generatedAt: generatedAt ?? new Date().toISOString(),
    source: source ?? 'unknown',
    trainCount: trains.length,
    trains,
    stationsWithTrains
  };
};

module.exports = {
  computeMapState,
  AT_STATION_THRESHOLD
};
