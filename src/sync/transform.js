const DEFAULT_CONTAINER_KEYS = ['records', 'data', 'items', 'results', 'trips', 'resources'];

const pickCollection = (rawData) => {
  if (Array.isArray(rawData)) {
    return rawData;
  }

  if (rawData && typeof rawData === 'object') {
    for (const key of DEFAULT_CONTAINER_KEYS) {
      if (Array.isArray(rawData[key])) {
        return rawData[key];
      }
    }
  }

  return [rawData];
};

const createKey = (value, index, usedKeys) => {
  let baseKey = String(index);

  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const preferred = value.id || value.key || value.trip_id || value.vehicle_id || value.stop_id;
    if (preferred !== undefined && preferred !== null) {
      baseKey = String(preferred);
    }
  }

  let candidate = baseKey;
  let suffix = 1;
  while (usedKeys.has(candidate)) {
    suffix += 1;
    candidate = `${baseKey}-${suffix}`;
  }

  usedKeys.add(candidate);
  return candidate;
};

const transformData = (rawData) => {
  const collection = pickCollection(rawData);
  const timestamp = new Date().toISOString();
  const usedKeys = new Set();

  return collection.map((item, index) => ({
    sourceKey: createKey(item, index, usedKeys),
    payload: JSON.stringify(item ?? null),
    updatedAt: timestamp
  }));
};

module.exports = {
  transformData
};
