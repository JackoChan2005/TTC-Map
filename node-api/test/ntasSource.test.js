const test = require('node:test');
const assert = require('node:assert');

const { positionsFromResponses } = require('../src/map/sources/ntasSource');

const topology = {
  lines: [{ id: 'line-2', stations: ['a', 'b', 'c'] }],
  stations: {
    a: { name: 'Alpha' },
    b: { name: 'Beta' },
    c: { name: 'Gamma' }
  },
  platforms: {
    p1: { station: 'b', line: 'line-2', direction: 0 },
    p2: { station: 'a', line: 'line-2', direction: 0 }
  }
};

test('train arriving within threshold is placed approaching the station', () => {
  const positions = positionsFromResponses(topology, [
    { platformId: 'p1', entries: [{ line: '2', direction: '0', nextTrains: '1, 4, 7' }] }
  ]);
  assert.strictEqual(positions.length, 1);
  assert.strictEqual(positions[0].from, 'a');
  assert.strictEqual(positions[0].to, 'b');
});

test('train far away is ignored', () => {
  const positions = positionsFromResponses(topology, [
    { platformId: 'p1', entries: [{ line: '2', direction: '0', nextTrains: '5, 9' }] }
  ]);
  assert.strictEqual(positions.length, 0);
});

test('terminal station with no previous stop reports at-station', () => {
  const positions = positionsFromResponses(topology, [
    { platformId: 'p2', entries: [{ line: '2', direction: '0', nextTrains: '0' }] }
  ]);
  assert.strictEqual(positions[0].from, 'a');
  assert.strictEqual(positions[0].to, null);
});

test('malformed nextTrains and unknown platforms are skipped', () => {
  const positions = positionsFromResponses(topology, [
    { platformId: 'p1', entries: [{ line: '2', direction: '0', nextTrains: '' }] },
    { platformId: 'unknown', entries: [{ line: '2', direction: '0', nextTrains: '0' }] }
  ]);
  assert.strictEqual(positions.length, 0);
});
