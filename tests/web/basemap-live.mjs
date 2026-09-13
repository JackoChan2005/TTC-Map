// One fixed-viewport integration check. No automated panning/zooming or tile
// collection: the public OSM service is not used for the regression suite.
import assert from 'node:assert/strict';
import path from 'node:path';
import fs from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
const { chromium } = await import(pathToFileURL(path.resolve(process.env.PLAYWRIGHT_MODULE || 'data/ui-validation/node_modules/playwright/index.mjs')));
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [], tiles = [], referers = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    if (response.url().startsWith('https://tile.openstreetmap.org/')) tiles.push({ status: response.status(), type: response.headers()['content-type'] });
  });
  page.on('request', request => {
    if (request.url().startsWith('https://tile.openstreetmap.org/')) referers.push(request.headers().referer);
  });
  await page.goto(process.env.TTCMAP_URL || 'http://127.0.0.1:8000/');
  await page.waitForFunction(() => document.querySelector('.basemap-tiles image[data-loaded="true"]'), { timeout: 45000 });
  await page.waitForFunction(() => document.getElementById('basemap-status').hidden, { timeout: 45000 });
  assert.ok(tiles.length > 0 && tiles.every(tile => tile.status === 200 && tile.type?.includes('image/png')));
  assert.ok(referers.length > 0 && referers.every(Boolean));
  assert.deepEqual(errors, []);
  const dir = 'data/ui-validation';
  await fs.mkdir(dir, { recursive: true });
  await page.screenshot({ path: dir + '/real-street-map.png' });
  const report = { tiles: tiles.length, errors, refererPresent: true, detail: await page.locator('#map').getAttribute('data-detail'),
    labels: await page.locator('.station-label').count(), directionalMarkers: await page.locator('.train-marker:not([data-angle=""])').count() };
  await fs.writeFile(dir + '/basemap-live-report.json', JSON.stringify(report, null, 2));
  console.log(report);
} finally { await browser.close(); }
