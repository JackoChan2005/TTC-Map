// Two databases, split by ownership:
//   gtfs — the Python-owned static GTFS database (SubwaySystem.db). Node only
//          ever reads it; the Python updater is its single writer.
//   rt   — Node's own database (realtime.db) for everything dynamic: the
//          realtime snapshot, synced_records, sync_runs and meta.

const fs = require('fs');
const path = require('path');
const sqlite3 = require('sqlite3').verbose();

const BUSY_TIMEOUT_MS = 5000;

let gtfsDb;
let rtDb;

const resolveConfiguredPath = (configured, fallback) => {
  const value = configured || fallback;
  return path.isAbsolute(value) ? value : path.resolve(__dirname, '..', value);
};

const resolveGtfsPath = () => resolveConfiguredPath(process.env.DATABASE_PATH, '../API/db/SubwaySystem.db');
const resolveRtPath = () => resolveConfiguredPath(process.env.RT_DATABASE_PATH, './data/realtime.db');

const runOn = (handle, sql, params = []) => new Promise((resolve, reject) => {
  handle.run(sql, params, function onRun(err) {
    if (err) {
      reject(err);
      return;
    }
    resolve(this);
  });
});

const getOn = (handle, sql, params = []) => new Promise((resolve, reject) => {
  handle.get(sql, params, (err, row) => {
    if (err) {
      reject(err);
      return;
    }
    resolve(row);
  });
});

const allOn = (handle, sql, params = []) => new Promise((resolve, reject) => {
  handle.all(sql, params, (err, rows) => {
    if (err) {
      reject(err);
      return;
    }
    resolve(rows);
  });
});

// Opened lazily: on a fresh clone the file does not exist until the first
// GTFS sync has run, and the server must still be able to boot to run it.
const openGtfs = () => new Promise((resolve, reject) => {
  if (gtfsDb) {
    resolve(gtfsDb);
    return;
  }

  const dbPath = resolveGtfsPath();
  if (!fs.existsSync(dbPath)) {
    reject(new Error(`GTFS database not found at ${dbPath}. Run "npm run sync" first.`));
    return;
  }

  const handle = new sqlite3.Database(dbPath, sqlite3.OPEN_READONLY, (err) => {
    if (err) {
      reject(err);
      return;
    }
    handle.configure('busyTimeout', BUSY_TIMEOUT_MS);
    gtfsDb = handle;
    resolve(gtfsDb);
  });
});

const getRt = () => {
  if (!rtDb) {
    throw new Error('Realtime database has not been initialized. Call init() first.');
  }
  return rtDb;
};

const gtfs = {
  get: async (sql, params = []) => getOn(await openGtfs(), sql, params),
  all: async (sql, params = []) => allOn(await openGtfs(), sql, params)
};

const rt = {
  run: (sql, params = []) => runOn(getRt(), sql, params),
  get: (sql, params = []) => getOn(getRt(), sql, params),
  all: (sql, params = []) => allOn(getRt(), sql, params),
  withTransaction: async (callback) => {
    await runOn(getRt(), 'BEGIN TRANSACTION');
    try {
      const result = await callback();
      await runOn(getRt(), 'COMMIT');
      return result;
    } catch (error) {
      await runOn(getRt(), 'ROLLBACK');
      throw error;
    }
  }
};

const createRtSchema = async () => {
  await rt.run('PRAGMA journal_mode=WAL');

  await rt.run(`
    CREATE TABLE IF NOT EXISTS synced_records (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      source_key TEXT NOT NULL UNIQUE,
      payload TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )
  `);

  await rt.run(`
    CREATE TABLE IF NOT EXISTS sync_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ran_at TEXT NOT NULL,
      status TEXT NOT NULL,
      record_count INTEGER NOT NULL,
      message TEXT
    )
  `);

  await rt.run(`
    CREATE TABLE IF NOT EXISTS meta (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL
    )
  `);

  await rt.run(`
    CREATE TABLE IF NOT EXISTS rt_snapshot (
      id INTEGER PRIMARY KEY CHECK (id = 1),
      polled_at TEXT NOT NULL,
      status TEXT NOT NULL,
      positions TEXT NOT NULL
    )
  `);
};

const init = () => new Promise((resolve, reject) => {
  if (rtDb) {
    resolve(rtDb);
    return;
  }

  const dbPath = resolveRtPath();
  fs.mkdirSync(path.dirname(dbPath), { recursive: true });
  const handle = new sqlite3.Database(dbPath, async (err) => {
    if (err) {
      reject(err);
      return;
    }

    handle.configure('busyTimeout', BUSY_TIMEOUT_MS);
    rtDb = handle;

    try {
      await createRtSchema();
      console.log(`Connected to realtime database at ${dbPath}`);
      resolve(rtDb);
    } catch (schemaError) {
      rtDb = null;
      reject(schemaError);
    }
  });
});

const closeHandle = (handle) => new Promise((resolve, reject) => {
  if (!handle) {
    resolve();
    return;
  }
  handle.close((err) => {
    if (err) {
      reject(err);
      return;
    }
    resolve();
  });
});

const close = async () => {
  await closeHandle(rtDb);
  rtDb = null;
  await closeHandle(gtfsDb);
  gtfsDb = null;
};

module.exports = {
  init,
  gtfs,
  rt,
  close,
  resolveGtfsPath
};
