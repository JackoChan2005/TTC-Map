import test from 'node:test';
import assert from 'node:assert';

import {
  validateNetwork,
  validateLayout,
  validateMapState
} from '../../web/js/mapModel.js';

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
