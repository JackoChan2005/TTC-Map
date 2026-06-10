const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '..', '..', 'env.config') });

const fs = require('fs');
const { spawn } = require('child_process');
const sqlite3 = require('sqlite3').verbose();

const db = require('../db');
const { fetchJson } = require('./fetchJson');
const { transformData } = require('./transform');

const DEFAULT_INTERVAL_MS = 60 * 1000;
const ROOT_DIR = path.resolve(__dirname, '..', '..', '..');
const PYTHON_SYNC_TABLE = 'SUBWAY_STOP_TIMES';

let syncInProgress = false;

const isTruthy = (value) => ['1', 'true', 'yes', 'on'].includes(String(value || '').trim().toLowerCase());

const resolvePathFromRoot = (inputPath, fallback) => {
  const resolved = inputPath || fallback;
  return path.isAbsolute(resolved) ? resolved : path.resolve(ROOT_DIR, resolved);
};

const getPythonConfig = () => ({
  enabled: isTruthy(process.env.PYTHON_SYNC_ENABLED),
  pythonBin: process.env.PYTHON_BIN || 'python',
  scriptPath: resolvePathFromRoot(process.env.PYTHON_SYNC_SCRIPT, 'API/src/update_db.py'),
  dbPath: resolvePathFromRoot(process.env.PYTHON_SYNC_DB_PATH, 'API/db/SubwaySystem.db')
});

const runPythonUpdate = ({ pythonBin, scriptPath }) => new Promise((resolve, reject) => {
  const child = spawn(pythonBin, [scriptPath], { cwd: ROOT_DIR });
  let stderr = '';

  child.stderr.on('data', (chunk) => {
    stderr += chunk.toString();
  });

  child.on('error', (error) => {
    reject(new Error(`Failed to run Python updater (${pythonBin} ${scriptPath}): ${error.message}`));
  });

  child.on('close', (code) => {
    if (code === 0) {
      resolve();
      return;
    }

    const message = stderr.trim() || `exit code ${code}`;
    reject(new Error(`Python updater failed: ${message}`));
  });
});

const openReadOnlyDb = (dbPath) => new Promise((resolve, reject) => {
  const sqliteDb = new sqlite3.Database(dbPath, sqlite3.OPEN_READONLY, (err) => {
    if (err) {
      reject(err);
      return;
    }
    resolve(sqliteDb);
  });
});

const readAll = (sqliteDb, sql, params = []) => new Promise((resolve, reject) => {
  sqliteDb.all(sql, params, (err, rows) => {
    if (err) {
      reject(err);
      return;
    }
    resolve(rows);
  });
});

const closeSqliteDb = (sqliteDb) => new Promise((resolve, reject) => {
  sqliteDb.close((err) => {
    if (err) {
      reject(err);
      return;
    }
    resolve();
  });
});

const mapPythonRowsToRecords = (rows) => {
  const updatedAt = new Date().toISOString();

  return rows.map((row, index) => {
    const tripId = row.trip_id ?? `trip-${index}`;
    const stopSequence = row.stop_sequence ?? index;

    return {
      sourceKey: `${tripId}-${stopSequence}`,
      payload: JSON.stringify(row),
      updatedAt
    };
  });
};

const syncFromPython = async () => {
  const pythonConfig = getPythonConfig();
  if (!pythonConfig.enabled) {
    return null;
  }

  if (!fs.existsSync(pythonConfig.scriptPath)) {
    throw new Error(`Python sync script not found at ${pythonConfig.scriptPath}`);
  }

  await runPythonUpdate(pythonConfig);

  if (!fs.existsSync(pythonConfig.dbPath)) {
    throw new Error(`Python sync database not found at ${pythonConfig.dbPath}`);
  }

  const sqliteDb = await openReadOnlyDb(pythonConfig.dbPath);

  try {
    const rows = await readAll(sqliteDb, `SELECT * FROM ${PYTHON_SYNC_TABLE}`);
    const records = mapPythonRowsToRecords(rows);

    return {
      source: `python:${path.relative(ROOT_DIR, pythonConfig.scriptPath).replace(/\\/g, '/')}`,
      records
    };
  } finally {
    await closeSqliteDb(sqliteDb);
  }
};

const getJsonSource = () => {
  const pythonConfig = getPythonConfig();
  if (pythonConfig.enabled) {
    return `python:${path.relative(ROOT_DIR, pythonConfig.scriptPath).replace(/\\/g, '/')}`;
  }

  return process.env.JSON_SOURCE || './data/source.json';
};

const loadRecordsForSync = async () => {
  const pythonSyncResult = await syncFromPython();
  if (pythonSyncResult) {
    return {
      source: pythonSyncResult.source,
      records: pythonSyncResult.records,
      mode: 'python'
    };
  }

  const source = getJsonSource();
  const rawData = await fetchJson(source);
  const records = transformData(rawData);

  return {
    source,
    records,
    mode: 'json'
  };
};

const persistRecords = async (records) => {
  await db.withTransaction(async () => {
    await db.run('DELETE FROM synced_records');

    for (const record of records) {
      await db.run(
        'INSERT INTO synced_records (source_key, payload, updated_at) VALUES (?, ?, ?)',
        [record.sourceKey, record.payload, record.updatedAt]
      );
    }
  });
};

const logRun = async ({ status, recordCount, message }) => {
  await db.run(
    'INSERT INTO sync_runs (ran_at, status, record_count, message) VALUES (?, ?, ?, ?)',
    [new Date().toISOString(), status, recordCount, message || null]
  );
};

const runSync = async () => {
  if (syncInProgress) {
    return {
      status: 'skipped',
      message: 'sync already running'
    };
  }

  syncInProgress = true;

  try {
    const { source, records, mode } = await loadRecordsForSync();
    const ranAt = new Date().toISOString();

    await persistRecords(records);
    await logRun({
      status: 'success',
      recordCount: records.length
    });

    return {
      status: 'success',
      source,
      mode,
      recordCount: records.length,
      ranAt
    };
  } catch (error) {
    await logRun({
      status: 'error',
      recordCount: 0,
      message: error.message
    });
    throw error;
  } finally {
    syncInProgress = false;
  }
};

const startSyncCron = (intervalMs = Number(process.env.SYNC_INTERVAL_MS || DEFAULT_INTERVAL_MS)) => setInterval(() => {
  runSync()
    .then((result) => {
      if (result.status === 'success') {
        console.log(`Scheduled sync completed at ${result.ranAt} (${result.recordCount} records)`);
      }
    })
    .catch((error) => {
      console.error('Scheduled sync failed:', error.message);
    });
}, intervalMs);

if (require.main === module) {
  db.init()
    .then(() => runSync())
    .then((result) => {
      console.log('Sync completed:', result);
    })
    .catch((error) => {
      console.error('Sync failed:', error.message);
      process.exitCode = 1;
    })
    .finally(async () => {
      try {
        await db.close();
      } catch (closeError) {
        console.error('Failed to close database:', closeError.message);
      }
    });
}

module.exports = {
  runSync,
  startSyncCron,
  getJsonSource
};
