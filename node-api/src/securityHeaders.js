// Security headers for every response. Single concern: nothing here knows
// about routes, rendering, or data.
//
// CSP notes: pages use external stylesheets and module scripts only (no
// inline styles/scripts), so no 'unsafe-inline' is required. Fonts are
// pinned to Google Fonts; everything else is same-origin.

const SECURITY_HEADERS = Object.freeze({
  'Content-Security-Policy': [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' https://fonts.googleapis.com",
    "font-src https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'self'"
  ].join('; '),
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'SAMEORIGIN',
  'Referrer-Policy': 'no-referrer'
});

const securityHeaders = () => (_req, res, next) => {
  for (const [name, value] of Object.entries(SECURITY_HEADERS)) {
    res.setHeader(name, value);
  }
  next();
};

module.exports = {
  securityHeaders,
  SECURITY_HEADERS
};
