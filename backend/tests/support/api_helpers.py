from __future__ import annotations

from fastapi.testclient import TestClient

from tests.support.constants import TINY_PNG_BYTES

def _create_media_object(client: TestClient, *, headers: dict[str, str], usage: str = "baseline") -> int:
    response = client.post(
        "/api/v1/media-objects",
        headers=headers,
        data={"usage": usage},
        files={"file": ("baseline.png", TINY_PNG_BYTES, "image/png")},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]

def _create_template(
    client: TestClient,
    *,
    headers: dict[str, str],
    media_object_id: int,
    template_code: str,
    template_name: str,
    match_strategy: str = "template",
    status: str = "published",
) -> int:
    response = client.post(
        "/api/v1/templates",
        headers=headers,
        json={
            "template_code": template_code,
            "template_name": template_name,
            "template_type": "page",
            "match_strategy": match_strategy,
            "threshold_value": 0.95,
            "status": status,
            "original_media_object_id": media_object_id,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]

def _get_template_current_baseline_revision_id(client: TestClient, *, headers: dict[str, str], template_id: int) -> int:
    response = client.get(f"/api/v1/templates/{template_id}", headers=headers)
    assert response.status_code == 200
    baseline_revision_id = response.json()["data"]["current_baseline_revision_id"]
    assert baseline_revision_id is not None
    return baseline_revision_id
