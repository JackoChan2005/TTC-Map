const express = require('express');

const { getMapState, SOURCES } = require('./map');
const { loadTopology, loadLayout } = require('./map/topology');
const { loadLedMap, renderLedState } = require('./map/renderers/ledRenderer');

const router = express.Router();

router.get('/network', (_req, res, next) => {
  try {
    res.json(loadTopology());
  } catch (error) {
    next(error);
  }
});

router.get('/layout/:name', (req, res, next) => {
  try {
    const layout = loadLayout(req.params.name);
    if (!layout) {
      res.status(404).json({ message: `Layout "${req.params.name}" not found` });
      return;
    }
    res.json(layout);
  } catch (error) {
    next(error);
  }
});

router.get('/map-state', async (req, res, next) => {
  try {
    const { source, at } = req.query;
    if (source && source !== 'auto' && !SOURCES[source]) {
      res.status(400).json({ message: `Unknown source "${source}". Use auto, schedule or ntas.` });
      return;
    }

    const now = at ? new Date(at) : new Date();
    if (Number.isNaN(now.getTime())) {
      res.status(400).json({ message: 'Query parameter "at" must be a valid date/time' });
      return;
    }

    res.json(await getMapState({ now, source }));
  } catch (error) {
    next(error);
  }
});

router.get('/led-state', async (req, res, next) => {
  try {
    const mapName = req.query.map || 'rev-a';
    const ledMap = loadLedMap(mapName);
    if (!ledMap) {
      res.status(404).json({ message: `LED map "${mapName}" not found` });
      return;
    }

    const state = await getMapState({ source: req.query.source });
    res.json(renderLedState(state, ledMap));
  } catch (error) {
    next(error);
  }
});

router.use((error, _req, res, _next) => {
  res.status(500).json({ message: error.message || 'Internal server error' });
});

module.exports = router;
