const express = require('express');
const db = require('./db');
const { runSync, getJsonSource } = require('./sync/syncJob');

const router = express.Router();
const TORONTO_TIMEZONE = 'America/Toronto';
const DEPARTURE_WINDOW_SECONDS = 120;
const WEEKDAY_COLUMNS = new Set([
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday'
]);

const parsePayload = (row) => {
  try {
    return {
      ...row,
      payload: JSON.parse(row.payload)
    };
  } catch (_error) {
    return row;
  }
};

const normalizeRouteValue = (value) => {
  if (value === null || value === undefined) {
    return '';
  }

  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(Math.trunc(value));
  }

  const cleaned = String(value).trim().toLowerCase();
  if (!cleaned) {
    return '';
  }

  if (/^\d+$/.test(cleaned)) {
    return String(Number.parseInt(cleaned, 10));
  }

  return cleaned;
};

const parseTimestampCandidate = (value) => {
  if (value === null || value === undefined) {
    return null;
  }

  if (typeof value === 'number' && Number.isFinite(value)) {
    const msValue = value > 1_000_000_000_000 ? value : value * 1000;
    const dateFromNumber = new Date(msValue);
    return Number.isNaN(dateFromNumber.getTime()) ? null : dateFromNumber;
  }

  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }

    const parsedMs = Date.parse(trimmed);
    if (!Number.isNaN(parsedMs)) {
      return new Date(parsedMs);
    }

    const timeOnlyMatch = trimmed.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
    if (timeOnlyMatch) {
      const now = new Date();
      const hours = Number.parseInt(timeOnlyMatch[1], 10);
      const minutes = Number.parseInt(timeOnlyMatch[2], 10);
      const seconds = Number.parseInt(timeOnlyMatch[3] || '0', 10);
      now.setHours(hours, minutes, seconds, 0);
      return now;
    }
  }

  return null;
};

const parseGtfsTimeToSeconds = (value) => {
  if (typeof value !== 'string') {
    return null;
  }

  const trimmed = value.trim();
  const match = trimmed.match(/^(\d+):([0-5]\d):([0-5]\d)$/);
  if (!match) {
    return null;
  }

  const hours = Number.parseInt(match[1], 10);
  const minutes = Number.parseInt(match[2], 10);
  const seconds = Number.parseInt(match[3], 10);

  return (hours * 3600) + (minutes * 60) + seconds;
};

const getTorontoTimeParts = (date) => {
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: TORONTO_TIMEZONE,
    weekday: 'long',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });

  const parts = formatter.formatToParts(date);
  const valueByType = {};
  for (const part of parts) {
    valueByType[part.type] = part.value;
  }

  return {
    weekday: String(valueByType.weekday || '').toLowerCase(),
    hour: Number.parseInt(valueByType.hour || '0', 10),
    minute: Number.parseInt(valueByType.minute || '0', 10),
    second: Number.parseInt(valueByType.second || '0', 10)
  };
};

const torontoServiceWeekdayForSec = (baseDate, sec) => {
  const serviceDate = sec >= 24 * 3600
    ? new Date(baseDate.getTime() - (24 * 3600 * 1000))
    : baseDate;
  const { weekday } = getTorontoTimeParts(serviceDate);
  return weekday;
};

const getRequestedWindow = (atValue) => {
  const baseDate = atValue ? parseTimestampCandidate(atValue) : new Date();
  if (!baseDate) {
    return null;
  }

  const explicitGtfsSeconds = parseGtfsTimeToSeconds(atValue);
  const { hour, minute, second } = getTorontoTimeParts(baseDate);
  const sec = explicitGtfsSeconds ?? ((hour * 3600) + (minute * 60) + second);
  const day = torontoServiceWeekdayForSec(baseDate, sec);

  if (!WEEKDAY_COLUMNS.has(day)) {
    return null;
  }

  return {
    sec,
    day,
    requestedAt: baseDate.toISOString()
  };
};

