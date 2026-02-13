const express = require('express');
const db = require('./db');
const { runSync, getJsonSource } = require('./sync/syncJob');

const router = express.Router();
const ROUTE_KEYS = new Set(['route', 'route_id', 'routeid', 'line', 'line_id', 'routenum', 'route_number']);
const TIME_KEYS = new Set([
  'timestamp',
  'time',
  'updated_at',
  'updatedat',
  'vehicle_timestamp',
  'trip_start_time',
  'departure_time',
  'arrival_time'
]);

const MAX_SEARCH_ROWS = 10000;

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

const findValuesByKey = (input, allowedKeys, depth = 0, out = []) => {
  if (depth > 4 || input === null || input === undefined) {
    return out;
  }

  if (Array.isArray(input)) {
    for (const item of input) {
      findValuesByKey(item, allowedKeys, depth + 1, out);
    }
    return out;
  }

  if (typeof input !== 'object') {
    return out;
  }

  for (const [key, value] of Object.entries(input)) {
    const normalizedKey = key.replace(/[\s-]/g, '').toLowerCase();
    if (allowedKeys.has(normalizedKey)) {
      out.push(value);
    }

    if (value && typeof value === 'object') {
      findValuesByKey(value, allowedKeys, depth + 1, out);
    }
  }

  return out;
};

const doesRouteMatch = (payload, requestedRoute) => {
  const routeCandidates = findValuesByKey(payload, ROUTE_KEYS);
  return routeCandidates.some((candidate) => normalizeRouteValue(candidate) === requestedRoute);
};

const getRecordTime = (record) => {
  const timeCandidates = findValuesByKey(record.payload, TIME_KEYS);
  for (const candidate of timeCandidates) {
    const parsed = parseTimestampCandidate(candidate);
    if (parsed) {
      return parsed;
    }
  }

  return parseTimestampCandidate(record.updated_at);
};

router.get('/route-search', async (req, res, next) => {
  try {
    const requestedRoute = normalizeRouteValue(req.query.route);
    if (!requestedRoute) {
      res.status(400).json({ message: 'Query parameter "route" is required' });
      return;
    }

    const at = req.query.at;
    const requestedTime = at ? parseTimestampCandidate(at) : new Date();
    if (!requestedTime) {
      res.status(400).json({ message: 'Query parameter "at" must be a valid date/time' });
      return;
    }

    const rows = await db.all(
      'SELECT id, source_key, payload, updated_at FROM synced_records ORDER BY id DESC LIMIT ?',
      [MAX_SEARCH_ROWS]
    );
    const records = rows.map(parsePayload);
    const routeRecords = records.filter((record) => doesRouteMatch(record.payload, requestedRoute));

    if (routeRecords.length === 0) {
      res.status(404).json({
        message: `No records found for route ${requestedRoute}`,
        route: requestedRoute,
        requestedAt: requestedTime.toISOString()
      });
      return;
    }

    const ranked = routeRecords
      .map((record) => {
        const recordTime = getRecordTime(record);
        const diffMs = recordTime ? Math.abs(recordTime.getTime() - requestedTime.getTime()) : Number.MAX_SAFE_INTEGER;
        return {
          id: record.id,
          sourceKey: record.source_key,
          updatedAt: record.updated_at,
          recordTime: recordTime ? recordTime.toISOString() : null,
          deltaSeconds: Number.isFinite(diffMs) ? Math.round(diffMs / 1000) : null,
          payload: record.payload
        };
      })
      .sort((a, b) => (a.deltaSeconds ?? Number.MAX_SAFE_INTEGER) - (b.deltaSeconds ?? Number.MAX_SAFE_INTEGER));

    res.json({
      route: requestedRoute,
      requestedAt: requestedTime.toISOString(),
      totalMatches: ranked.length,
      bestMatch: ranked[0],
      matches: ranked.slice(0, 25)
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
