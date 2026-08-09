const SVG_NS = 'http://www.w3.org/2000/svg';
const REFRESH_MS = 10_000;

const svg = document.getElementById('map');
const statusEl = document.getElementById('status');
const sourcePill = document.getElementById('source-pill');
const trainCountEl = document.getElementById('train-count');
const legendEl = document.getElementById('legend');

let network = null;
let layout = null;
let trainLayer = null;

const el = (tag, attrs) => {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    node.setAttribute(key, value);
  }
  return node;
};

const pos = (stationId) => layout.stations[stationId];

const drawBase = () => {
  svg.setAttribute('viewBox', `0 0 ${layout.width} ${layout.height}`);
  svg.replaceChildren();

  for (const line of network.lines) {
    const points = line.stations.map((s) => {
      const p = pos(s);
      return `${p.x},${p.y}`;
    }).join(' ');

    svg.appendChild(el('polyline', {
      points,
      fill: 'none',
      stroke: line.color,
      'stroke-width': 5,
      'stroke-linecap': 'round',
      'stroke-linejoin': 'round'
    }));
  }

  for (const [stationId, station] of Object.entries(network.stations)) {
    const p = pos(stationId);
    if (!p) {
      continue;
    }
    const lineColor = network.lines.find((l) => l.id === station.lines[0]).color;
    const circle = el('circle', {
      cx: p.x,
      cy: p.y,
      r: station.interchange ? 7 : 4.5,
      class: `station${station.interchange ? ' interchange' : ''}`,
      stroke: station.interchange ? undefined : lineColor
    });
    if (!station.interchange) {
      circle.setAttribute('stroke', lineColor);
    }
    const title = document.createElementNS(SVG_NS, 'title');
    title.textContent = station.name;
    circle.appendChild(title);
    svg.appendChild(circle);
  }

  trainLayer = el('g', { id: 'trains' });
  svg.appendChild(trainLayer);

  legendEl.replaceChildren(...network.lines.map((line) => {
    const span = document.createElement('span');
    span.className = 'legend-line';
    span.innerHTML = `<span class="legend-swatch" style="background:${line.color}"></span>`;
    span.appendChild(document.createTextNode(line.name));
    return span;
  }));
};

const trainPoint = (train) => {
  if (train.at) {
    return pos(train.at);
  }
  const [a, b] = train.between;
  const pa = pos(a);
  const pb = pos(b);
  return {
    x: pa.x + (pb.x - pa.x) * train.progress,
    y: pa.y + (pb.y - pa.y) * train.progress
  };
};

const drawTrains = (state) => {
  trainLayer.replaceChildren();

  for (const train of state.trains) {
    const p = trainPoint(train);
    if (!p) {
      continue;
    }
    const line = network.lines.find((l) => l.id === train.line);
    const dot = el('circle', {
      cx: p.x,
      cy: p.y,
      r: 5.5,
      class: 'train',
      fill: line ? line.color : '#1f2937'
    });
    const title = document.createElementNS(SVG_NS, 'title');
    const where = train.at ? `at ${train.stationName}` : `near ${train.stationName}`;
    title.textContent = `${line ? line.name : train.line} train ${where}`;
    dot.appendChild(title);
    trainLayer.appendChild(dot);
  }

  const live = state.source === 'ntas';
  sourcePill.textContent = live ? 'live · NTAS' : `schedule simulation${state.fallback ? ' (realtime unavailable)' : ''}`;
  sourcePill.classList.toggle('live', live);
  trainCountEl.textContent = `${state.trainCount} trains`;
  statusEl.textContent = `Updated ${new Date(state.generatedAt).toLocaleTimeString()}`;
};

const refresh = async () => {
  try {
    const response = await fetch('/api/v1/map-state');
    if (!response.ok) {
      throw new Error(`map-state HTTP ${response.status}`);
    }
    drawTrains(await response.json());
  } catch (error) {
    statusEl.textContent = `Update failed: ${error.message}`;
  }
};

const start = async () => {
  try {
    const [networkRes, layoutRes] = await Promise.all([
      fetch('/api/v1/network'),
      fetch('/api/v1/layout/geographic')
    ]);
    if (!networkRes.ok || !layoutRes.ok) {
      throw new Error('failed to load network/layout');
    }
    network = await networkRes.json();
    layout = await layoutRes.json();

    drawBase();
    await refresh();
    setInterval(refresh, REFRESH_MS);
  } catch (error) {
    statusEl.textContent = `Failed to load map: ${error.message}`;
  }
};

start();
