// Polls NTAS on a fixed cadence and keeps exactly one snapshot row in the
// realtime database. sources/snapshotSource.js is the read side: a single
// failed poll marks the snapshot 'error', so serving falls back to the
// schedule simulation immediately — stale realtime positions are never shown.

const db = require('../db');
const ntasSource = require('./sources/ntasSource');

const DEFAULT_POLL_MS = 30_000;

const getPollMs = () => Number(process.env.NTAS_POLL_MS || DEFAULT_POLL_MS);

const writeSnapshot = ({ status, positions }) => db.rt.run(`
  INSERT INTO rt_snapshot (id, polled_at, status, positions)
  VALUES (1, ?, ?, ?)
  ON CONFLICT(id) DO UPDATE SET
    polled_at = excluded.polled_at,
    status = excluded.status,
    positions = excluded.positions
`, [new Date().toISOString(), status, JSON.stringify(positions ?? [])]);

const pollOnce = async () => {
  try {
    const positions = await ntasSource.getTrainPositions();
    await writeSnapshot({ status: 'ok', positions });
    return { status: 'ok', trainCount: positions.length };
  } catch (error) {
    try {
      await writeSnapshot({ status: 'error', positions: [] });
    } catch (writeError) {
      console.error('Failed to record NTAS poll failure:', writeError.message);
    }
    return { status: 'error', message: error.message };
  }
};

let timer = null;

const start = () => {
  if (timer) {
    return timer;
  }

  const logResult = (result) => {
    if (result.status === 'error') {
      console.error(`NTAS poll failed (${result.message}); map falls back to schedule`);
    }
  };

  pollOnce().then((result) => {
    if (result.status === 'ok') {
      console.log(`NTAS recorder started (${result.trainCount} trains, polling every ${Math.floor(getPollMs() / 1000)}s)`);
    } else {
      logResult(result);
    }
  });

  timer = setInterval(() => {
    pollOnce().then(logResult);
  }, getPollMs());
  return timer;
};

const stop = () => {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
};

module.exports = {
  start,
  stop,
  pollOnce
};
