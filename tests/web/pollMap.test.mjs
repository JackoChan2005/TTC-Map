import test from 'node:test';
import assert from 'node:assert/strict';
import { createMapPoller } from '../../web/js/pollMap.js';

test('reloads topology before applying a new-generation state', async () => {
  const events = [];
  const configs = [{generation:'a'}, {generation:'b'}];
  const poll = createMapPoller({fetchConfig: async () => configs.shift(),
    fetchState: async () => ({generation:'b'}),
    onConfig: c => events.push('config-'+c.generation),
    onState: s => events.push('state-'+s.generation)});
  await poll();
  assert.deepEqual(events, ['config-a','config-b','state-b']);
});

test('discards state when config changes again during reload', async () => {
  const configs = [{generation:'a'}, {generation:'c'}];
  let rendered = false;
  const poll = createMapPoller({fetchConfig: async () => configs.shift(),
    fetchState: async () => ({generation:'b'}), onConfig: () => {},
    onState: () => { rendered = true; }});
  await assert.rejects(poll(), /matching update/);
  assert.equal(rendered, false);
});

test('serializes refresh calls so slow responses cannot arrive out of order', async () => {
  let release;
  let requests=0;
  const pending = new Promise(resolve => {release=resolve;});
  const poll = createMapPoller({fetchConfig: async () => ({generation:'a'}),
    fetchState: async () => {requests++; await pending; return {generation:'a'};},
    onConfig: () => {}, onState: () => {}});
  const first=poll();
  await Promise.resolve(); await Promise.resolve();
  await poll();
  release(); await first;
  assert.equal(requests, 1);
});
