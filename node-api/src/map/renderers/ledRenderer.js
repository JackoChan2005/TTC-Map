// Renders a MapState frame into the packed LED bitmask the ESP32 polls.
// Each board revision is just a mapping file in hardware/led-maps/ —
// adding a display means adding a file, not code.

const fs = require('fs');
const path = require('path');

const LED_MAPS_DIR = path.resolve(__dirname, '..', '..', '..', '..', 'Hardware', 'led-maps');

const loadLedMap = (name) => {
  if (!/^[a-z][a-z0-9-]*$/.test(name)) {
    throw new Error(`Invalid LED map name: ${name}`);
  }
  const mapPath = path.join(LED_MAPS_DIR, `${name}.json`);
  if (!fs.existsSync(mapPath)) {
    return null;
  }
  return JSON.parse(fs.readFileSync(mapPath, 'utf8'));
};

const renderLedState = (mapState, ledMap) => {
  const on = [];
  for (const led of ledMap.leds) {
    if (mapState.stationsWithTrains[led.station]) {
      on.push(led.index);
    }
  }

  const bytes = Buffer.alloc(Math.ceil(ledMap.ledCount / 8));
  for (const index of on) {
    bytes[Math.floor(index / 8)] |= 1 << (index % 8);
  }

  return {
    generatedAt: mapState.generatedAt,
    source: mapState.source,
    map: ledMap.name,
    ledCount: ledMap.ledCount,
    on,
    bits: bytes.toString('hex')
  };
};

module.exports = {
  loadLedMap,
  renderLedState,
  LED_MAPS_DIR
};
