const test = require('node:test');
const assert = require('node:assert');

const { computeMapState } = require('../src/map/stateEngine');

const topology = {
  lines: [{ id: 'line-1', stations: ['a', 'b', 'c'] }],
  stations: {
    a: { name: 'Alpha' },
    b: { name: 'Beta' },
    c: { name: 'Gamma' }
  },
  platforms: {}
};

test('low progress snaps to the departure station', () => {
  const state = computeMapState(topology, [
    { line: 'line-1', direction: 0, from: 'a', to: 'b', progress: 0.1 }
  ]);
  assert.strictEqual(state.trains[0].at, 'a');
  assert.strictEqual(state.trains[0].between, null);
  assert.deepStrictEqual(state.stationsWithTrains, { a: 1 });
});

test('high progress snaps to the arrival station', () => {
  const state = computeMapState(topology, [
    { line: 'line-1', direction: 0, from: 'a', to: 'b', progress: 0.95 }
  ]);
  assert.strictEqual(state.trains[0].at, 'b');
  assert.strictEqual(state.trains[0].stationName, 'Beta');
});

test('mid progress stays between with nearest station counted', () => {
  const state = computeMapState(topology, [
    { line: 'line-1', direction: 0, from: 'a', to: 'b', progress: 0.6 }
  ]);
  assert.strictEqual(state.trains[0].at, null);
  assert.deepStrictEqual(state.trains[0].between, ['a', 'b']);
  assert.deepStrictEqual(state.stationsWithTrains, { b: 1 });
});

test('positions at unknown stations are dropped', () => {
  const state = computeMapState(topology, [
    { line: 'line-1', direction: 0, from: 'nope', to: 'b', progress: 0.5 }
  ]);
  assert.strictEqual(state.trainCount, 0);
});

test('to=null means at the from station', () => {
  const state = computeMapState(topology, [
    { line: 'line-1', direction: 1, from: 'c', to: null, progress: 0 }
  ]);
  assert.strictEqual(state.trains[0].at, 'c');
});
