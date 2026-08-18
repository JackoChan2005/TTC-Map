import test from 'node:test';
import assert from 'node:assert';

import {
  validateNetwork,
  validateLayout,
  validateMapState,
  buildLinePaths,
  buildStationMarkers,
  buildTrainMarkers,
  stationKind
} from '../../web/js/mapModel.js';

const network = validateNetwork({
  lines: [
    { id: 'line-1', name: 'Alpha Line', color: '#D5C82B', stations: ['a', 'b', 'c'] },
    { id: 'line-2', name: 'Beta Line', color: '#008000', stations: ['d', 'b'] }
  ],
  stations: {
    a: { name: 'Alpha', interchange: false, lines: ['line-1'] },
    b: { name: 'Beta', interchange: true, lines: ['line-1', 'line-2'] },
    c: { name: 'Gamma', interchange: false, lines: ['line-1'] },
    d: { name: 'Delta', interchange: false, lines: ['line-2'] }
  }
});

const layout = validateLayout({
  width: 100,
  height: 100,
  stations: {
    a: { x: 0, y: 0 },
    b: { x: 10, y: 10 },
    c: { x: 10, y: 30 },
    d: { x: 0, y: 10 }
  }
});

test('line paths expand off-grid edges into elbows', () => {
  const paths = buildLinePaths(network, layout);
  const line1 = paths.find((p) => p.id === 'line-1');
  assert.deepStrictEqual(line1.points, [
    { x: 0, y: 0 },
    { x: 10, y: 10 },
    { x: 10, y: 30 }
  ]);
});

test('station kinds: interchange beats terminal, terminals are line ends', () => {
  assert.strictEqual(stationKind(network, 'b'), 'interchange');
  assert.strictEqual(stationKind(network, 'a'), 'terminal');
  assert.strictEqual(stationKind(network, 'd'), 'terminal');
});

test('station markers carry position, kind and line colour', () => {
  const markers = buildStationMarkers(network, layout);
  const beta = markers.find((m) => m.id === 'b');
  assert.strictEqual(beta.kind, 'interchange');
  assert.strictEqual(beta.x, 10);
  assert.strictEqual(markers.length, 4);
});

test('train between stations is interpolated along the edge', () => {
  const state = validateMapState({
    generatedAt: 'x',
    source: 'schedule',
    trains: [{ line: 'line-1', at: null, between: ['b', 'c'], progress: 0.5, stationName: 'Gamma' }]
  });
  const markers = buildTrainMarkers(state, network, layout);
  assert.strictEqual(markers.length, 1);
  assert.strictEqual(markers[0].x, 10);
  assert.strictEqual(markers[0].y, 20);
  assert.strictEqual(markers[0].color, '#D5C82B');
});

test('train at a station sits on the station', () => {
  const state = validateMapState({
    source: 'ntas',
    trains: [{ line: 'line-2', at: 'd', between: null, progress: 0, stationName: 'Delta' }]
  });
  const markers = buildTrainMarkers(state, network, layout);
  assert.deepStrictEqual({ x: markers[0].x, y: markers[0].y }, { x: 0, y: 10 });
});

test('validateMapState clamps progress and drops malformed trains', () => {
  const state = validateMapState({
    source: 'ntas',
    trains: [
      { line: 'line-1', at: null, between: ['a', 'b'], progress: 47, stationName: 'ok' },
      { line: 'line-1', at: null, between: null, progress: 0.5 },
      'not an object',
      null
    ]
  });
  assert.strictEqual(state.trains.length, 1);
  assert.strictEqual(state.trains[0].progress, 1);
});

test('validateMapState rejects non-object payloads', () => {
  assert.throws(() => validateMapState(null));
  assert.throws(() => validateMapState('<script>alert(1)</script>'));
});

test('unknown sources are coerced to schedule', () => {
  const state = validateMapState({ source: 'javascript:alert(1)', trains: [] });
  assert.strictEqual(state.source, 'schedule');
});

test('validateNetwork forces malicious colours to the fallback', () => {
  const hostile = validateNetwork({
    lines: [{
      id: 'line-x',
      name: 'X',
      color: 'url(javascript:alert(1))',
      stations: ['a']
    }],
    stations: { a: { name: 'A', lines: ['line-x'] } }
  });
  assert.strictEqual(hostile.lines[0].color, '#1f2937');
});

test('validateNetwork keeps station names as plain strings only', () => {
  const result = validateNetwork({
    lines: [],
    stations: { a: { name: { evil: true }, lines: [] } }
  });
  assert.strictEqual(result.stations.a.name, 'Unknown');
});

test('validateLayout coerces non-finite coordinates to zero', () => {
  const result = validateLayout({ width: 100, height: 100, stations: { a: { x: 'NaN-ish', y: Infinity } } });
  assert.deepStrictEqual(result.stations.a, { x: 0, y: 0 });
});

test('validateNetwork and validateLayout reject junk payloads', () => {
  assert.throws(() => validateNetwork([]));
  assert.throws(() => validateLayout(42));
});

test('trains referencing unknown stations are dropped, not rendered', () => {
  const state = validateMapState({
    source: 'ntas',
    trains: [{ line: 'line-1', at: 'ghost-station', between: null, progress: 0, stationName: 'Ghost' }]
  });
  const markers = buildTrainMarkers(state, network, layout);
  assert.strictEqual(markers.length, 0);
});
