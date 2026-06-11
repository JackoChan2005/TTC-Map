// Source selection for the map state engine.
//   MAP_SOURCE=auto      realtime (NTAS) with automatic schedule fallback
//   MAP_SOURCE=schedule  static GTFS simulation only
//   MAP_SOURCE=ntas      realtime only (errors when the feed is down)

const { loadTopology } = require('./topology');
const { computeMapState } = require('./stateEngine');
const scheduleSource = require('./sources/scheduleSource');
const ntasSource = require('./sources/ntasSource');

const SOURCES = {
  schedule: scheduleSource,
  ntas: ntasSource
};

const getMapState = async ({ now = new Date(), source } = {}) => {
  const topology = loadTopology();
  const mode = source || process.env.MAP_SOURCE || 'auto';

  if (SOURCES[mode]) {
    const positions = await SOURCES[mode].getTrainPositions(now);
    return computeMapState(topology, positions, { source: mode });
  }

  if (mode !== 'auto') {
    throw new Error(`Unknown map source: ${mode}`);
  }

  try {
    const positions = await ntasSource.getTrainPositions(now);
    return computeMapState(topology, positions, { source: 'ntas' });
  } catch (error) {
    console.error(`NTAS source failed (${error.message}), falling back to schedule`);
    const positions = await scheduleSource.getTrainPositions(now);
    const state = computeMapState(topology, positions, { source: 'schedule' });
    state.fallback = true;
    return state;
  }
};

module.exports = {
  getMapState,
  SOURCES
};
