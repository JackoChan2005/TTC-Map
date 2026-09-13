"""Security headers applied to API and static frontend responses."""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response

SECURITY_HEADERS = {
    "Content-Security-Policy": "; ".join(
        [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' https://fonts.googleapis.com",
            "font-src https://fonts.gstatic.com",
            "img-src 'self' data: https://tile.openstreetmap.org",
            "connect-src 'self'",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'self'",
        ]
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    # Public map tiles require an identifying origin referrer; no path/query leaks.
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


async def security_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Add the common browser hardening headers to every response."""
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    return response
