const fs = require('fs');
const path = require('path');

const SHARED_DIR = path.resolve(__dirname, '..', '..', '..', 'shared');

let cached;

const loadTopology = () => {
  if (!cached) {
    const raw = fs.readFileSync(path.join(SHARED_DIR, 'network.json'), 'utf8');
    cached = JSON.parse(raw);
  }
  return cached;
};

const loadLayout = (name) => {
  if (!/^[a-z][a-z0-9-]*$/.test(name)) {
    throw new Error(`Invalid layout name: ${name}`);
  }
  const layoutPath = path.join(SHARED_DIR, 'layouts', `${name}.json`);
  if (!fs.existsSync(layoutPath)) {
    return null;
  }
  return JSON.parse(fs.readFileSync(layoutPath, 'utf8'));
};

// stations of a line in travel order for a direction
// (network.json lists direction_id 0 order)
const stationOrder = (topology, lineId, direction) => {
  const line = topology.lines.find((l) => l.id === lineId);
  if (!line) {
    return [];
  }
  return direction === 0 ? line.stations : [...line.stations].reverse();
};

// station the train came from, given the station it is approaching
const previousStation = (topology, lineId, direction, stationId) => {
  const order = stationOrder(topology, lineId, direction);
  const idx = order.indexOf(stationId);
  return idx > 0 ? order[idx - 1] : null;
};

module.exports = {
  loadTopology,
  loadLayout,
  stationOrder,
  previousStation,
  SHARED_DIR
};
