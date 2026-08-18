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

const start = async () => {
  let network;
  let layout;
  try {
    const [rawNetwork, rawLayout] = await Promise.all([
      fetchJson('/api/v1/network'),
      fetchJson('/api/v1/layout/schematic')
    ]);
    network = validateNetwork(rawNetwork);
    layout = validateLayout(rawLayout);
  } catch (error) {
    setStatus(`Failed to load the map: ${error.message}`);
    return;
  }

  const linePaths = buildLinePaths(network, layout);
  const trainLayer = drawBase(svg, layout, linePaths, buildStationMarkers(network, layout));
  renderLegend(legendEl, linePaths);

  const refresh = async () => {
    try {
      const state = validateMapState(await fetchJson('/api/v1/map-state'));
      drawTrains(trainLayer, buildTrainMarkers(state, network, layout));

      sourcePill.textContent = sourceLabel(state);
      sourcePill.classList.toggle('live', state.source === 'ntas');
      trainCountEl.textContent = trainCountLabel(state.trains.length);
      setStatus(`Updated ${formatClock(state.generatedAt) || 'just now'}`);
    } catch (error) {
      setStatus(`Update failed: ${error.message}`);
    }
  };

  await refresh();
  setInterval(refresh, REFRESH_MS);
};

start();
