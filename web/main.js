import { createMapPoller } from './js/pollMap.js';
// Main page bootstrap: fetch -> validate -> build models -> render.

import {
  validateNetwork,
  validateLayout,
  validateMapState,
  buildLinePaths,
  buildStationMarkers,
  buildTrainMarkers
} from './js/mapModel.js';
import { formatClock, trainCountLabel, sourceLabel } from './js/format.js';
import { drawBase, drawTrains, renderLegend } from './js/render/svgMap.js';

const REFRESH_MS = 10_000;

const svg = document.getElementById('map');
const statusEl = document.getElementById('status');
const sourcePill = document.getElementById('source-pill');
const trainCountEl = document.getElementById('train-count');
const legendEl = document.getElementById('legend');

const fetchJson = async (url) => {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} responded ${response.status}`);
  }
  return response.json();
};

const setStatus = (message) => {
  statusEl.textContent = message;
};

let network, layout, linePaths, trainLayer;
const poll = createMapPoller({
  fetchConfig: () => fetchJson('/api/v1/map-config'),
  fetchState: async () => validateMapState(await fetchJson('/api/v1/map-state')),
  onConfig: (config) => {
    network = validateNetwork(config.network);
    layout = validateLayout(config.layout);
    linePaths = buildLinePaths(network, layout);
    trainLayer = drawBase(svg, layout, linePaths, buildStationMarkers(network, layout));
    renderLegend(legendEl, linePaths);
  },
  onState: (state) => {
    drawTrains(trainLayer, buildTrainMarkers(state, network, layout));
    renderLegend(legendEl, linePaths, state.lineSources);
    sourcePill.textContent = sourceLabel(state);
    sourcePill.classList.toggle('live', state.source === 'ntas');
    trainCountEl.textContent = trainCountLabel(state.trains.length);
    setStatus(`Updated ${formatClock(state.generatedAt) || 'just now'}`);
  }
});

const refresh = async () => {
  try {
    await poll();
  } catch (error) {
    trainLayer?.replaceChildren();
    sourcePill.textContent = 'unavailable';
    sourcePill.classList.remove('live');
    trainCountEl.textContent = '';
    setStatus(`Update failed: ${error.message}`);
  } finally {
    setTimeout(refresh, REFRESH_MS);
  }
};
refresh();
