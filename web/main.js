import { api } from './js/api.js';
import { createMapPoller } from './js/pollMap.js';
import { validateNetwork, validateLayout, validateMapState } from './js/mapModel.js';
import { sourceLabel } from './js/format.js';
import { searchNetwork, stationDepartures, sourceDescription, remainingSeconds } from './js/uiModel.js';
import { createExplorerMap } from './js/render/explorerMap.js';
import { geographicLayout } from './js/geographic.js';

const $ = id => document.getElementById(id);
const node = (tag, className, text) => {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
};
const button = (text, className, action) => {
  const element = node('button', className, text);
  element.type = 'button';
  element.addEventListener('click', action);
  return element;
};
const color = (element, line) => {
  element.style.setProperty('--route-color', line.color);
  element.style.setProperty('--route-ink', line.textColor);
  return element;
};
const badge = (line, small = false) => color(node('span', 'line-badge' + (small ? ' small' : ''), line.number), line);
const clock = value => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'time unavailable' : date.toLocaleTimeString([], {
    hour: 'numeric', minute: '2-digit', timeZone: 'America/Toronto'
  });
};
let network, config, state = null, line = null, station = null, direction = 0;
let schematic = false, timer, refreshBusy = false, detailRequest = 0, searchRequest = 0;
let departureData = null, departureMessage = '', lastDepartureKey = '';
const preferences = { labels: true, estimates: true, light: false };
const cache = new Map();
const isSearch = () => location.pathname.startsWith('/search');
const map = createExplorerMap($('map'), id => {
  const target = line?.stations.includes(id) ? line : network.lines.find(item => item.stations.includes(id));
  if (target) navigate('/?line=' + encodeURIComponent(target.number) + '&station=' + encodeURIComponent(id));
}, status => {
  $('basemap-status').hidden = status === 'ready' || status === 'schematic';
  $('basemap-status').textContent = status === 'loading' ? 'Loading street map…' : 'Street map unavailable · transit overlay remains available';
  $('basemap-attribution').hidden = status === 'schematic';
});

function notify(text) {
  $('map-message').textContent = text;
  $('map-message').hidden = false;
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => { $('map-message').hidden = true; }, 5000);
}

function navigate(url) {
  history.pushState({}, '', url);
  $('network-search').value = '';
  $('search-results').hidden = true;
  document.querySelector('.context-panel').classList.remove('collapsed');
  document.querySelector('.workspace').classList.remove('panel-collapsed');
  $('collapse-panel').setAttribute('aria-expanded', 'true');
  $('collapse-panel').setAttribute('aria-label', 'Collapse panel');
  $('collapse-panel').textContent = '−';
  $('panel-content').scrollTop = 0;
  applyLocation();
}
document.addEventListener('click', event => {
  const link = event.target.closest('a');
  if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
  const url = new URL(link.href);
  if (url.origin === location.origin && ['/', '/search/'].includes(url.pathname) && !url.hash) {
    event.preventDefault(); navigate(url.pathname + url.search);
  }
});
window.addEventListener('popstate', applyLocation);

function applyLocation() {
  detailRequest++;
  searchRequest++;
  const params = new URLSearchParams(location.search);
  const prior = line?.id;
  line = network?.lines.find(item => item.number === params.get('line')) || null;
  station = line?.stations.includes(params.get('station')) ? params.get('station') : null;
  if (prior !== line?.id) direction = 0;
  $('overview').hidden = isSearch() || !!line;
  $('route-detail').hidden = isSearch() || !line;
  $('departure-view').hidden = !isSearch();
  document.body.classList.toggle('route-mode', !!line && !isSearch());
  $('explore-tab').toggleAttribute('aria-current', !isSearch());
  $('departures-tab').toggleAttribute('aria-current', isSearch());
  (isSearch() ? $('departures-tab') : $('explore-tab')).setAttribute('aria-current', 'page');
  document.title = isSearch() ? 'Scheduled departures · TTC Map' : line ? line.name + ' · TTC Map' : 'TTC Map · Explore Toronto by rail';
  map.select(line, station);
  if (params.has('line') && network && !line) notify('That line is not in the published rail network.');
  if (line && !isSearch()) {
    renderDetail();
    loadDetailDepartures();
  }
  if (isSearch()) {
    if (line) $('route').value = line.number;
    $('search-btn').disabled = !network?.lines.length;
  }
}

