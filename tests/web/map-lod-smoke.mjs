import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { launchBrowser } from './browser.js';
const browser = await launchBrowser();
const network = JSON.parse(await fs.readFile('shared/network.json', 'utf8'));
const layout = JSON.parse(await fs.readFile('shared/layouts/schematic.json', 'utf8'));
const line = network.lines[0];
const interchangeCount = Object.values(network.stations).filter(station => station.lines.length > 1).length;
const output = 'data/ui-validation';
const errors = [], report = [];
let tilesFail = false;
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on('pageerror', error => errors.push(error.message));
  await page.route('https://tile.openstreetmap.org/**', route => tilesFail
    ? route.fulfill({ status: 503, body: 'Intentional test outage' })
    : route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64') }));
  await page.route('**/api/v1/**', route => {
    const endpoint = new URL(route.request().url()).pathname;
    const send = body => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
    if (endpoint.endsWith('/map-config')) return send({ generation: 'zoom-test-only', network, layout });
    if (endpoint.endsWith('/map-state')) return send({
      generation: 'zoom-test-only', generatedAt: new Date().toISOString(), source: 'ntas',
      lineSources: { [line.id]: { source: 'ntas' } },
      trains: [
        { line: line.id, at: line.stations[10], direction: 0 },
        { line: line.id, at: line.stations[10], direction: 1 },
        { line: line.id, at: line.stations[0] }
      ]
    });
    return send({ matches: [] });
  });
  const settled = () => page.waitForFunction(() => document.querySelector('.station-dot') && document.getElementById('source-status').textContent.includes('positions'));
  const checkLabels = async () => {
    const boxes = await page.locator('.station-label').evaluateAll(nodes => nodes.map(node => {
      const b = node.getBoundingClientRect(); return { text: node.textContent, x: b.x, y: b.y, w: b.width, h: b.height };
    }));
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j];
      assert.ok(a.x + a.w <= b.x + .5 || b.x + b.w <= a.x + .5 || a.y + a.h <= b.y + .5 || b.y + b.h <= a.y + .5,
        'Overlapping labels: ' + a.text + ' / ' + b.text);
    }
    return boxes.length;
  };
  for (const viewport of [{ width: 1440, height: 900 }, { width: 768, height: 1024 }, { width: 390, height: 844 }, { width: 320, height: 640 }]) {
    await page.setViewportSize(viewport);
    await page.goto(process.env.TTCMAP_URL || 'http://127.0.0.1:8000/');
    await settled();
    assert.equal(await page.locator('.station-label[data-interchange="true"]').count(), interchangeCount, 'All fitted interchanges labelled at ' + viewport.width);
    const fittedLabels = await checkLabels();
    await page.screenshot({ path: output + '/lod-fixture-fit-' + viewport.width + '.png' });
    for (let i = 0; i < 8; i++) {
      await page.locator('#zoom-out').click();
      await checkLabels();
      assert.equal(await page.locator('.station-label[data-interchange="true"]').count(), interchangeCount, 'Interchange retained at every outward step');
    }
    assert.equal(await page.locator('#map').getAttribute('data-detail'), 'wide');
    assert.equal(await page.locator('.map-station[data-interchange="false"]').count(), 0);
    assert.equal(await page.locator('.station-label').count(), interchangeCount);
    assert.ok(await page.locator('.train-marker').count() > 0);
    const wideWidths = await page.locator('.train-glyph').evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().width));
    assert.ok(wideWidths.every(width => width >= 5 && width < 20));
    await page.screenshot({ path: output + '/lod-fixture-wide-' + viewport.width + '.png' });
    await page.locator('#fit-map').click();
    for (let i = 0; i < 24 && await page.locator('#map').getAttribute('data-detail') !== 'detail'; i++) {
      await page.locator('#zoom-in').click(); await checkLabels();
    }
    assert.equal(await page.locator('#map').getAttribute('data-detail'), 'detail');
    const detailedLabels = await page.locator('.station-label').allTextContents();
    assert.ok(detailedLabels.some(text => text.includes(' · ')));
    const closeWidths = await page.locator('.train-glyph').evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().width));
    assert.ok(closeWidths.every(width => width >= 5 && width < 24));
    await page.screenshot({ path: output + '/lod-fixture-detail-' + viewport.width + '.png' });
    report.push({ viewport, fittedLabels, interchanges: interchangeCount, wide: 'passed', detailedLabels: detailedLabels.length });
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(process.env.TTCMAP_URL || 'http://127.0.0.1:8000/');
  await settled();
  const directions = await page.locator('.train-marker').evaluateAll(nodes => nodes.map(node => ({ direction: node.dataset.direction, angle: node.dataset.angle })));
  assert.ok(directions.some(train => train.direction === '0' && train.angle !== ''));
  assert.ok(directions.some(train => train.direction === '1' && train.angle !== ''));
  assert.ok(directions.some(train => train.direction === 'unknown' && train.angle === ''));
  tilesFail = true;
  await page.reload();
  await settled();
  await page.waitForFunction(() => document.getElementById('basemap-status').textContent.includes('unavailable'));
  assert.ok(await page.locator('.station-dot').count() > 0);
  assert.ok(await page.locator('.train-marker').count() > 0);
  assert.deepEqual(errors, []);
  await fs.writeFile(output + '/lod-report.json', JSON.stringify({ report, errors, directionFallback: 'passed', tileOutage: 'passed' }, null, 2));
  console.log(report);
} finally { await browser.close(); }
