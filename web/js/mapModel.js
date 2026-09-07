// View models for the schematic map, plus validation of API responses.
// Everything from the network is treated as untrusted input: fields are
// type-checked, numbers coerced and clamped, and bad entries dropped
// before any of it reaches the DOM. Pure functions, no DOM.

import { octolinearPoints, pointAlongPath } from './geometry.js';

const FALLBACK_COLOR = '#1f2937';
const COLOR_PATTERN = /^#[0-9a-fA-F]{6}$/;

const asString = (value) => (typeof value === 'string' ? value : '');

const asColor = (value) => (COLOR_PATTERN.test(asString(value)) ? value : FALLBACK_COLOR);

const asFiniteNumber = (value, fallback = 0) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
};

export const validateNetwork = (raw) => {
  if (!raw || typeof raw !== 'object' || !Array.isArray(raw.lines) || typeof raw.stations !== 'object') {
    throw new Error('Invalid network payload');
  }

  const stations = {};
  for (const [id, station] of Object.entries(raw.stations)) {
    if (!station || typeof station !== 'object') {
      continue;
    }
    stations[id] = {
      name: asString(station.name) || 'Unknown',
      interchange: station.interchange === true,
      lines: Array.isArray(station.lines) ? station.lines.map(asString) : []
    };
  }

  const lines = raw.lines
    .filter((line) => line && typeof line === 'object' && Array.isArray(line.stations))
    .map((line) => ({
      id: asString(line.id),
      name: asString(line.name) || 'Line',
      color: asColor(line.color),
      stations: line.stations.map(asString).filter((s) => stations[s])
    }));

  return { lines, stations };
};

export const validateLayout = (raw) => {
  if (!raw || typeof raw !== 'object' || typeof raw.stations !== 'object') {
    throw new Error('Invalid layout payload');
  }

  const stations = {};
  for (const [id, point] of Object.entries(raw.stations)) {
    if (!point || typeof point !== 'object') {
      continue;
    }
    stations[id] = { x: asFiniteNumber(point.x), y: asFiniteNumber(point.y) };
  }

  return {
    width: Math.max(asFiniteNumber(raw.width, 1000), 1),
    height: Math.max(asFiniteNumber(raw.height, 600), 1),
    stations
  };
};

export const validateMapState = (raw) => {
  if (!raw || typeof raw !== 'object') {
    throw new Error('Invalid map state payload');
  }

  const trains = (Array.isArray(raw.trains) ? raw.trains : [])
    .filter((train) => train && typeof train === 'object')
    .map((train) => ({
      line: asString(train.line),
      at: train.at === null || train.at === undefined ? null : asString(train.at),
      between: Array.isArray(train.between) && train.between.length === 2
        ? [asString(train.between[0]), asString(train.between[1])]
        : null,
      progress: Math.min(Math.max(asFiniteNumber(train.progress), 0), 1),
      stationName: asString(train.stationName)
    }))
    .filter((train) => train.at !== null || train.between !== null);

  return {
    generatedAt: asString(raw.generatedAt),
    source: ['ntas', 'mixed'].includes(raw.source) ? raw.source : 'schedule',
    generation: asString(raw.generation),
    lineSources: Object.fromEntries(Object.entries(raw.lineSources || {}).filter(
      ([key, value]) => /^line-[12456]$/.test(key) && value && typeof value === 'object'
    ).map(([key, value]) => [key, {
      source: ['ntas', 'schedule'].includes(value.source) ? value.source : null,
      reason: asString(value.reason)
    }])),
    fallback: raw.fallback === true,
    trains
  };
};

const positionOf = (layout, stationId) => layout.stations[stationId] || null;

// One polyline per line, edges expanded to octolinear segments.
export const buildLinePaths = (network, layout) => network.lines.map((line) => {
  const points = [];
  for (let i = 1; i < line.stations.length; i += 1) {
    const a = positionOf(layout, line.stations[i - 1]);
    const b = positionOf(layout, line.stations[i]);
    if (!a || !b) {
      continue;
    }
    const segment = octolinearPoints(a, b);
    for (const point of points.length === 0 ? segment : segment.slice(1)) {
      points.push(point);
    }
  }
  return { id: line.id, color: line.color, name: line.name, points };
});

const KIND_INTERCHANGE = 'interchange';
const KIND_TERMINAL = 'terminal';
const KIND_REGULAR = 'regular';

export const stationKind = (network, stationId) => {
  if (network.stations[stationId]?.interchange) {
    return KIND_INTERCHANGE;
  }
  for (const line of network.lines) {
    if (line.stations[0] === stationId || line.stations[line.stations.length - 1] === stationId) {
      return KIND_TERMINAL;
    }
  }
  return KIND_REGULAR;
};

export const buildStationMarkers = (network, layout) => Object.entries(network.stations)
  .map(([id, station]) => {
    const position = positionOf(layout, id);
    if (!position) {
      return null;
    }
    const line = network.lines.find((l) => l.id === station.lines[0]);
    return {
      id,
      name: station.name,
      x: position.x,
      y: position.y,
      kind: stationKind(network, id),
      color: line ? line.color : FALLBACK_COLOR
    };
  })
  .filter(Boolean);

export const buildTrainMarkers = (state, network, layout) => state.trains
  .map((train) => {
    const line = network.lines.find((l) => l.id === train.line);
    const color = line ? line.color : FALLBACK_COLOR;

    if (train.at) {
      const position = positionOf(layout, train.at);
      return position
        ? { x: position.x, y: position.y, angle: 0, color, label: train.stationName }
        : null;
    }

    const a = positionOf(layout, train.between[0]);
    const b = positionOf(layout, train.between[1]);
    if (!a || !b) {
      return null;
    }
    const point = pointAlongPath(octolinearPoints(a, b), train.progress);
    return { x: point.x, y: point.y, angle: point.angle, color, label: train.stationName };
  })
  .filter(Boolean);