function renderOverview() {
  if (!network) return;
  $('line-count').textContent = network.lines.length + ' LINES';
  $('route-list').replaceChildren(...network.lines.map(item => {
    const card = button('', 'route-card', () => navigate('/?line=' + encodeURIComponent(item.number)));
    card.setAttribute('aria-label', 'Explore Line ' + item.number + ' ' + item.name);
    const copy = node('span', 'route-copy');
    copy.append(node('strong', '', item.name), node('small', '', network.stations[item.stations[0]]?.name + ' ↔ ' + network.stations[item.stations.at(-1)]?.name));
    const label = node('small', 'route-source', sourceDescription(state, item.id));
    label.dataset.sourceLine = item.id;
    copy.append(label);
    card.append(badge(item), copy, node('span', 'chevron', '›'));
    return card;
  }));
  if (!network.lines.length) $('route-list').append(node('p', 'empty-copy', 'No rail lines were included in this network.'));
}

function renderDetail() {
  const container = $('route-detail');
  color(container, line);
  const back = button('← All lines', 'back-button', () => navigate('/'));
  const header = color(node('div', 'route-header'), line);
  const text = node('div');
  text.append(node('h2', '', line.name), node('p', '', 'LINE ' + line.number + ' · ' + line.stations.length + ' STATIONS'));
  header.append(badge(line), text);
  const source = node('p', 'section-intro', sourceDescription(state, line.id));
  source.id = 'detail-source';
  const tools = node('div', 'route-tools');
  const label = node('label', '', 'DIRECTION'); label.htmlFor = 'direction';
  const select = node('select'); select.id = 'direction';
  [0, 1].forEach(value => {
    const option = node('option', '', 'To ' + network.stations[value === 0 ? line.stations.at(-1) : line.stations[0]]?.name);
    option.value = value; select.append(option);
  });
  select.value = direction;
  select.addEventListener('change', () => { direction = Number(select.value); renderDetail(); updateTimeline(); });
  tools.append(label, select);
  const timeline = node('ol', 'timeline');
  const order = direction === 0 ? line.stations : [...line.stations].reverse();
  order.forEach(id => {
    const item = node('li');
    const stop = network.stations[id];
    const control = button('', 'station-button', () => navigate('/?line=' + encodeURIComponent(line.number) + '&station=' + encodeURIComponent(id)));
    control.setAttribute('aria-pressed', String(id === station));
    control.append(node('span', 'station-name', stop.name));
    for (const transferId of stop.lines.filter(value => value !== line.id)) {
      const transfer = network.lines.find(value => value.id === transferId);
      if (transfer) { const marker = badge(transfer, true); marker.title = 'Transfer to ' + transfer.name; control.append(marker); }
    }
    const meta = node('span', 'station-meta'); meta.dataset.stationMeta = id;
    control.append(meta); item.append(control);
    if (id === station) { const detail = node('div'); detail.id = 'station-detail'; item.append(detail); }
    timeline.append(item);
  });
  const note = node('p', 'disclosure', 'Positions follow the selected direction. Countdown values are scheduled departures within two minutes, not live arrivals.');
  container.replaceChildren(back, header, source, tools, timeline, note);
  updateTimeline();
  if (station) container.querySelector('[aria-pressed="true"]')?.scrollIntoView({ block: 'nearest' });
}

function updateTimeline() {
  if (!line || isSearch()) return;
  const source = $('detail-source');
  if (source) source.textContent = sourceDescription(state, line.id);
  for (const element of document.querySelectorAll('[data-station-meta]')) {
    const id = element.dataset.stationMeta;
    const trains = (state?.trains || []).filter(train => train.line === line.id && train.direction === direction
      && (train.at === id || train.between?.[1] === id));
    const departures = stationDepartures(departureData, network, line.id, id, direction)
      .filter(record => remainingSeconds(record, departureData) >= 0);
    const seconds = remainingSeconds(departures[0], departureData);
    const schedule = Number.isFinite(seconds) ? Math.max(0, Math.ceil(seconds / 60)) + ' min · sched.' : '';
    element.textContent = trains.length ? trains.length + (state.lineSources[line.id]?.source === 'ntas' ? ' observed' : ' estimated') : schedule;
    element.title = trains.length ? 'Train at or approaching this station' : schedule;
  }
  const detail = $('station-detail');
  if (!detail) return;
  detail.replaceChildren();
  if (!station) return;
  const card = node('div', 'station-info');
  card.append(node('h3', '', network.stations[station].name));
  const departures = stationDepartures(departureData, network, line.id, station, direction)
    .filter(record => remainingSeconds(record, departureData) >= 0);
  card.append(node('p', '', departureData
    ? (departures.length ? departures.map(record => 'Scheduled in ' + remainingSeconds(record, departureData) + ' sec').join(' · ') : 'No upcoming scheduled departure for this direction in the returned two-minute window.')
    : departureMessage || 'Loading scheduled departures…'));
  card.append(node('p', '', 'Live arrival countdowns are not available. Schedule results are capped at 200 across the line.'));
  const link = node('a', '', 'Search this line’s timetable →');
  link.href = '/search/?line=' + encodeURIComponent(line.number); card.append(link);
  const transfers = network.stations[station].lines.filter(id => id !== line.id);
  for (const id of transfers) {
    const target = network.lines.find(item => item.id === id);
    if (target) card.append(button('Transfer to Line ' + target.number, 'secondary', () => navigate('/?line=' + encodeURIComponent(target.number) + '&station=' + encodeURIComponent(station))));
  }
  detail.append(card);
}

