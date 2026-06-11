const path = require('path');
require('./loadEnv');

const express = require('express');
const db = require('./db');
const routes = require('./routes');
const mapRoutes = require('./mapRoutes');
const { securityHeaders } = require('./securityHeaders');
const { runSync, startSyncCron } = require('./sync/syncJob');

const app = express();

app.use(securityHeaders());
app.use(express.json());
app.use(express.static(path.resolve(__dirname, '..', 'public')));
app.use('/api/v1', mapRoutes);
app.use('/api', routes);
// the schematic map moved from /map/ to the main page
app.get(['/map', '/map/*'], (_req, res) => res.redirect(301, '/'));

const PORT = Number(process.env.PORT || 3000);
const SYNC_INTERVAL_MS = Number(process.env.SYNC_INTERVAL_MS || 60_000);

const startServer = async () => {
  await db.init();

  try {
    const initialSync = await runSync();
    console.log('Initial sync result:', initialSync);
  } catch (error) {
    console.error(`Initial sync failed: ${error.message}`);
  }

  const cronHandle = startSyncCron(SYNC_INTERVAL_MS);
  const server = app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
    console.log(`Sync scheduled every ${Math.floor(SYNC_INTERVAL_MS / 1000)} seconds`);
  });

  const shutdown = async () => {
    clearInterval(cronHandle);

    server.close(async () => {
      try {
        await db.close();
      } catch (error) {
        console.error('Error closing database:', error.message);
      } finally {
        process.exit(0);
      }
    });
  };

  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
};

startServer().catch((error) => {
  console.error('Server startup failed:', error.message);
  process.exit(1);
});

