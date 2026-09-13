import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { launchBrowser } from './browser.js';

// Optional browser tooling is locked in tests/web/package-lock.json.
const browser = await launchBrowser();
const base = process.env.TTCMAP_URL || 'http://127.0.0.1:8000';
const output = 'data/ui-validation';
await fs.mkdir(output, { recursive: true });
const errors = [], consoleErrors = [], requests = [], failures = [];
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
// Pan/zoom regression tests must not scan the public OSM tile service.
// The separate fixed-viewport basemap-live check verifies real map imagery.
await context.route('https://tile.openstreetmap.org/**', route => route.fulfill({
  contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64')
}));
const page = await context.newPage();
page.on('pageerror', error => errors.push(error.message));
page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
page.on('request', request => { if (request.url().includes('/api/')) requests.push(new URL(request.url()).pathname); });
page.on('requestfailed', request => failures.push(request.url()));
const visible = selector => page.locator(selector).first().waitFor({ state: 'visible' });
const noOverflow = async () => assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
const routes = ['/', '/index.html', '/search', '/search/', '/search/index.html', '/map', '/map/'];
const report = { realRoutes: [], fixtureRoutes: [], checks: [] };
try {
  // Use real transit responses first; only map tiles are intercepted.
  for (const route of routes) {
    const response = await page.goto(base + route);
    assert.equal(response.status(), 200, route);
    await page.waitForFunction(() => document.getElementById('source-status').textContent !== 'Connecting to transit data');
    await noOverflow();
    report.realRoutes.push({ route, url: new URL(page.url()).pathname, status: await page.locator('#source-status').textContent() });
  }
  await page.goto(base);
  await page.waitForFunction(() => document.getElementById('source-status').textContent !== 'Connecting to transit data');
  if ((await page.locator('#source-status').textContent()) === 'Transit data unavailable') assert.equal(await page.locator('.train-marker').count(), 0);
  await page.screenshot({ path: output + '/real-backend-desktop.png' });
  await page.locator('[data-dialog="alerts"]').click();
  await visible('#info-dialog');
  await page.waitForFunction(() => !document.getElementById('dialog-content').textContent.includes('Checking'));
  await page.keyboard.press('Escape');
  report.checks.push('Real backend startup, actual availability state, health diagnostics, all direct routes');
  const realConfigResponse = await context.request.get(base + '/api/v1/map-config');
  if (realConfigResponse.ok()) {
    const realConfig = await realConfigResponse.json();
    const realState = await (await context.request.get(base + '/api/v1/map-state')).json();
    report.realData = { generation: realConfig.generation, stations: Object.keys(realConfig.network.stations).length,
      source: realState.source, trainCount: realState.trainCount, lineSources: realState.lineSources, departures: [] };
    for (const item of realConfig.network.lines) {
      const url = '/?line=' + encodeURIComponent(item.number) + '&station=' + encodeURIComponent(item.stations[0]);
      await page.goto(base + url);
      await visible('.station-info');
      await page.waitForFunction(() => !document.querySelector('.station-info').textContent.includes('Loading'));
      assert.equal(await page.locator('.timeline li').count(), item.stations.length);
      await page.goto(base + '/search/?line=' + encodeURIComponent(item.number));
      await page.waitForFunction(() => !document.getElementById('search-btn').disabled);
      const responsePromise = page.waitForResponse(response => response.url().includes('/api/v1/departures?'));
      await page.locator('#search-btn').click();
      const response = await responsePromise;
      assert.ok([200, 404].includes(response.status()));
      await page.waitForFunction(() => !document.getElementById('search-btn').disabled);
      report.realData.departures.push({ line: item.number, status: response.status(), cards: await page.locator('.departure-card').count() });
      report.realRoutes.push({ route: url, status: 'Rendered actual API topology and timetable' });
    }
    report.checks.push('Actual published topology, station details, and timetable searches across all five lines');
  }

  // Explicit browser-only fixtures: committed topology/layout, synthetic train
  // and departure records for UI behavior. Never copied into web/ or served.
  const network = JSON.parse(await fs.readFile('shared/network.json', 'utf8'));
  const schematic = JSON.parse(await fs.readFile('shared/layouts/schematic.json', 'utf8'));
  const line = network.lines[0], station = line.stations[2];
  const platformId = Object.keys(network.platforms).find(id => network.platforms[id].station === station && network.platforms[id].line === line.id && network.platforms[id].direction === 0);
  let mode = 'normal', departureMode = 'normal', geoFailure = false, healthFailure = false;
  const fixtureState = () => ({
    generation: 'ui-test-fixture', generatedAt: new Date().toISOString(), source: 'mixed',
    lineSources: Object.fromEntries(network.lines.map((line, index) => [line.id, { source: index < 3 ? 'ntas' : 'schedule', reason: index < 3 ? null : 'realtime_not_enabled' }])),
    trains: mode === 'empty' ? [] : network.lines.flatMap(line => [
      { line: line.id, direction: 0, at: line.stations[2], stationName: network.stations[line.stations[2]].name },
      { line: line.id, direction: 1, between: [line.stations[4], line.stations[3]], progress: .5, stationName: network.stations[line.stations[3]].name }
    ])
  });
  await context.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url()), endpoint = url.pathname;
    const send = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (mode === 'failure' && endpoint.endsWith('/map-state')) return send({ message: 'Intentional test outage' }, 503);
    if (endpoint.endsWith('/map-config')) {
      const data = structuredClone(network);
      if (geoFailure) delete data.stations[Object.keys(data.stations)[0]].lat;
      return send({ generation: 'ui-test-fixture', network: data, layout: schematic });
    }
    if (endpoint.endsWith('/map-state')) return send(mode === 'optional' ? { generation: 'ui-test-fixture', source: 'schedule' } : fixtureState());
    if (endpoint.endsWith('/departures')) {
      if (departureMode === 'failure') return send({ message: 'Intentional test outage' }, 503);
      if (departureMode === '404') return send({ message: 'No trains' }, 404);
      if (departureMode === 'empty') return send({ matches: [], requestedAt: new Date().toISOString() });
      if (departureMode === 'optional') return send({ matches: [{}], requestedAt: new Date().toISOString() });
      assert.ok(['1', '2', '4', '5', '6'].includes(url.searchParams.get('route')));
      return send({ requestedAt: new Date().toISOString(), totalMatches: 1, matches: [{ deltaSeconds: 60, payload: {
        stop_id: platformId, direction_id: 0, line_id: line.id, route_id: line.routeId, departure_time: '12:01:00'
      } }] });
    }
    if (endpoint.endsWith('/health')) return healthFailure ? send({ message: 'Intentional test outage' }, 503) : send({ status: 'ok', gtfs: { ready: true }, realtime: {} });
    throw new Error('Unexpected endpoint: ' + endpoint);
  });
  consoleErrors.length = 0;
  for (const route of routes) {
    await page.goto(base + route);
    await page.waitForFunction(() => document.querySelectorAll('.station-dot').length > 0);
    await noOverflow();
    report.fixtureRoutes.push(route);
  }
  for (const item of network.lines) {
    const route = '/?line=' + encodeURIComponent(item.number);
    await page.goto(base + route);
    await visible('.timeline');
    assert.equal(await page.locator('.timeline li').count(), item.stations.length);
    report.fixtureRoutes.push(route);
  }
  await page.goto(base);
  await visible('.route-card');
  assert.equal(await page.locator('.route-card').count(), 5);
  await page.screenshot({ path: output + '/fixture-overview-desktop.png' });
  await page.getByRole('button', { name: 'Explore Line 1', exact: false }).click();
  await visible('.timeline');
  assert.equal(await page.locator('.timeline li').count(), line.stations.length);
  assert.ok(await page.locator('.dimmed').count() > 0);
  await page.locator('#direction').selectOption('1');
  assert.equal(await page.locator('.station-name').first().textContent(), network.stations[line.stations.at(-1)].name);
  await page.locator('#direction').selectOption('0');
  await page.locator('.station-button').nth(2).click();
  await visible('.station-info');
  await page.waitForFunction(() => document.querySelector('.station-info').textContent.includes('Scheduled in'));
  await page.screenshot({ path: output + '/fixture-route-desktop.png' });
  await page.getByRole('button', { name: 'Transfer to Line 4', exact: true }).click();
  assert.equal(new URL(page.url()).searchParams.get('line'), '4');
  await page.goBack();
  await visible('.station-info');
  await page.goBack();
  assert.equal(new URL(page.url()).searchParams.has('station'), false);
  await page.locator('.back-button').click();
  await page.locator('#network-search').fill('union');
  await visible('.search-result');
  await page.locator('#network-search').press('Enter');
  await visible('.station-info');
  assert.ok((await page.locator('.station-info h3').textContent()).toLowerCase().includes('union'));
  await page.locator('#network-search').fill('no-station-matches-this');
  assert.ok((await page.locator('#search-results').textContent()).includes('No stations'));
  await page.locator('#network-search').fill('');
  const beforeZoom = await page.locator('#map').getAttribute('viewBox');
  await page.locator('#zoom-in').click();
  assert.notEqual(await page.locator('#map').getAttribute('viewBox'), beforeZoom);
  await page.locator('#zoom-out').click();
  await page.locator('#fit-map').click();
  const beforePan = await page.locator('#map').getAttribute('viewBox');
  await page.locator('#map').focus();
  await page.keyboard.press('ArrowRight');
  assert.notEqual(await page.locator('#map').getAttribute('viewBox'), beforePan);
  await page.locator('#map-type').click();
  assert.equal(await page.locator('#map-type').textContent(), 'Map: schematic');
  await page.locator('#map-type').click();
  await page.locator('.back-button').click();
  await page.locator('[data-dialog="settings"]').click();
  await page.getByLabel('Station labels', { exact: true }).uncheck();
  assert.equal(await page.locator('.station-label[data-interchange="false"]').count(), 0);
  assert.ok(await page.locator('.station-label[data-interchange="true"]').count() > 0);
  await page.getByLabel('Station labels', { exact: true }).check();
  assert.ok(await page.locator('.train-marker.estimate').count() > 0);
  await page.getByLabel('Show scheduled train estimates').uncheck();
  assert.equal(await page.locator('.train-marker.estimate').count(), 0);
  await page.getByLabel('Show scheduled train estimates').check();
  await page.getByLabel('Light map appearance').check();
  await page.keyboard.press('Escape');
  await page.locator('[data-dialog="about"]').click();
  await visible('#info-dialog');
  await page.locator('#close-dialog').click();
  healthFailure = true;
  await page.locator('[data-dialog="alerts"]').click();
  await page.waitForFunction(() => document.getElementById('dialog-content').textContent.includes('temporarily unavailable'));
  await page.keyboard.press('Escape');
  healthFailure = false;
  await page.locator('#departures-tab').click();
  await visible('#search-form');
  await page.locator('#route').selectOption('1');
  await page.locator('#now-btn').click();
  await page.locator('#search-btn').click();
  await visible('.departure-card');
  await page.locator('.departure-card summary').click();
  await visible('.departure-card pre');
  for (const value of ['404', 'empty', 'failure', 'optional']) {
    departureMode = value;
    await page.locator('#search-btn').click();
    await page.waitForFunction(() => !document.getElementById('search-btn').disabled);
    if (value !== 'optional') assert.equal(await page.locator('.departure-card').count(), 0);
  }
  report.checks.push('Line focus and timeline, directions, station schedules, search/no matches, history, zoom/fit, map type, settings/about dialogs, timetable success/404/empty/503/missing fields');
  for (const size of [{width:390,height:844},{width:320,height:640},{width:768,height:1024},{width:1440,height:900}]) {
    await page.setViewportSize(size);
    await page.goto(base);
    await visible('.route-card');
    await noOverflow();
    await page.screenshot({ path: output + '/fixture-overview-' + size.width + '.png' });
    await page.locator('#collapse-panel').click();
    await page.getByRole('button', { name: 'Expand panel' }).click();
    await page.getByRole('button', { name: 'Explore Line 6', exact: false }).click();
    await visible('.timeline');
    await noOverflow();
    await page.goto(base + '/search/?line=5');
    await visible('#search-form');
    await noOverflow();
  }
  report.checks.push('Desktop/tablet/mobile: 1440×900, 768×1024, 390×844, 320×640; panel collapse/expand and direct route/search states');
  await page.goto(base);
  await visible('.train-marker');
  mode = 'failure';
  await page.locator('#refresh').click();
  await page.waitForFunction(() => document.getElementById('source-status').textContent.includes('unavailable'));
  assert.equal(await page.locator('.train-marker').count(), 0);
  mode = 'empty'; await page.locator('#refresh').click();
  await page.waitForFunction(() => document.getElementById('source-status').textContent.includes('0 positions'));
  mode = 'optional'; await page.locator('#refresh').click();
  await page.waitForFunction(() => document.getElementById('source-status').textContent.startsWith('schedule'));
  geoFailure = true;
  await page.reload();
  await visible('.station-dot');
  assert.equal(await page.locator('#map-type').textContent(), 'Map: schematic');
  assert.equal(await page.locator('#map-type').isDisabled(), true);
  report.checks.push('Train removal after outage, empty and missing optional state fields, missing station coordinates with schematic fallback');
  assert.deepEqual(errors, []);
  const unexpected = consoleErrors.filter(message => !message.includes('Failed to load resource'));
  assert.deepEqual(unexpected, []);
  assert.deepEqual(failures, []);
  assert.ok(!requests.includes('/api/v1/layout/geographic'));
  assert.ok(requests.includes('/api/v1/health'));
  const allowed = ['/api/v1/map-config','/api/v1/map-state','/api/v1/departures','/api/v1/health'];
  assert.ok(requests.every(endpoint => allowed.includes(endpoint)));
  report.endpoints = [...new Set(requests)];
  report.runtimeErrors = errors;
  report.unexpectedConsoleErrors = unexpected;
  report.failedNetworkRequests = failures;
  await fs.writeFile(output + '/report.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
} finally { await browser.close(); }
