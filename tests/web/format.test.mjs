import test from 'node:test';
import assert from 'node:assert/strict';
import { sourceLabel, lineSourceLabel } from '../../web/js/format.js';
import { validateMapState } from '../../web/js/mapModel.js';

test('mixed sources and planned schedules are labelled truthfully', () => {
  const state = validateMapState({ source: 'mixed', generation: 'g', lineSources: {
    'line-1': { source: 'ntas' },
    'line-6': { source: 'schedule', reason: 'realtime_not_enabled' }
  }, trains: [] });
  assert.equal(state.source, 'mixed');
  assert.equal(state.generation, 'g');
  assert.equal(sourceLabel(state), 'live + scheduled');
  assert.equal(lineSourceLabel(state.lineSources['line-6']), 'scheduled');
  assert.equal(lineSourceLabel({ source: 'schedule', reason: 'insufficient_coverage' }),
    'scheduled (live predictions unavailable)');
});
