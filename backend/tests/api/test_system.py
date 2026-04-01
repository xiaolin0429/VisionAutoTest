from __future__ import annotations

from tests.support.runtime import app_client

def test_healthz():
    with app_client(reset=True) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "ok"

def test_demo_acceptance_target_page_is_served():
    with app_client(reset=True) as client:
        response = client.get("/demo/acceptance-target")
        assert response.status_code == 200
        assert "VisionAutoTest Demo Target" in response.text
        assert "data-testid=\"cta-open-form\"" in response.text
        assert "data-testid=\"submit-button\"" in response.text
        assert "data-testid=\"name-input\"" in response.text
        assert "data-testid=\"demo-form\" hidden" not in response.text
        assert "data-testid=\"scroll-container\"" in response.text
        assert "data-testid=\"long-press-target\"" in response.text
