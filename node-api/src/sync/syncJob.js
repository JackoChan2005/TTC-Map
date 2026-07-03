const path = require('path');
require('../loadEnv');

const fs = require('fs');
const { spawn } = require('child_process');

const db = require('../db');
const { fetchJson, getPackageMetadata, getCkanPackageId } = require('./fetchJson');
const { transformData } = require('./transform');

// The GTFS feed changes every few weeks, so the cron only *checks* CKAN's
// metadata_modified on this interval and rebuilds when it differs from the
// version recorded in the meta table (or when the database is missing).
const DEFAULT_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000;
const ROOT_DIR = path.resolve(__dirname, '..', '..', '..');
const PYTHON_SYNC_TABLE = 'SUBWAY_STOP_TIMES';
const GTFS_VERSION_META_KEY = 'gtfs_last_modified';
const INSERT_CHUNK_SIZE = 300;

let syncInProgress = false;

const isTruthy = (value) => ['1', 'true', 'yes', 'on'].includes(String(value || '').trim().toLowerCase());

const resolvePathFromRoot = (inputPath, fallback) => {
  const resolved = inputPath || fallback;
  return path.isAbsolute(resolved) ? resolved : path.resolve(ROOT_DIR, resolved);
};

const getPythonConfig = () => ({
  enabled: isTruthy(process.env.PYTHON_SYNC_ENABLED),
  pythonBin: process.env.PYTHON_BIN || 'python',
  scriptPath: resolvePathFromRoot(process.env.PYTHON_SYNC_SCRIPT, 'API/src/update_db.py')
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

const getStoredGtfsVersion = () => db.rt
  .get('SELECT value FROM meta WHERE key = ?', [GTFS_VERSION_META_KEY])
  .then((row) => row?.value ?? null);

const setStoredGtfsVersion = (value) => db.rt.run(
  'INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value',
  [GTFS_VERSION_META_KEY, value]
);

const fetchRemoteGtfsVersion = async () => {
  const packageId = getCkanPackageId(process.env.JSON_SOURCE);
  if (!packageId) {
    return null;
  }
  const pkg = await getPackageMetadata(packageId, process.env.CKAN_BASE_URL || undefined);
  return pkg.metadata_modified || null;
};

const syncFromPython = async ({ force = false } = {}) => {
  const pythonConfig = getPythonConfig();
  if (!pythonConfig.enabled) {
    return null;
  }

  const source = `python:${path.relative(ROOT_DIR, pythonConfig.scriptPath).replace(/\\/g, '/')}`;
  const dbMissing = !fs.existsSync(db.resolveGtfsPath());
  const storedVersion = await getStoredGtfsVersion();

  let remoteVersion = null;
  try {
    remoteVersion = await fetchRemoteGtfsVersion();
  } catch (error) {
    // CKAN unreachable: keep serving the existing database rather than fail,
    // unless we have nothing to serve yet.
    if (!dbMissing && storedVersion) {
      return {
        source,
        records: null,
        updated: false,
        message: `GTFS version check failed (${error.message}); keeping current data`
      };
    }
  }

  const upToDate = !force && !dbMissing && storedVersion && remoteVersion === storedVersion;
  if (upToDate) {
    return {
      source,
      records: null,
      updated: false,
      message: `GTFS feed unchanged (${remoteVersion})`
    };
  }

  if (!fs.existsSync(pythonConfig.scriptPath)) {
    throw new Error(`Python sync script not found at ${pythonConfig.scriptPath}`);
  }

  await runPythonUpdate(pythonConfig);

  if (!fs.existsSync(db.resolveGtfsPath())) {
    throw new Error(`Python sync database not found at ${db.resolveGtfsPath()}`);
  }

  const rows = await db.gtfs.all(`SELECT * FROM ${PYTHON_SYNC_TABLE}`);
  const records = mapPythonRowsToRecords(rows);
  if (remoteVersion) {
    await setStoredGtfsVersion(remoteVersion);
  }

  return {
    source,
    records,
    updated: true,
    message: `rebuilt from GTFS feed (${remoteVersion || 'version unknown'})`
  };
};

const getJsonSource = () => {
  const pythonConfig = getPythonConfig();
  if (pythonConfig.enabled) {
    return `python:${path.relative(ROOT_DIR, pythonConfig.scriptPath).replace(/\\/g, '/')}`;
  }

  return process.env.JSON_SOURCE || './data/source.json';
};

const loadRecordsForSync = async ({ force = false } = {}) => {
  const pythonSyncResult = await syncFromPython({ force });
  if (pythonSyncResult) {
    return { ...pythonSyncResult, mode: 'python' };
  }

  const source = getJsonSource();
  const rawData = await fetchJson(source);
  const records = transformData(rawData);

  return {
    source,
    records,
    updated: true,
    message: null,
    mode: 'json'
  };
};

const persistRecords = async (records) => {
  await db.rt.withTransaction(async () => {
    await db.rt.run('DELETE FROM synced_records');

    for (let i = 0; i < records.length; i += INSERT_CHUNK_SIZE) {
      const chunk = records.slice(i, i + INSERT_CHUNK_SIZE);
      const placeholders = chunk.map(() => '(?, ?, ?)').join(', ');
      const params = chunk.flatMap((record) => [record.sourceKey, record.payload, record.updatedAt]);
      await db.rt.run(
        `INSERT INTO synced_records (source_key, payload, updated_at) VALUES ${placeholders}`,
        params
      );
    }
  });
};

const logRun = async ({ status, recordCount, message }) => {
  await db.rt.run(
    'INSERT INTO sync_runs (ran_at, status, record_count, message) VALUES (?, ?, ?, ?)',
    [new Date().toISOString(), status, recordCount, message || null]
  );
};

const runSync = async ({ force = false } = {}) => {
  if (syncInProgress) {
    return {
      status: 'skipped',
      message: 'sync already running'
    };
  }

  syncInProgress = true;

  try {
    const { source, records, updated, message, mode } = await loadRecordsForSync({ force });
    const ranAt = new Date().toISOString();

    if (updated && records) {
      await persistRecords(records);
    }
    await logRun({
      status: 'success',
      recordCount: records ? records.length : 0,
      message
    });

    return {
      status: 'success',
      source,
      mode,
      updated,
      message,
      recordCount: records ? records.length : 0,
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

const startSyncCron = (intervalMs = Number(process.env.GTFS_CHECK_INTERVAL_MS || DEFAULT_CHECK_INTERVAL_MS)) => setInterval(() => {
  runSync()
    .then((result) => {
      if (result.status === 'success') {
        const detail = result.updated
          ? `${result.recordCount} records`
          : (result.message || 'no update needed');
        console.log(`Scheduled GTFS check completed at ${result.ranAt} (${detail})`);
      }
    })
    .catch((error) => {
      console.error('Scheduled GTFS check failed:', error.message);
    });
}, intervalMs);

if (require.main === module) {
  const force = process.argv.includes('--force');
  db.init()
    .then(() => runSync({ force }))
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