async function getDepartures(number) {
  const found = cache.get(number);
  if (found && Date.now() - found.time < 30000) return found.promise;
  const entry = { time: Date.now(), promise: api.departures(number) };
  cache.set(number, entry);
  try { return await entry.promise; } catch (error) { if (cache.get(number) === entry) cache.delete(number); throw error; }
}
async function loadDetailDepartures() {
  if (!line || isSearch()) return;
  const id = ++detailRequest, target = line;
  if (lastDepartureKey !== target.id) { departureData = null; departureMessage = ''; lastDepartureKey = target.id; }
  try {
    const result = await getDepartures(target.number);
    if (id !== detailRequest) return;
    departureData = result; departureMessage = '';
  } catch (error) {
    if (id !== detailRequest) return;
    departureData = null;
    departureMessage = error.status === 404 ? 'No scheduled departures in this two-minute window.' : 'Scheduled departures unavailable. ' + error.message;
  }
  updateTimeline();
}

function useLayout() {
  if (!config || !network) return;
  const geo = !schematic && !!config.geographic;
  map.setConfig(network, geo ? config.geographic : validateLayout(config.layout), geo);
  map.select(line, station);
  $('map-type').textContent = 'Map: ' + (geo ? 'geographic' : 'schematic');
  $('map-caption').textContent = geo ? 'Geographic rail network' : 'Schematic rail network';
  $('geometry-note').textContent = geo
    ? 'Station coordinates from TTC · route connections and train positions are approximate.'
    : 'Schematic layout; not to scale.' + (!config.geographic ? ' Station coordinates unavailable.' : '');
  $('map-type').disabled = !config.geographic;
}
const poll = createMapPoller({
  fetchConfig: () => api.config(),
  fetchState: async () => validateMapState(await api.state()),
  onConfig: value => {
    config = value; network = validateNetwork(value.network);
    config.geographic = geographicLayout(network);
    state = null; departureData = null; cache.clear();
    map.setState(null);
    $('map-empty').hidden = Object.keys(network.stations).length > 0;
    if (!$('map-empty').hidden) {
      $('map-empty').querySelector('h2').textContent = 'No stations published';
      $('map-empty').querySelector('p').textContent = 'The current network contains no station data.';
    }
    $('route').replaceChildren(...network.lines.map(item => {
      const option = node('option', '', 'Line ' + item.number + ' · ' + item.name); option.value = item.number; return option;
    }));
    $('search-btn').disabled = !network.lines.length;
    useLayout(); renderOverview(); applyLocation();
  },
  onState: value => {
    state = value; map.setState(state);
    $('source-status').textContent = sourceLabel(state) + ' · ' + state.trains.length + ' positions';
    $('update-status').textContent = 'Updated ' + clock(state.generatedAt) + ' Toronto';
    $('status-banner').className = 'status-banner available';
    for (const element of document.querySelectorAll('[data-source-line]')) element.textContent = sourceDescription(state, element.dataset.sourceLine);
    updateTimeline();
    if (line && !isSearch()) loadDetailDepartures();
  }
});

