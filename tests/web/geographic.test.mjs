import test from 'node:test';
import assert from 'node:assert/strict';
import { project, WORLD_SIZE, geographicLayout, trainGeometry, detailLevel, visibleTiles, placeLabels } from '../../web/js/geographic.js';
import { validateNetwork } from '../../web/js/mapModel.js';

test('Web Mercator aligns the equator and longitude with standard XYZ tiles', () => {
  assert.deepEqual(project(0, 0), { x: WORLD_SIZE / 2, y: WORLD_SIZE / 2 });
  assert.equal(project(0, -180).x, 0);
  assert.ok(project(43.65, -79.38).y < WORLD_SIZE / 2);
  assert.equal(project(null, -79), null);
  assert.equal(project(91, 0), null);
});
test('API coordinates are retained, missing coordinates cannot become a fabricated origin', () => {
  const n = validateNetwork({ lines: [], stations: { a: { name: 'a', lat: 43.65, lon: -79.38 }, b: { lat: null, lon: 0 } } });
  assert.equal(n.stations.a.lat, 43.65);
  assert.equal(n.stations.b.lat, null);
  assert.equal(geographicLayout(n), null);
  delete n.stations.b;
  const layout = geographicLayout(n), projected = project(43.65, -79.38);
  assert.equal(layout.stations.a.x + layout.originX, projected.x);
  assert.equal(layout.stations.a.y + layout.originY, projected.y);
});
const network = { lines: [{ id: 'line-1', stations: ['a', 'b', 'c'] }], stations: { a: { name: 'A' }, c: { name: 'C' } } };
const layout = { stations: { a: { x: 0, y: 0 }, b: { x: 100, y: 0 }, c: { x: 100, y: 100 } } };
test('arrows follow both API directions between stations without changing positions', () => {
  const a = trainGeometry({ line: 'line-1', direction: 0, between: ['a', 'b'], progress: .25 }, network, layout, true);
  const b = trainGeometry({ line: 'line-1', direction: 1, between: ['b', 'a'], progress: .75 }, network, layout, true);
  assert.equal(a.x, b.x);
  assert.equal(a.angle, 0);
  assert.equal(b.angle, 180);
});
test('at-station arrows use the correct route tangent, including incoming terminal tangent', () => {
  assert.equal(trainGeometry({ line: 'line-1', direction: 0, at: 'b' }, network, layout, true).angle, 90);
  assert.equal(trainGeometry({ line: 'line-1', direction: 1, at: 'b' }, network, layout, true).angle, 180);
  assert.equal(trainGeometry({ line: 'line-1', direction: 0, at: 'c' }, network, layout, true).angle, 90);
});
test('missing or inconsistent direction has a neutral fallback', () => {
  assert.equal(trainGeometry({ line: 'line-1', at: 'a' }, network, layout, true).angle, null);
  assert.equal(trainGeometry({ line: 'line-1', direction: 1, between: ['a', 'b'], progress: .5 }, network, layout, true).angle, null);
  assert.equal(trainGeometry({ line: 'unknown', at: 'a' }, network, layout, true), null);
});
test('progressive detail uses defined geographic zoom thresholds', () => {
  assert.deepEqual([9, 11, 12.5, 14].map(detailLevel), ['wide', 'network', 'local', 'detail']);
});
test('tile requests are bounded to the visible viewport', () => {
  const tiles = visibleTiles({ originX: 256, originY: 256 }, { x: 0, y: 0, w: 255, h: 255 }, 1);
  assert.equal(tiles.length, 1);
  assert.equal(tiles[0].key, '12/1/1');
});
test('crowded transfers take priority and labels never overlap', () => {
  const items = Array.from({ length: 9 }, (_, id) => ({ id, x: 100, y: 60, width: 75, interchange: true, priority: 0 }));
  items.unshift({ id: 'ordinary', x: 100, y: 60, width: 120, priority: 100, interchange: false });
  const placed = placeLabels(items, { x: 0, y: 0, w: 250, h: 140 });
  assert.equal(placed.filter(item => item.interchange).length, 9);
  for (let i = 0; i < placed.length; i++) for (let j = i + 1; j < placed.length; j++) {
    const a = placed[i], b = placed[j];
    assert.ok(a.x + a.w <= b.x || b.x + b.w <= a.x || a.y + a.h <= b.y || b.y + b.h <= a.y);
  }
});
