import test from 'node:test';
import assert from 'node:assert';

import { octolinearPoints, pathLength, pointAlongPath } from '../../web/js/geometry.js';

test('horizontal pair stays a single segment', () => {
  const points = octolinearPoints({ x: 0, y: 0 }, { x: 10, y: 0 });
  assert.strictEqual(points.length, 2);
});

test('perfect diagonal stays a single segment', () => {
  const points = octolinearPoints({ x: 0, y: 0 }, { x: 8, y: 8 });
  assert.strictEqual(points.length, 2);
});

test('off-grid pair becomes diagonal then straight', () => {
  const points = octolinearPoints({ x: 0, y: 0 }, { x: 10, y: 4 });
  assert.strictEqual(points.length, 3);
  assert.deepStrictEqual(points[1], { x: 4, y: 4 });
});

test('elbow respects negative directions', () => {
  const points = octolinearPoints({ x: 10, y: 0 }, { x: 0, y: -3 });
  assert.deepStrictEqual(points[1], { x: 7, y: -3 });
});

test('path length sums segments', () => {
  const length = pathLength([{ x: 0, y: 0 }, { x: 3, y: 4 }, { x: 3, y: 14 }]);
  assert.strictEqual(length, 15);
});

test('point at t=0 and t=1 are the endpoints', () => {
  const path = [{ x: 0, y: 0 }, { x: 10, y: 0 }];
  assert.deepStrictEqual(pointAlongPath(path, 0), { x: 0, y: 0, angle: 0 });
  const end = pointAlongPath(path, 1);
  assert.strictEqual(end.x, 10);
});

test('point midway through an elbow lands on the second segment', () => {
  const path = [{ x: 0, y: 0 }, { x: 4, y: 4 }, { x: 4, y: 12 }];
  const point = pointAlongPath(path, 0.75);
  assert.strictEqual(point.x, 4);
  assert.ok(point.y > 4);
  assert.strictEqual(point.angle, 90);
});

test('t outside [0,1] is clamped', () => {
  const path = [{ x: 0, y: 0 }, { x: 10, y: 0 }];
  assert.strictEqual(pointAlongPath(path, -5).x, 0);
  assert.strictEqual(pointAlongPath(path, 5).x, 10);
});

test('single-point path returns the point with zero angle', () => {
  assert.deepStrictEqual(pointAlongPath([{ x: 2, y: 3 }], 0.5), { x: 2, y: 3, angle: 0 });
});
