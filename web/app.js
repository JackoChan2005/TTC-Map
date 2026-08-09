const form = document.getElementById('search-form');
const routeInput = document.getElementById('route');
const atTimeInput = document.getElementById('at-time');
const nowBtn = document.getElementById('now-btn');
const searchBtn = document.getElementById('search-btn');
const statusEl = document.getElementById('status');
const resultsEl = document.getElementById('results');
const bestMatchEl = document.getElementById('best-match');
const matchesEl = document.getElementById('matches');

// line names, colors and terminals come from the canonical topology;
// the page still works (with neutral styling) if it fails to load
let linesByRouteId = {};

const loadNetwork = async () => {
  try {
    const response = await fetch('/api/v1/network');
    if (!response.ok) {
      return;
    }
    const network = await response.json();
    for (const line of network.lines) {
      const first = network.stations[line.stations[0]];
      const last = network.stations[line.stations[line.stations.length - 1]];
      linesByRouteId[line.routeId] = {
        name: line.name,
        color: line.color,
        textColor: line.textColor,
        terminals: { 0: last ? last.name : null, 1: first ? first.name : null }
      };
    }
  } catch {
    // non-fatal: cards render without line styling
  }
};

const toDateTimeLocalValue = (date) => {
  const offsetMs = date.getTimezoneOffset() * 60 * 1000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
};

const setNow = () => {
  atTimeInput.value = toDateTimeLocalValue(new Date());
};

const formatGtfsTime = (value) => {
  const match = String(value || '').match(/^(\d+):([0-5]\d):([0-5]\d)$/);
  if (!match) {
    return String(value || 'N/A');
  }
  const hours = Number(match[1]);
  const clock = hours % 24;
  const suffix = clock >= 12 ? 'p.m.' : 'a.m.';
  const display = `${clock % 12 === 0 ? 12 : clock % 12}:${match[2]} ${suffix}`;
  return hours >= 24 ? `${display} (after midnight)` : display;
};

// "King Station - Southbound Platform" -> "King" (direction is shown separately)
const cleanStopName = (value) => String(value || '')
  .replace(/ - (North|South|East|West)bound Platform$/i, '')
  .replace(/ Station$/i, '');

const formatDelta = (seconds) => {
  if (typeof seconds !== 'number' || Number.isNaN(seconds)) {
    return null;
  }
  if (seconds < 60) {
    return `departs in ${seconds} s`;
  }
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest === 0 ? `departs in ${minutes} min` : `departs in ${minutes} min ${rest} s`;
};

const node = (tag, className, text) => {
  const element = document.createElement(tag);
  if (className) {
    element.className = className;
  }
  if (text !== undefined) {
    element.textContent = text;
  }
  return element;
};

const createDepartureCard = (record, { highlight = false } = {}) => {
  const payload = record.payload || {};
  const line = linesByRouteId[payload.route_id];

  const card = node('article', `card departure${highlight ? ' highlight' : ''}`);

  const top = node('div', 'card-top');
  const pill = node('span', 'line-pill', line ? line.name : `Route ${payload.route_id ?? '?'}`);
  if (line) {
    pill.style.background = line.color;
    pill.style.color = line.textColor;
  }
  top.appendChild(pill);

  const terminal = line ? line.terminals[payload.direction_id] : null;
  if (terminal) {
    top.appendChild(node('span', 'direction', `to ${terminal}`));
  }
  card.appendChild(top);

  const main = node('div', 'departure-main');
  main.appendChild(node('strong', 'stop-name', cleanStopName(payload.stop_name) || 'Unknown station'));
  main.appendChild(node('span', 'departure-time', formatGtfsTime(payload.departure_time)));
  card.appendChild(main);

  const metaParts = [];
  const delta = formatDelta(record.deltaSeconds);
  if (delta) {
    metaParts.push(delta);
  }
  if (payload.trip_id) {
    metaParts.push(`trip ${payload.trip_id}`);
  }
  if (metaParts.length > 0) {
    card.appendChild(node('div', 'departure-meta', metaParts.join(' · ')));
  }

  const details = node('details', 'raw-record');
  details.appendChild(node('summary', null, 'Raw record'));
  details.appendChild(node('pre', null, JSON.stringify(payload, null, 2)));
  card.appendChild(details);

  return card;
};

const showStatus = (message, isError = false) => {
  statusEl.textContent = message;
  statusEl.style.color = isError ? '#9f1239' : '#556173';
};

const clearResults = () => {
  bestMatchEl.replaceChildren();
  matchesEl.replaceChildren();
  resultsEl.classList.add('hidden');
};

nowBtn.addEventListener('click', setNow);

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const route = routeInput.value.trim();
  if (!route) {
    showStatus('Route number is required.', true);
    return;
  }

  const selectedAt = atTimeInput.value ? new Date(atTimeInput.value) : new Date();
  const atIso = Number.isNaN(selectedAt.getTime()) ? new Date().toISOString() : selectedAt.toISOString();
  const url = `/api/v1/departures?route=${encodeURIComponent(route)}&at=${encodeURIComponent(atIso)}`;

  showStatus('Searching departures…');
  clearResults();
  searchBtn.disabled = true;

  try {
    const response = await fetch(url);
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.message || 'Route search failed');
    }

    const count = result.totalMatches;
    showStatus(`${count} departure${count === 1 ? '' : 's'} for route ${result.route} within 2 minutes.`);

    bestMatchEl.appendChild(createDepartureCard(result.bestMatch, { highlight: true }));
    for (const record of result.matches.slice(1)) {
      matchesEl.appendChild(createDepartureCard(record));
    }

    resultsEl.classList.remove('hidden');
  } catch (error) {
    showStatus(error.message, true);
  } finally {
    searchBtn.disabled = false;
  }
});

setNow();
loadNetwork();
