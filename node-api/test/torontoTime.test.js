const test = require('node:test');
const assert = require('node:assert');

const { getServiceWindows, getTorontoParts } = require('../src/map/torontoTime');

test('daytime instant maps to Toronto clock seconds and weekday', () => {
  // 2026-06-10T15:00:00Z is 11:00:00 EDT on a Wednesday
  const parts = getTorontoParts(new Date('2026-06-10T15:00:00Z'));
  assert.strictEqual(parts.weekday, 'wednesday');
  assert.strictEqual(parts.sec, 11 * 3600);
});

test('service windows include the previous day shifted by 24h', () => {
  // 2026-06-11T05:30:00Z is 01:30:00 EDT Thursday — late-night service
  // is encoded as 25:30:00 on Wednesday in GTFS
  const windows = getServiceWindows(new Date('2026-06-11T05:30:00Z'));
  assert.deepStrictEqual(windows[0], { day: 'thursday', sec: 5400 });
  assert.deepStrictEqual(windows[1], { day: 'wednesday', sec: 5400 + 86400 });
});
