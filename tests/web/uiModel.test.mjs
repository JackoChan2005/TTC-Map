import test from 'node:test';
import assert from 'node:assert/strict';
import { searchNetwork, stationDepartures, sourceDescription, remainingSeconds } from '../../web/js/uiModel.js';
import { api, ApiError } from '../../web/js/api.js';

const network = {
  lines: [{ id: 'line-1', number: '1', name: 'Yonge-University' }],
  stations: { union: { name: 'Union', lines: ['line-1'] } },
  platforms: { '100': { station: 'union', line: 'line-1', direction: 0 } }
};
test('search finds case-insensitive stations and line numbers without address results', () => {
  assert.equal(searchNetwork(network, ' UNION ')[0].id, 'union');
  assert.equal(searchNetwork(network, '1')[0].type, 'line');
  assert.deepEqual(searchNetwork(network, 'some address'), []);
  assert.deepEqual(searchNetwork(network, ' '), []);
});
test('departure joins use the published platform ID, line and direction', () => {
  const correct = { deltaSeconds: 60, payload: { stop_id: '100', direction_id: 0 } };
  const result = { matches: [correct, { payload: { stop_id: '100', direction_id: 1 } }, { payload: { stop_id: 'missing' } }, null] };
  assert.deepEqual(stationDepartures(result, network, 'line-1', 'union', 0), [correct]);
  assert.deepEqual(stationDepartures(result, network, 'line-2', 'union', 0), []);
  assert.deepEqual(stationDepartures({}, network, 'line-1', 'union', 0), []);
});
test('missing sources never claim live service', () => {
  assert.equal(sourceDescription(null, 'line-1'), 'Data unavailable');
  assert.equal(sourceDescription({ lineSources: {} }, 'line-1'), 'Source unavailable');
  assert.equal(sourceDescription({ lineSources: { 'line-1': { source: 'schedule', reason: 'realtime_not_enabled' } } }, 'line-1'), 'Scheduled estimates');
});
test('cached schedule countdowns account for elapsed time and expire', () => {
  const result = { requestedAt: '2026-09-11T12:00:00Z' };
  assert.equal(remainingSeconds({ deltaSeconds: 60 }, result, Date.parse('2026-09-11T12:00:20Z')), 40);
  assert.equal(remainingSeconds({ deltaSeconds: 60 }, result, Date.parse('2026-09-11T12:01:01Z')), -1);
  assert.equal(remainingSeconds({}, result), null);
});
test('config loads coordinates and schematic from one atomic response', async t => {
  const calls = [];
  t.mock.method(globalThis, 'fetch', async url => {
    calls.push(url);
    return new Response(JSON.stringify({ generation: 'same', network, layout: { stations: {} } }));
  });
  assert.equal((await api.config()).generation, 'same');
  assert.deepEqual(calls, ['/api/v1/map-config']);
});
test('departures encode parameters and retain empty-window status', async t => {
  t.mock.method(globalThis, 'fetch', async url => {
    assert.equal(url, '/api/v1/departures?route=1&at=2026-09-11T12%3A00%3A00Z');
    return new Response(JSON.stringify({ message: 'No trains' }), { status: 404 });
  });
  await assert.rejects(api.departures('1', '2026-09-11T12:00:00Z'), error => error instanceof ApiError && error.status === 404);
});
