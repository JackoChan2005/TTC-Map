"""Browser security policy for API and static frontend responses."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ttcmap.app import create_app
from ttcmap.security import SECURITY_HEADERS, security_headers


def make_client() -> TestClient:
    app = FastAPI()
    app.middleware("http")(security_headers)

    @app.get("/probe")
    def probe() -> dict:
        return {"status": "ok"}

    return TestClient(app)


def test_sets_every_security_header():
    response = make_client().get("/probe")

    assert response.status_code == 200
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value


def test_csp_blocks_plugins_framing_and_off_origin_scripts():
    csp = make_client().get("/probe").headers["Content-Security-Policy"]

    assert "object-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp
    assert "script-src 'self'" in csp
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp


def test_nosniff_and_referrer_policy_are_pinned():
    headers = make_client().get("/probe").headers

    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    csp = headers["Content-Security-Policy"]
    assert "img-src 'self' data: https://tile.openstreetmap.org" in csp
    assert "connect-src 'self'" in headers["Content-Security-Policy"]


def test_old_map_url_redirects_to_schematic_homepage():
    response = TestClient(create_app()).get("/map/", follow_redirects=False)

    assert response.status_code in {302, 307}
    assert response.headers["location"] == "/"
    assert response.headers["Content-Security-Policy"] == SECURITY_HEADERS[
        "Content-Security-Policy"
    ]