async function refresh() {
  if (refreshBusy) return;
  clearTimeout(timer); refreshBusy = true; $('refresh').disabled = true;
  try { await poll(); }
  catch (error) {
    state = null; map.setState(null);
    $('source-status').textContent = 'Transit data unavailable';
    $('update-status').textContent = (network ? 'Train updates paused' : 'Published network unavailable') + ' · Retrying every 10 seconds';
    $('status-banner').className = 'status-banner unavailable';
    if (!network) {
      $('map-empty').querySelector('h2').textContent = 'The network is taking a moment';
      $('map-empty').querySelector('p').textContent = 'Transit data is unavailable. The map will appear automatically when the published network is ready.';
      $('departure-status').textContent = 'The rail network is unavailable. Departure search will be enabled when it returns.';
    }
    for (const element of document.querySelectorAll('[data-source-line]')) element.textContent = 'Data unavailable';
    updateTimeline();
  } finally { refreshBusy = false; $('refresh').disabled = false; timer = setTimeout(refresh, 10000); }
}
$('refresh').addEventListener('click', () => { cache.clear(); refresh(); });
$('fit-map').addEventListener('click', () => map.fit());
$('zoom-in').addEventListener('click', () => map.zoom(.8));
$('zoom-out').addEventListener('click', () => map.zoom(1.25));
$('map-type').addEventListener('click', () => { if (!config) return; schematic = !schematic; useLayout(); });
$('collapse-panel').addEventListener('click', () => {
  const collapsed = document.querySelector('.context-panel').classList.toggle('collapsed');
  document.querySelector('.workspace').classList.toggle('panel-collapsed', collapsed);
  $('collapse-panel').textContent = collapsed ? '+' : '−';
  $('collapse-panel').setAttribute('aria-expanded', String(!collapsed));
  $('collapse-panel').setAttribute('aria-label', collapsed ? 'Expand panel' : 'Collapse panel');
  map.fit();
});

$('network-search').addEventListener('input', () => {
  const query = $('network-search').value;
  const results = $('search-results'); results.hidden = !query.trim();
  results.replaceChildren();
  if (results.hidden) return;
  if (!network) { results.append(node('p', 'empty-copy', 'Search will be available when the rail network loads.')); return; }
  const matches = searchNetwork(network, query);
  if (!matches.length) results.append(node('p', 'empty-copy', 'No stations or lines found. Address search and trip planning are not available.'));
  for (const match of matches) {
    const target = network.lines.find(item => item.id === match.lines[0]);
    if (!target) continue;
    const result = button('', 'search-result', () => navigate('/?line=' + encodeURIComponent(target.number)
      + (match.type === 'station' ? '&station=' + encodeURIComponent(match.id) : '')));
    const copy = node('span', '', match.name); copy.append(node('small', '', match.type === 'line' ? 'Rail line' : 'Station · Line ' + target.number));
    result.append(badge(target, true), copy); results.append(result);
  }
});
$('network-search').addEventListener('keydown', event => {
  if (event.key === 'ArrowDown') { event.preventDefault(); $('search-results').querySelector('button')?.focus(); }
  if (event.key === 'Enter') { event.preventDefault(); $('search-results').querySelector('button')?.click(); }
  if (event.key === 'Escape') { $('search-results').hidden = true; }
});
document.addEventListener('keydown', event => {
  if (event.key === '/' && !['INPUT', 'SELECT', 'TEXTAREA'].includes(event.target.tagName) && !$('info-dialog').open) {
    event.preventDefault();
    if (document.querySelector('.context-panel').classList.contains('collapsed')) $('collapse-panel').click();
    $('network-search').focus();
  }
});

function setNow() {
  const now = new Date();
  $('at-time').value = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}
