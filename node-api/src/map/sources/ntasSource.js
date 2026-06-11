// Realtime train positions from TTC's NTAS (Next Train Arrival System).
// One request per platform returns the next arrival times in minutes, e.g.
//   [{"line":"2","direction":"0","nextTrains":"1, 3, 6", ...}]
// A train arriving within ARRIVING_MIN minutes is placed approaching that
// platform's station from the previous station on the line. NTAS has no
// train ids, so positions are deduped per (line, direction, station).

const https = require('https');

const { loadTopology, previousStation } = require('../topology');

const NTAS_BASE_URL = process.env.NTAS_BASE_URL
  || 'https://ntas.ttc.ca/api/ntas/get-next-train-time/';
const ARRIVING_MIN = Number(process.env.NTAS_ARRIVING_MIN || 1);
const CACHE_MS = Number(process.env.NTAS_CACHE_MS || 30_000);
const CONCURRENCY = Number(process.env.NTAS_CONCURRENCY || 10);
const REQUEST_TIMEOUT_MS = 5_000;

const agent = new https.Agent({ keepAlive: true, maxSockets: CONCURRENCY });

let cache = { at: 0, positions: null };

const fetchPlatform = (platformId) => new Promise((resolve, reject) => {
  const req = https.get(`${NTAS_BASE_URL}${platformId}`, { agent }, (res) => {
    if (res.statusCode !== 200) {
      res.resume();
      reject(new Error(`NTAS HTTP ${res.statusCode} for platform ${platformId}`));
      return;
    }

    let data = '';
    res.setEncoding('utf8');
    res.on('data', (chunk) => { data += chunk; });
    res.on('end', () => {
      try {
        resolve(JSON.parse(data));
      } catch (err) {
        reject(new Error(`NTAS invalid JSON for platform ${platformId}`));
      }
    });
  });

  req.setTimeout(REQUEST_TIMEOUT_MS, () => req.destroy(new Error('NTAS timeout')));
  req.on('error', reject);
});

const firstArrivalMinutes = (entry) => {
  const first = String(entry.nextTrains || '').split(',')[0].trim();
  const minutes = Number.parseInt(first, 10);
  return Number.isNaN(minutes) ? null : minutes;
};

// pure; exported for tests
const positionsFromResponses = (topology, responses) => {
  const byKey = new Map();

  for (const { platformId, entries } of responses) {
    const platform = topology.platforms[platformId];
    if (!platform || !Array.isArray(entries)) {
      continue;
    }

    for (const entry of entries) {
      const minutes = firstArrivalMinutes(entry);
      if (minutes === null || minutes > ARRIVING_MIN) {
        continue;
      }

      const direction = Number.parseInt(entry.direction, 10);
      const station = platform.station;
      const from = previousStation(topology, platform.line, direction, station);

      const key = `${platform.line}|${direction}|${station}`;
      byKey.set(key, {
        line: platform.line,
        direction,
        from: from ?? station,
        to: from ? station : null,
        progress: from ? 1 - (minutes / (ARRIVING_MIN + 1)) : 0
      });
    }
  }

  return [...byKey.values()];
};

const runWithConcurrency = async (items, limit, worker) => {
  const results = [];
  let next = 0;

  const lane = async () => {
    while (next < items.length) {
      const index = next;
      next += 1;
      results[index] = await worker(items[index]).then(
        (value) => ({ status: 'fulfilled', value }),
        (reason) => ({ status: 'rejected', reason })
      );
    }
  };

  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, lane));
  return results;
};

const getTrainPositions = async () => {
  if (cache.positions && Date.now() - cache.at < CACHE_MS) {
    return cache.positions;
  }

  const topology = loadTopology();
  const platformIds = Object.keys(topology.platforms);

  const settled = await runWithConcurrency(platformIds, CONCURRENCY, async (platformId) => ({
    platformId,
    entries: await fetchPlatform(platformId)
  }));

  const ok = settled.filter((r) => r.status === 'fulfilled').map((r) => r.value);
  if (ok.length < platformIds.length / 2) {
    throw new Error(`NTAS unavailable: only ${ok.length}/${platformIds.length} platforms responded`);
  }

  const positions = positionsFromResponses(topology, ok);
  cache = { at: Date.now(), positions };
  return positions;
};

module.exports = {
  name: 'ntas',
  getTrainPositions,
  positionsFromResponses
};
