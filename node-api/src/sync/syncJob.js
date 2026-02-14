const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '..', '..', 'env.config') });

const db = require('../db');
const { fetchJson } = require('./fetchJson');
const { transformData } = require('./transform');

const DEFAULT_INTERVAL_MS = 60 * 1000;

let syncInProgress = false;

const getJsonSource = () => process.env.JSON_SOURCE || './data/source.json';

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
    const source = getJsonSource();
    const rawData = await fetchJson(source);
    const records = transformData(rawData);
    const ranAt = new Date().toISOString();

    await persistRecords(records);
    await logRun({
      status: 'success',
      recordCount: records.length
    });

    return {
      status: 'success',
      source,
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