router.get('/route-search', async (req, res, next) => {
  try {
    const requestedRoute = normalizeRouteValue(req.query.route);
    if (!requestedRoute) {
      res.status(400).json({ message: 'Query parameter "route" is required' });
      return;
    }

    const requestedWindow = getRequestedWindow(req.query.at);
    if (!requestedWindow) {
      res.status(400).json({ message: 'Query parameter "at" must be a valid date/time' });
      return;
    }

    const rows = await db.all(`
      SELECT
        sst.trip_id,
        sst.stop_sequence,
        sst.route_id,
        sst.service_id,
        sst.direction_id,
        sst.stop_id,
        sst.stop_name,
        sst.arrival_time,
        sst.departure_time,
        sst.departing_time_sec
      FROM SUBWAY_STOP_TIMES sst
      JOIN SERVICE_DAYS sd
        ON sd.service_id = sst.service_id
      WHERE sd.${requestedWindow.day} = 1
        AND CAST(sst.route_id AS TEXT) = ?
        AND sst.departing_time_sec BETWEEN ? AND ?
      ORDER BY sst.departure_time
      LIMIT 200
    `, [requestedRoute, requestedWindow.sec, requestedWindow.sec + DEPARTURE_WINDOW_SECONDS]);

    if (rows.length === 0) {
      res.status(404).json({
        message: `No trains for route ${requestedRoute} in the next 2 minutes`,
        route: requestedRoute,
        requestedAt: requestedWindow.requestedAt,
        serviceDay: requestedWindow.day
      });
      return;
    }

    const matches = rows.map((row) => ({
      sourceKey: `${row.trip_id}-${row.stop_sequence}`,
      recordTime: row.departure_time,
      updatedAt: null,
      deltaSeconds: row.departing_time_sec - requestedWindow.sec,
      payload: row
    }));

    res.json({
      route: requestedRoute,
      requestedAt: requestedWindow.requestedAt,
      serviceDay: requestedWindow.day,
      totalMatches: matches.length,
      bestMatch: matches[0],
      matches
    });
  } catch (error) {
    next(error);
  }
});

router.get('/health', async (_req, res, next) => {
  try {
    const latestRun = await db.get('SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1');
    res.json({
      status: 'ok',
      source: getJsonSource(),
      latestSync: latestRun || null,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    next(error);
  }
});

router.post('/sync/run', async (_req, res, next) => {
  try {
    const result = await runSync();
    res.json(result);
  } catch (error) {
    next(error);
  }
});

router.get('/sync/status', async (_req, res, next) => {
  try {
    const latestRun = await db.get('SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1');
    if (!latestRun) {
      res.status(404).json({ message: 'No sync run recorded yet' });
      return;
    }

    res.json(latestRun);
  } catch (error) {
    next(error);
  }
});

router.get('/records', async (req, res, next) => {
  try {
    const limit = Number.parseInt(req.query.limit, 10);
    const safeLimit = Number.isNaN(limit) ? 100 : Math.min(Math.max(limit, 1), 1000);

    const rows = await db.all(
      'SELECT id, source_key, payload, updated_at FROM synced_records ORDER BY id DESC LIMIT ?',
      [safeLimit]
    );

    res.json(rows.map(parsePayload));
  } catch (error) {
    next(error);
  }
});

router.get('/records/:sourceKey', async (req, res, next) => {
  try {
    const row = await db.get(
      'SELECT id, source_key, payload, updated_at FROM synced_records WHERE source_key = ?',
      [req.params.sourceKey]
    );

    if (!row) {
      res.status(404).json({ message: 'Record not found' });
      return;
    }

    res.json(parsePayload(row));
  } catch (error) {
    next(error);
  }
});

router.use((error, _req, res, _next) => {
  res.status(500).json({
    message: error.message || 'Internal server error'
  });
});

module.exports = router;
