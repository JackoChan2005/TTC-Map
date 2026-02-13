const path = require('path');
const sqlite3 = require('sqlite3').verbose();

let db;

const resolveDbPath = () => {
  const configured = process.env.DATABASE_PATH || './data.db';
  return path.isAbsolute(configured)
    ? configured
    : path.resolve(__dirname, '..', configured);
};

const getDb = () => {
  if (!db) {
    throw new Error('Database has not been initialized. Call init() first.');
  }
  return db;
};

const run = (sql, params = []) => new Promise((resolve, reject) => {
  getDb().run(sql, params, function onRun(err) {
    if (err) {
      reject(err);
      return;
    }
    resolve(this);
  });
});

const get = (sql, params = []) => new Promise((resolve, reject) => {
  getDb().get(sql, params, (err, row) => {
    if (err) {
      reject(err);
      return;
    }
    resolve(row);
  });
});

const all = (sql, params = []) => new Promise((resolve, reject) => {
  getDb().all(sql, params, (err, rows) => {
    if (err) {
      reject(err);
      return;
    }
    resolve(rows);
  });
});

const withTransaction = async (callback) => {
  await run('BEGIN TRANSACTION');
  try {
    const result = await callback();
    await run('COMMIT');
    return result;
  } catch (error) {
    await run('ROLLBACK');
    throw error;
  }
};

const createSchema = async () => {
  await run(`
    CREATE TABLE IF NOT EXISTS synced_records (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      source_key TEXT NOT NULL UNIQUE,
      payload TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )
  `);

  await run(`
    CREATE TABLE IF NOT EXISTS sync_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ran_at TEXT NOT NULL,
      status TEXT NOT NULL,
      record_count INTEGER NOT NULL,
      message TEXT
    )
  `);
};

const init = () => new Promise((resolve, reject) => {
  if (db) {
    resolve(db);
    return;
  }

  const dbPath = resolveDbPath();
  db = new sqlite3.Database(dbPath, async (err) => {
    if (err) {
      reject(err);
      return;
    }

    try {
      await createSchema();
      console.log(`Connected to SQLite database at ${dbPath}`);
      resolve(db);
    } catch (schemaError) {
      reject(schemaError);
    }
  });
});

const close = () => new Promise((resolve, reject) => {
  if (!db) {
    resolve();
    return;
  }

  db.close((err) => {
    if (err) {
      reject(err);
      return;
    }
    db = null;
    resolve();
  });
});

module.exports = {
  init,
  getDb,
  run,
  get,
  all,
  withTransaction,
  close
};