$('now-btn').addEventListener('click', setNow);
$('route').addEventListener('change', () => {
  history.replaceState({}, '', '/search/?line=' + encodeURIComponent($('route').value));
  $('departure-results').replaceChildren();
  $('departure-status').textContent = 'Published schedules, not live arrival predictions.';
  applyLocation();
});
$('time-zone').textContent = '(' + Intl.DateTimeFormat().resolvedOptions().timeZone + ')';
setNow();
function departureCard(record) {
  const payload = record?.payload || {};
  const card = node('article', 'departure-card');
  const target = network?.lines.find(item => item.id === payload.line_id || item.routeId === String(payload.route_id));
  const top = node('div', 'departure-top');
  if (target) top.append(badge(target, true));
  top.append(node('span', 'tag', 'SCHEDULED'), node('strong', '', Number.isFinite(record?.deltaSeconds) ? record.deltaSeconds + ' sec' : 'Time unavailable'));
  const platform = network?.platforms?.[payload.stop_id];
  card.append(top, node('h3', '', network?.stations[platform?.station]?.name || payload.stop_name || 'Station unavailable'));
  const terminal = target && [0, 1].includes(Number(payload.direction_id))
    ? network.stations[Number(payload.direction_id) === 0 ? target.stations.at(-1) : target.stations[0]]?.name : null;
  card.append(node('p', '', (terminal ? 'Toward ' + terminal + ' · ' : '') + (payload.departure_time || 'Departure time unavailable') + ' (Toronto service time)'));
  const details = node('details'); details.append(node('summary', '', 'Schedule record'), node('pre', '', JSON.stringify(payload, null, 2)));
  card.append(details); return card;
}
$('search-form').addEventListener('submit', async event => {
  event.preventDefault();
  const target = $('route').value;
  if (!target) return;
  const at = $('at-time').value ? new Date($('at-time').value) : new Date();
  if (Number.isNaN(at.getTime())) { $('departure-status').textContent = 'Choose a valid departure time.'; return; }
  const id = ++searchRequest;
  $('search-btn').disabled = true; $('departure-results').replaceChildren(); $('departure-status').textContent = 'Searching the published timetable…';
  try {
    const result = await api.departures(target, at.toISOString());
    if (id !== searchRequest) return;
    const matches = Array.isArray(result.matches) ? result.matches.filter(item => item && typeof item === 'object') : [];
    $('departure-status').textContent = matches.length
      ? matches.length + ' scheduled departures across Line ' + target + ' in the two-minute window from ' + clock(result.requestedAt) + ' Toronto. Maximum 200 results.'
      : 'No scheduled departures in this two-minute window.';
    $('departure-results').replaceChildren(...matches.map(departureCard));
  } catch (error) {
    if (id !== searchRequest) return;
    $('departure-status').textContent = error.status === 404 ? 'No scheduled departures in this two-minute window. Try another time.' : 'Departures unavailable. ' + error.message;
  } finally { if (id === searchRequest) $('search-btn').disabled = false; }
});

const dialog = $('info-dialog');
$('close-dialog').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', event => { if (event.target === dialog) {
  const rect = dialog.getBoundingClientRect();
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
} });
document.querySelectorAll('[data-dialog]').forEach(control => control.addEventListener('click', async () => {
  const kind = control.dataset.dialog, content = $('dialog-content');
  content.replaceChildren();
  $('dialog-title').textContent = { about: 'A closer look at your city', alerts: 'Service information', settings: 'Make the map yours' }[kind];
  if (kind === 'about') {
    content.append(node('p', '', 'TTC Map is an independent rail explorer using TTC schedule data from Toronto Open Data and available NTAS observations. It is not an official TTC service.'));
    content.append(node('p', '', 'OpenStreetMap supplies the street background. TTC station coordinates are projected onto it. Route connections and train positions are approximate, not exact track geometry or GPS. Arrows follow the API direction and station order; a round marker means direction is unavailable.'));
    content.append(node('p', '', 'Interchange labels remain visible as you zoom out. Nearby train observations on the same line and direction can share a marker; hover for the count.'));
  } else if (kind === 'alerts') {
    content.append(node('p', '', 'Service alerts and on-time status are not available in this app. A connected data feed does not mean that all lines are running normally.'));
    const health = node('p', '', 'Checking data availability…'); content.append(health);
    const link = node('a', '', 'Visit the official TTC website ↗'); link.href = 'https://www.ttc.ca/'; link.target = '_blank'; link.rel = 'noopener noreferrer'; content.append(link);
    dialog.showModal();
    try {
      const result = await api.health();
      health.textContent = 'Data service: ' + (result.status || 'unknown') + '. Published schedule: ' + (result.gtfs?.ready ? 'ready.' : 'unavailable.');
      for (const [id, info] of Object.entries(result.realtime?.lines || {})) {
        const name = network?.lines.find(item => item.id === id)?.name || id;
        content.append(node('p', '', name + ': ' + (info.source === 'ntas' ? 'live observations' : info.source === 'schedule' ? 'scheduled estimates' : 'data unavailable')));
      }
    } catch { health.textContent = 'Data service diagnostics are temporarily unavailable.'; }
    return;
  } else {
      for (const [key, title] of [['labels', 'Station labels'], ['estimates', 'Show scheduled train estimates'], ['light', 'Light map appearance']]) {
      const label = node('label', 'dialog-setting'); const input = node('input'); input.type = 'checkbox'; input.checked = preferences[key];
      input.addEventListener('change', () => { preferences[key] = input.checked; map.preferences(preferences); document.body.classList.toggle('light-map', preferences.light); });
      label.append(input, document.createTextNode(title)); content.append(label);
    }
    content.append(node('p', '', 'Station labels controls ordinary stops; interchange labels stay visible. Filled arrows show live observations, outlined arrows show scheduled estimates. Appearance settings apply to this session.'));
  }
  dialog.showModal();
}));
applyLocation();
refresh();
