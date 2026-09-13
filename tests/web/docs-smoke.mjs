import assert from 'node:assert/strict';
import { launchBrowser } from './browser.js';

const browser = await launchBrowser();
try {
  const base = process.env.TTCMAP_URL || 'http://127.0.0.1:8000';
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.route('**/*', route => new URL(route.request().url()).origin === new URL(base).origin
    ? route.continue() : route.abort());
  for (const route of ['/docs', '/redoc', '/api/', '/api/index.html']) {
    await page.goto(base + route);
    await page.locator('article').first().waitFor();
    const health = page.locator('article').filter({ has: page.getByRole('heading', { name: 'GET /api/v1/health', exact: true }) });
    await health.getByRole('button').click();
    await page.waitForFunction(() => [...document.querySelectorAll('[role=status]')].some(el => el.textContent === 'HTTP 200'));
    assert.ok(await health.locator('pre').first().textContent());
    assert.equal(await page.getByRole('heading', { name: 'GET /api/v1/gtfs/refresh', exact: true }).count(), 0);
  }
  await page.setViewportSize({ width: 320, height: 640 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  assert.deepEqual(errors, []);
  await page.route('**/openapi.json', route => route.fulfill({ status: 200, json: { paths: {} } }));
  await page.reload();
  await page.getByText('No API endpoints are available.').waitFor();
  await page.route('**/openapi.json', route => route.fulfill({ status: 503, json: { message: 'Test outage' } }));
  await page.reload();
  await page.getByText('API schema unavailable:', { exact: false }).waitFor();
  console.log('API reference: all routes, offline assets, GET request, mobile, empty/error states passed.');
} finally { await browser.close(); }
