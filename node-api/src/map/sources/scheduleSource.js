// Schedule-based train positions: a train is between consecutive stops A and B
// when A's departure has passed and B's has not. Static GTFS, so this is a
// simulation of where trains should be, not live data.

const db = require('../../db');
const { loadTopology } = require('../topology');
const { getServiceWindows, WEEKDAY_COLUMNS } = require('../torontoTime');

const getTrainPositions = async (now = new Date()) => {
  const topology = loadTopology();
  const byTrip = new Map();

  for (const window of getServiceWindows(now)) {
    if (!WEEKDAY_COLUMNS.has(window.day)) {
      continue;
    }

    const rows = await db.gtfs.all(`
      SELECT
        a.trip_id AS tripId,
        a.direction_id AS direction,
        a.stop_id AS fromStop,
        b.stop_id AS toStop,
        a.departing_time_sec AS depSec,
        b.departing_time_sec AS arrSec
      FROM SUBWAY_STOP_TIMES a
      JOIN SUBWAY_STOP_TIMES b
        ON b.trip_id = a.trip_id
       AND b.stop_sequence = a.stop_sequence + 1
      JOIN SERVICE_DAYS sd
        ON sd.service_id = a.service_id
      WHERE sd.${window.day} = 1
        AND a.departing_time_sec <= ?
        AND b.departing_time_sec > ?
    `, [window.sec, window.sec]);

    for (const row of rows) {
      const from = topology.platforms[String(row.fromStop)];
      const to = topology.platforms[String(row.toStop)];
      if (!from || !to) {
        continue;
      }

      const span = row.arrSec - row.depSec;
      byTrip.set(row.tripId, {
        line: from.line,
        direction: row.direction,
        tripId: row.tripId,
        from: from.station,
        to: to.station,
        progress: span > 0 ? (window.sec - row.depSec) / span : 0
      });
    }
  }

  return [...byTrip.values()];
};

module.exports = {
  name: 'schedule',
  getTrainPositions
};
