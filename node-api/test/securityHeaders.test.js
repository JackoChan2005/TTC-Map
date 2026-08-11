const test = require('node:test');
const assert = require('node:assert');

const { securityHeaders, SECURITY_HEADERS } = require('../src/securityHeaders');

const runMiddleware = () => {
  const headers = {};
  const res = { setHeader: (name, value) => { headers[name] = value; } };
  let nextCalled = false;
  securityHeaders()({}, res, () => { nextCalled = true; });
  return { headers, nextCalled };
};

test('sets every security header and calls next', () => {
  const { headers, nextCalled } = runMiddleware();
  assert.strictEqual(nextCalled, true);
  for (const name of Object.keys(SECURITY_HEADERS)) {
    assert.ok(headers[name], `missing ${name}`);
  }
});

test('CSP blocks plugins, framing by others, and off-origin scripts', () => {
  const { headers } = runMiddleware();
  const csp = headers['Content-Security-Policy'];
  assert.match(csp, /object-src 'none'/);
  assert.match(csp, /frame-ancestors 'self'/);
  assert.match(csp, /script-src 'self'(;|$)/);
  assert.ok(!csp.includes("unsafe-inline"), 'CSP must not allow inline code');
  assert.ok(!csp.includes('unsafe-eval'), 'CSP must not allow eval');
});

test('nosniff and referrer policy are pinned', () => {
  const { headers } = runMiddleware();
  assert.strictEqual(headers['X-Content-Type-Options'], 'nosniff');
  assert.strictEqual(headers['Referrer-Policy'], 'no-referrer');
});
