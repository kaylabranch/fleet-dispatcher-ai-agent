"""Executable API requirements for browser-based human supervision."""

from __future__ import annotations

from fastapi.testclient import TestClient

from server.main import app


def test_browser_interventions_are_allowed_from_the_vite_dev_server() -> None:
    """The dashboard must be able to POST JSON interventions from localhost:5173."""
    with TestClient(app) as client:
        response = client.options(
            "/intervene",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
