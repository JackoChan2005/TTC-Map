// Train positions from the NTAS snapshot that rtRecorder maintains in the
// realtime database. Throws when the snapshot is failed, missing or stale so
// the caller falls back — one failed poll means no realtime data is served.

const db = require('../../db');

const DEFAULT_MAX_AGE_MS = 90_000;

const getMaxAgeMs = () => Number(process.env.RT_SNAPSHOT_MAX_AGE_MS || DEFAULT_MAX_AGE_MS);

// pure; exported for tests
const snapshotIsUsable = (snapshot, nowMs = Date.now(), maxAgeMs = getMaxAgeMs()) => {
  if (!snapshot || snapshot.status !== 'ok') {
    return false;
  }
  const polledAtMs = Date.parse(snapshot.polledAt);
  if (Number.isNaN(polledAtMs)) {
    return false;
  }
  return nowMs - polledAtMs <= maxAgeMs;
};

const readSnapshot = async () => {
  const row = await db.rt.get('SELECT polled_at, status, positions FROM rt_snapshot WHERE id = 1');
  if (!row) {
    return null;
  }

  let positions = [];
  try {
    positions = JSON.parse(row.positions);
  } catch (_error) {
    return { polledAt: row.polled_at, status: 'error', positions: [] };
  }

  return { polledAt: row.polled_at, status: row.status, positions };
};

const getTrainPositions = async (now = new Date()) => {
  const snapshot = await readSnapshot();
  if (!snapshotIsUsable(snapshot, now.getTime())) {
    throw new Error('realtime snapshot unavailable (failed, missing or stale)');
  }
  return snapshot.positions;
};

module.exports = {
  name: 'snapshot',
  getTrainPositions,
  snapshotIsUsable
};
