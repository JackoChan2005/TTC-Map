import { octolinearPoints } from '../geometry.js';
import { detailLevel, zoomLevel, trainGeometry, visibleTiles, placeLabels } from '../geographic.js';

const el = (tag, attributes = {}, text) => {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  return node;
};

export function createExplorerMap(svg, onStation, onBasemap = () => {}) {
  let network, layout, state, selectedLine, selectedStation, geographic = true;
  let labels = true, estimates = true, box = { x: 0, y: 0, w: 1000, h: 700 };
  let drag = null, moved = false, frame = null;
  const tileLayer = el('g', { class: 'basemap-tiles', 'aria-hidden': 'true' });
  const vectorLayer = el('g', { class: 'transit-overlay' });
  svg.replaceChildren(tileLayer, vectorLayer);
  const tiles = new Map();
  const measure = document.createElement('canvas').getContext('2d');
  measure.font = '11px "Segoe UI", Arial, sans-serif';
  const size = () => ({ w: Math.max(svg.clientWidth, 1), h: Math.max(svg.clientHeight, 1) });
  const point = id => layout?.stations[id];
  const segment = (a, b) => geographic ? [a, b] : octolinearPoints(a, b);
  const area = () => {
    const { w, h } = size();
    const panel = document.querySelector('.context-panel')?.getBoundingClientRect();
    const collapsed = panel?.height < 110;
    const mobile = w <= 700;
    const x = mobile || collapsed ? 14 : (panel?.right || 400) + 24;
    const y = mobile ? 104 : 128;
    const right = w - (mobile ? 58 : 72);
    const bottom = mobile ? (panel?.top || h) - 66 : h - 100;
    return { x, y, w: Math.max(120, right - x), h: Math.max(95, bottom - y), mobile, collapsed };
  };

  function fit(ids = selectedLine?.stations) {
    if (!layout) return;
    const points = (ids || Object.keys(layout.stations)).map(point).filter(Boolean);
    if (!points.length) return;
    const xs = points.map(p => p.x), ys = points.map(p => p.y), a = area(), s = size();
    const unit = Math.max(Math.max(120, Math.max(...xs) - Math.min(...xs)) * 1.14 / a.w,
      Math.max(120, Math.max(...ys) - Math.min(...ys)) * 1.14 / a.h);
    box = { x: (Math.min(...xs) + Math.max(...xs)) / 2 - (a.x + a.w / 2) * unit,
      y: (Math.min(...ys) + Math.max(...ys)) / 2 - (a.y + a.h / 2) * unit, w: unit * s.w, h: unit * s.h };
    render();
  }

  function tileStatus() {
    if (!geographic) { onBasemap('schematic'); return; }
    const values = [...tiles.values()];
    onBasemap(values.some(tile => tile.failed) ? 'unavailable'
      : values.length && values.every(tile => tile.loaded) ? 'ready' : 'loading');
  }
  function syncTiles(unit) {
    tileLayer.style.display = geographic ? '' : 'none';
    if (!geographic) { tileStatus(); return; }
    const visible = visibleTiles(layout, box, unit);
    const keys = new Set(visible.map(tile => tile.key));
    for (const [key, tile] of tiles) if (!keys.has(key)) { tile.node.remove(); tiles.delete(key); }
    for (const tile of visible) {
      let entry = tiles.get(tile.key);
      if (!entry) {
        const image = el('image', { x: tile.x, y: tile.y, width: tile.size, height: tile.size,
          preserveAspectRatio: 'none', visibility: 'hidden', 'data-tile': tile.key });
        entry = { node: image, loaded: false, failed: false, failedAt: 0 };
        const current = entry;
        image.addEventListener('load', () => {
          current.loaded = true; current.failed = false; image.setAttribute('visibility', 'visible');
          image.dataset.loaded = 'true'; tileStatus();
        });
        image.addEventListener('error', () => { current.failed = true; current.failedAt = Date.now(); tileStatus(); });
        tiles.set(tile.key, entry); tileLayer.append(image);
        // Normal browser image loading honours the provider's cache headers.
        // Only visible tiles are requested: no offline downloads or prefetch.
        image.setAttribute('href', 'https://tile.openstreetmap.org/' + tile.key + '.png');
      } else if (entry.failed && Date.now() - entry.failedAt > 30000) {
        entry.failedAt = Date.now();
        entry.node.setAttribute('href', 'https://tile.openstreetmap.org/' + tile.key + '.png');
      }
      entry.node.setAttribute('x', tile.x); entry.node.setAttribute('y', tile.y);
      entry.node.setAttribute('width', tile.size); entry.node.setAttribute('height', tile.size);
    }
    tileStatus();
  }

  function render() {
    if (!network || !layout) return;
    const s = size(), unit = box.w / s.w, a = area();
    const zoom = geographic ? zoomLevel(unit) : 12 - Math.log2(unit);
    const level = detailLevel(zoom);
    const stationRadius = Math.max(2.6, Math.min(4.5, 3.2 + (zoom - 12) * .35));
    const trainSize = Math.max(3.8, Math.min(6.5, 4.6 + (zoom - 12) * .35));
    svg.setAttribute('viewBox', `${box.x} ${box.y} ${box.w} ${box.h}`);
    svg.dataset.detail = level;
    svg.dataset.zoom = zoom.toFixed(2);
    syncTiles(unit);
    const root = el('g');
    for (const line of network.lines) {
      const paths = [];
      for (let i = 1; i < line.stations.length; i++) {
        const start = point(line.stations[i - 1]), end = point(line.stations[i]);
        if (start && end) paths.push('M' + segment(start, end).map(p => p.x + ',' + p.y).join(' L'));
      }
      const group = el('g', { class: selectedLine && line.id !== selectedLine.id ? 'dimmed' : '', 'data-line': line.id });
      const attrs = { d: paths.join(' '), stroke: line.color };
      group.append(el('path', { ...attrs, class: 'line-path line-casing', stroke: '#102029' }),
        el('path', { ...attrs, class: 'line-path' }));
      root.append(group);
    }

    const labelCandidates = [], stationNodes = new Map();
    const terminals = new Set(network.lines.flatMap(line => [line.stations[0], line.stations.at(-1)]));
    for (const [id, station] of Object.entries(network.stations)) {
      const p = point(id);
      if (!p) continue;
      const interchange = station.lines.length > 1;
      const active = !selectedLine || selectedLine.stations.includes(id);
      if (level === 'wide' && !interchange) continue;
      if (level === 'network' && !interchange && !terminals.has(id) && id !== selectedStation) continue;
      const x = (p.x - box.x) / unit, y = (p.y - box.y) / unit;
      if (x < -15 || y < -15 || x > s.w + 15 || y > s.h + 15) continue;
      const group = el('g', { class: 'map-station' + (!active && !interchange ? ' dimmed' : ''),
        role: 'button', tabindex: active || interchange ? 0 : -1, 'aria-label': station.name,
        'data-station': id, 'data-interchange': String(interchange) });
      group.append(el('title', {}, station.name));
      const lines = station.lines.map(id => network.lines.find(line => line.id === id)).filter(Boolean);
      const radius = (interchange ? stationRadius + 2 : stationRadius) * unit;
      if (id === selectedStation) group.append(el('circle', { cx: p.x, cy: p.y, r: radius + 4 * unit, class: 'station-selection' }));
      const dot = el('circle', { cx: p.x, cy: p.y, r: radius, class: 'station-dot' });
      dot.style.setProperty('--station-color', lines[0]?.color || '#b9c8ce');
      group.append(dot);
      if (interchange) lines.forEach((line, i) => {
        const circumference = 2 * Math.PI * radius;
        group.append(el('circle', { cx: p.x, cy: p.y, r: radius, fill: 'none', stroke: line.color,
          'stroke-width': 2.5 * unit, 'stroke-dasharray': circumference / lines.length + ' ' + circumference,
          'stroke-dashoffset': -i * circumference / lines.length, transform: `rotate(-90 ${p.x} ${p.y})`,
          class: 'transfer-ring' }));
      });
      group.append(el('circle', { cx: p.x, cy: p.y, r: 10 * unit, fill: 'transparent' }));
      group.addEventListener('click', () => { if (!moved) onStation(id); });
      group.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); event.stopPropagation(); onStation(id); }
      });
      root.append(group); stationNodes.set(id, group);
      const inArea = x >= a.x && y >= a.y && x <= a.x + a.w && y <= a.y + a.h;
      const showLabel = interchange || labels && active && (level === 'detail' || id === selectedStation || terminals.has(id));
      if (inArea && showLabel) {
        const text = station.name + (level === 'detail' ? ' · ' + lines.map(line => line.number).join('/') : '');
        labelCandidates.push({ id, text, x, y, interchange, priority: (id === selectedStation ? 100 : 0) + (terminals.has(id) ? 10 : 0),
          width: measure.measureText(text).width + 5 });
      }
    }
    // At local scale regular names are considered, after terminals/transfers.
    if (labels && level === 'local') for (const [id, group] of stationNodes) {
      if (labelCandidates.some(item => item.id === id)) continue;
      const station = network.stations[id], p = point(id);
      if (selectedLine && !selectedLine.stations.includes(id)) continue;
      const x = (p.x - box.x) / unit, y = (p.y - box.y) / unit;
      if (x >= a.x && y >= a.y && x <= a.x + a.w && y <= a.y + a.h)
        labelCandidates.push({ id, text: station.name, x, y, interchange: false, priority: 0, width: measure.measureText(station.name).width + 5 });
    }
    const labelLayer = el('g', { class: 'station-labels' });
    for (const label of placeLabels(labelCandidates, a)) {
      const x = box.x + label.x * unit, y = box.y + label.y * unit;
      const px = box.x + label.stationX * unit, py = box.y + label.stationY * unit;
      const endX = box.x + Math.max(label.x, Math.min(label.x + label.w, label.stationX)) * unit;
      if (Math.hypot(label.x - label.stationX, label.y - label.stationY) > 22)
        labelLayer.append(el('path', { d: `M${px},${py} L${endX},${y + 7 * unit}`, class: 'label-leader' }));
      const text = el('text', { x, y: y + 11 * unit, 'font-size': 11 * unit, class: 'station-label',
        'data-label-station': label.id, 'data-interchange': String(label.interchange) }, label.text);
      labelLayer.append(text);
    }

    const trainGroups = new Map();
    for (const train of state?.trains || []) {
      if (selectedLine && train.line !== selectedLine.id) continue;
      const live = state.lineSources[train.line]?.source === 'ntas';
      if (!live && !estimates) continue;
      const p = trainGeometry(train, network, layout, geographic);
      if (!p) continue;
      const x = (p.x - box.x) / unit, y = (p.y - box.y) / unit;
      if (x < 0 || y < 0 || x > s.w || y > s.h) continue;
      // Co-located observations on the same line/direction share a marker.
      // Positions are not moved or invented to manufacture visual separation.
      const key = [train.line, train.direction, live, Math.round(x / (trainSize * 1.7)), Math.round(y / (trainSize * 1.7))].join(':');
      if (trainGroups.has(key)) { trainGroups.get(key).count++; continue; }
      trainGroups.set(key, { p, train, live, count: 1 });
    }
    for (const { p, train, live, count } of trainGroups.values()) {
      const marker = el('g', { transform: `translate(${p.x} ${p.y})`, class: 'train-marker' + (live ? '' : ' estimate'),
        'data-line': train.line, 'data-direction': train.direction ?? 'unknown', 'data-angle': p.angle ?? '',
        'data-count': count, role: 'img' });
      const caption = `${p.line.name} · ${live ? 'Live observation' : 'Scheduled estimate'} · ${p.angle === null ? 'Direction unavailable' : 'Toward ' + p.terminal}${count > 1 ? ' · ' + count + ' overlapping observations' : ''}`;
      marker.setAttribute('aria-label', caption);
      marker.append(el('title', {}, caption));
      const glyph = p.angle === null
        ? el('circle', { r: trainSize * unit })
        : el('path', { d: 'M 1.25 0 L -1 -.85 L -.55 0 L -1 .85 Z', transform: `rotate(${p.angle}) translate(0 ${3.5 * unit}) scale(${trainSize * unit})` });
      glyph.setAttribute('fill', live ? p.line.color : '#172b35');
      glyph.setAttribute('stroke', live ? '#ffffff' : p.line.color);
      glyph.setAttribute('stroke-width', p.angle === null ? 1.2 * unit : 1);
      if (p.angle !== null) glyph.setAttribute('vector-effect', 'non-scaling-stroke');
      glyph.setAttribute('class', 'train-glyph');
      if (!live) glyph.setAttribute('stroke-dasharray', p.angle === null ? 2 * unit + ' ' + unit : '2 1');
      marker.append(glyph);
      root.append(marker);
    }
    root.append(labelLayer);
    const focused = document.activeElement?.getAttribute('data-station');
    vectorLayer.replaceChildren(root);
    if (focused) Array.from(svg.querySelectorAll('[data-station]')).find(node => node.dataset.station === focused)?.focus({ preventScroll: true });
  }

  function zoom(factor, anchor) {
    if (!layout) return;
    const s = size(), a = area();
    const center = anchor || { x: a.x + a.w / 2, y: a.y + a.h / 2 };
    const old = box.w / s.w;
    const unit = Math.min(16, Math.max(.07, old * factor));
    box = { x: box.x + center.x * (old - unit), y: box.y + center.y * (old - unit), w: unit * s.w, h: unit * s.h };
    render();
  }
  svg.addEventListener('wheel', event => {
    event.preventDefault();
    const rect = svg.getBoundingClientRect();
    zoom(event.deltaY > 0 ? 1.15 : 1 / 1.15, { x: event.clientX - rect.left, y: event.clientY - rect.top });
  }, { passive: false });
  svg.addEventListener('pointerdown', event => {
    if (!layout || event.button !== 0) return;
    moved = false; drag = { x: event.clientX, y: event.clientY, box: { ...box } };
  });
  svg.addEventListener('pointermove', event => {
    if (!drag) return;
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) < 4) return;
    moved = true; svg.setPointerCapture(event.pointerId);
    const unit = box.w / size().w;
    box.x = drag.box.x - dx * unit; box.y = drag.box.y - dy * unit;
    if (!frame) frame = requestAnimationFrame(() => { frame = null; render(); });
  });
  const endDrag = () => { drag = null; };
  svg.addEventListener('pointerup', endDrag);
  window.addEventListener('pointerup', endDrag);
  svg.addEventListener('pointercancel', endDrag);
  svg.addEventListener('lostpointercapture', endDrag);
  svg.addEventListener('keydown', event => {
    if (event.target !== svg) return;
    const shifts = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    if (shifts[event.key]) {
      event.preventDefault(); const [x, y] = shifts[event.key]; box.x += x * box.w / 8; box.y += y * box.h / 8; render();
    } else if (['+', '=', '-'].includes(event.key)) { event.preventDefault(); zoom(event.key === '-' ? 1.25 : .8); }
  });
  new ResizeObserver(() => { if (layout) fit(); }).observe(svg);
  return {
    setConfig(n, l, geo) { network = n; layout = l; geographic = geo; fit(); },
    setState(s) { state = s; render(); },
    select(line, station, refit = true) { selectedLine = line; selectedStation = station; refit ? fit() : render(); },
    preferences(options) { labels = options.labels; estimates = options.estimates; render(); },
    fit: () => fit(), zoom
  };
}
