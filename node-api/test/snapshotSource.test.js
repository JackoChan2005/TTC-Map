const test = require('node:test');
const assert = require('node:assert');

const { snapshotIsUsable } = require('../src/map/sources/snapshotSource');

const NOW = Date.parse('2026-07-02T12:00:00.000Z');
const MAX_AGE_MS = 90_000;

const snapshotAt = (isoTime, status = 'ok') => ({
  polledAt: isoTime,
  status,
  positions: []
});

test('fresh ok snapshot is usable', () => {
  const snapshot = snapshotAt('2026-07-02T11:59:30.000Z');
  assert.strictEqual(snapshotIsUsable(snapshot, NOW, MAX_AGE_MS), true);
});

test('snapshot at exactly max age is still usable', () => {
  const snapshot = snapshotAt('2026-07-02T11:58:30.000Z');
  assert.strictEqual(snapshotIsUsable(snapshot, NOW, MAX_AGE_MS), true);
});

test('stale snapshot is rejected even when status is ok', () => {
  const snapshot = snapshotAt('2026-07-02T11:58:29.000Z');
  assert.strictEqual(snapshotIsUsable(snapshot, NOW, MAX_AGE_MS), false);
});

test('error snapshot is rejected immediately regardless of age', () => {
  const snapshot = snapshotAt('2026-07-02T11:59:59.000Z', 'error');
  assert.strictEqual(snapshotIsUsable(snapshot, NOW, MAX_AGE_MS), false);
});

test('missing snapshot is rejected', () => {
  assert.strictEqual(snapshotIsUsable(null, NOW, MAX_AGE_MS), false);
});

test('unparseable polled_at is rejected', () => {
  const snapshot = snapshotAt('not-a-date');
  assert.strictEqual(snapshotIsUsable(snapshot, NOW, MAX_AGE_MS), false);
});
