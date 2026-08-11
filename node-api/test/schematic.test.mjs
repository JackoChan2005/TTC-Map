import test from 'node:test';
import assert from 'node:assert';

import {
  quantizeDirection,
  buildSchematicPositions,
  fitToCanvas,
  buildSchematicLayout
} from '../scripts/lib/schematic.mjs';

test('quantizeDirection snaps to the 8 compass directions', () => {
  assert.deepStrictEqual(quantizeDirection(10, 0), [1, 0]);
  assert.deepStrictEqual(quantizeDirection(10, 9), [1, 1]);
  assert.deepStrictEqual(quantizeDirection(0, -10), [0, -1]);
  assert.deepStrictEqual(quantizeDirection(-10, 1), [-1, 0]);
  assert.deepStrictEqual(quantizeDirection(-7, -7), [-1, -1]);
});

const network = {
  lines: [
    { id: 'line-1', stations: ['a', 'b', 'c'] },
    { id: 'line-2', stations: ['d', 'b', 'e'] }
  ]
};

const geo = {
  stations: {
    a: { x: 0, y: 0 },
    b: { x: 0, y: 100 },
    c: { x: 0, y: 200 },
    d: { x: -100, y: 100 },
    e: { x: 100, y: 100 }
  }
};

test('every station gets a position and edges are unit octolinear steps', () => {
  const positions = buildSchematicPositions(network, geo);
  assert.strictEqual(Object.keys(positions).length, 5);

  const [ax, ay] = positions.a;
  const [bx, by] = positions.b;
  assert.ok(Math.abs(bx - ax) <= 1 && Math.abs(by - ay) <= 1);
});

test('shared stations anchor later lines instead of being re-placed', () => {
  const positions = buildSchematicPositions(network, geo);
  const [dx] = positions.d;
  const [bx] = positions.b;
  const [ex] = positions.e;
  assert.ok(dx < bx && bx < ex, 'line 2 extends west and east of the shared anchor');
});

test('no two stations occupy the same cell', () => {
  const positions = buildSchematicPositions(network, geo);
  const cells = new Set(Object.values(positions).map(([x, y]) => `${x},${y}`));
  assert.strictEqual(cells.size, Object.keys(positions).length);
});

test('fitToCanvas scales into the requested width with margins', () => {
  const layout = fitToCanvas({ a: [0, 0], b: [4, 2] }, { width: 1000, margin: 40 });
  assert.strictEqual(layout.stations.a.x, 40);
  assert.strictEqual(layout.stations.b.x, 960);
  assert.ok(layout.height > 0);
});

test('end-to-end layout has the schematic name and all stations', () => {
  const layout = buildSchematicLayout(network, geo);
  assert.strictEqual(layout.name, 'schematic');
  assert.strictEqual(Object.keys(layout.stations).length, 5);
});
