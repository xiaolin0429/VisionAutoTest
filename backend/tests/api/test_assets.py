from __future__ import annotations

import pytest
from tests.support.constants import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME
from tests.support.api_helpers import _create_media_object, _create_template, _get_template_current_baseline_revision_id
from tests.support.fakes import _install_template_workbench_adapter
from tests.support.runtime import _reset_local_data, app_client

def test_template_create_rejects_unsupported_match_strategy():
    with app_client(reset=True) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "unsupported_strategy_ws", "workspace_name": "Unsupported Strategy WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        media_object_id = _create_media_object(client, headers=workspace_headers)
        response = client.post(
            "/api/v1/templates",
            headers=workspace_headers,
            json={
                "template_code": "tpl_orb",
                "template_name": "ORB Template",
                "template_type": "page",
                "match_strategy": "orb",
                "threshold_value": 0.95,
                "status": "draft",
                "original_media_object_id": media_object_id,
            },
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "TEMPLATE_MATCH_STRATEGY_UNSUPPORTED"

@pytest.mark.vision
def test_template_ocr_analysis_persists_snapshot_and_can_be_read(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.models import TemplateOCRResult

    _install_template_workbench_adapter(monkeypatch)

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_ocr_ws", "workspace_name": "Template OCR WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_ocr_snapshot",
            template_name="OCR Snapshot Template",
        )
        baseline_revision_id = _get_template_current_baseline_revision_id(client, headers=workspace_headers, template_id=template_id)

        create_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results",
            headers=workspace_headers,
        )
        assert create_resp.status_code == 201
        payload = create_resp.json()["data"]
        assert payload["status"] == "succeeded"
        assert payload["engine_name"] == "paddleocr"
        assert payload["image_width"] == 200
        assert payload["image_height"] == 100
        assert payload["blocks"][0]["text"] == "VisionAutoTest"
        assert payload["blocks"][0]["ratio_rect"]["x_ratio"] == 0.1

        get_resp = client.get(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results",
            headers=workspace_headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["id"] == payload["id"]

        with SessionLocal() as db:
            snapshots = db.query(TemplateOCRResult).filter(TemplateOCRResult.template_id == template_id).all()
            assert len(snapshots) == 1
            assert snapshots[0].baseline_revision_id == baseline_revision_id

@pytest.mark.vision
def test_template_ocr_analysis_rerun_updates_same_snapshot(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.models import TemplateOCRResult

    _install_template_workbench_adapter(
        monkeypatch,
        analyses=[
            {
                "engine_name": "paddleocr",
                "image_width": 200,
                "image_height": 100,
                "blocks": [
                    {
                        "order_no": 1,
                        "text": "first-run",
                        "confidence": 0.91,
                        "polygon_points": [{"x": 10, "y": 10}, {"x": 60, "y": 10}, {"x": 60, "y": 24}, {"x": 10, "y": 24}],
                        "pixel_rect": {"x": 10, "y": 10, "width": 50, "height": 14},
                        "ratio_rect": {"x_ratio": 0.05, "y_ratio": 0.1, "width_ratio": 0.25, "height_ratio": 0.14},
                    }
                ],
            },
            {
                "engine_name": "paddleocr",
                "image_width": 200,
                "image_height": 100,
                "blocks": [
                    {
                        "order_no": 1,
                        "text": "second-run",
                        "confidence": 0.95,
                        "polygon_points": [{"x": 20, "y": 20}, {"x": 80, "y": 20}, {"x": 80, "y": 40}, {"x": 20, "y": 40}],
                        "pixel_rect": {"x": 20, "y": 20, "width": 60, "height": 20},
                        "ratio_rect": {"x_ratio": 0.1, "y_ratio": 0.2, "width_ratio": 0.3, "height_ratio": 0.2},
                    }
                ],
            },
        ],
    )

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_ocr_rerun_ws", "workspace_name": "Template OCR Rerun WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_ocr_rerun",
            template_name="OCR Rerun Template",
        )
        baseline_revision_id = _get_template_current_baseline_revision_id(client, headers=workspace_headers, template_id=template_id)

        first_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results",
            headers=workspace_headers,
        )
        second_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results",
            headers=workspace_headers,
        )

        assert first_resp.status_code == 201
        assert second_resp.status_code == 201
        assert first_resp.json()["data"]["id"] == second_resp.json()["data"]["id"]
        assert second_resp.json()["data"]["blocks"][0]["text"] == "second-run"

        with SessionLocal() as db:
            snapshots = db.query(TemplateOCRResult).filter(TemplateOCRResult.template_id == template_id).all()
            assert len(snapshots) == 1
            assert snapshots[0].result_json["blocks"][0]["text"] == "second-run"

@pytest.mark.vision
def test_template_ocr_missing_snapshot_returns_not_generated_placeholder(monkeypatch):
    _reset_local_data()

    _install_template_workbench_adapter(monkeypatch)

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_ocr_missing_ws", "workspace_name": "Template OCR Missing WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_ocr_missing",
            template_name="OCR Missing Template",
        )
        baseline_revision_id = _get_template_current_baseline_revision_id(client, headers=workspace_headers, template_id=template_id)

        response = client.get(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results",
            headers=workspace_headers,
        )
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["status"] == "not_generated"
        assert payload["error_code"] == "TEMPLATE_OCR_RESULT_NOT_FOUND"
        assert payload["blocks"] == []
        assert payload["id"] is None

@pytest.mark.vision
def test_template_ocr_failure_persists_failed_snapshot(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.models import TemplateOCRResult

    _install_template_workbench_adapter(monkeypatch, ocr_error="ocr engine unavailable")

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_ocr_fail_ws", "workspace_name": "Template OCR Fail WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_ocr_fail",
            template_name="OCR Fail Template",
        )
        baseline_revision_id = _get_template_current_baseline_revision_id(client, headers=workspace_headers, template_id=template_id)

        create_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results",
            headers=workspace_headers,
        )
        assert create_resp.status_code == 500
        assert create_resp.json()["error"]["code"] == "TEMPLATE_OCR_ANALYSIS_FAILED"

        get_resp = client.get(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results",
            headers=workspace_headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["status"] == "failed"
        assert get_resp.json()["data"]["error_code"] == "TEMPLATE_OCR_ANALYSIS_FAILED"
        assert get_resp.json()["data"]["blocks"] == []

        with SessionLocal() as db:
            snapshot = db.query(TemplateOCRResult).filter(TemplateOCRResult.template_id == template_id).one()
            assert snapshot.status == "failed"
            assert snapshot.error_code == "TEMPLATE_OCR_ANALYSIS_FAILED"

@pytest.mark.vision
def test_template_preview_uses_persisted_masks_when_request_omitted(monkeypatch):
    _reset_local_data()

    _install_template_workbench_adapter(monkeypatch)

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_preview_ws", "workspace_name": "Template Preview WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_preview_saved",
            template_name="Preview Saved Template",
        )
        baseline_revision_id = _get_template_current_baseline_revision_id(client, headers=workspace_headers, template_id=template_id)

        mask_resp = client.post(
            f"/api/v1/templates/{template_id}/mask-regions",
            headers=workspace_headers,
            json={"region_name": "saved_mask", "x_ratio": 0.1, "y_ratio": 0.2, "width_ratio": 0.3, "height_ratio": 0.2, "sort_order": 1},
        )
        assert mask_resp.status_code == 201

        preview_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/preview-images",
            headers=workspace_headers,
            json={},
        )
        assert preview_resp.status_code == 201
        payload = preview_resp.json()["data"]
        assert payload["image_width"] == 200
        assert payload["image_height"] == 100
        assert payload["mask_regions"][0]["name"] == "saved_mask"
        assert payload["overlay_content_url"].endswith(f"/api/v1/media-objects/{payload['overlay_media_object_id']}/content")
        assert payload["processed_content_url"].endswith(f"/api/v1/media-objects/{payload['processed_media_object_id']}/content")

        overlay_resp = client.get(payload["overlay_content_url"], headers=workspace_headers)
        processed_resp = client.get(payload["processed_content_url"], headers=workspace_headers)
        assert overlay_resp.status_code == 200
        assert processed_resp.status_code == 200

@pytest.mark.vision
def test_template_preview_draft_masks_do_not_persist(monkeypatch):
    _reset_local_data()

    _install_template_workbench_adapter(monkeypatch)

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_preview_draft_ws", "workspace_name": "Template Preview Draft WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_preview_draft",
            template_name="Preview Draft Template",
        )
        baseline_revision_id = _get_template_current_baseline_revision_id(client, headers=workspace_headers, template_id=template_id)

        preview_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/preview-images",
            headers=workspace_headers,
            json={
                "mask_regions": [
                    {"name": "draft_1", "x_ratio": 0.05, "y_ratio": 0.1, "width_ratio": 0.2, "height_ratio": 0.2, "sort_order": 2},
                    {"x_ratio": 0.4, "y_ratio": 0.2, "width_ratio": 0.1, "height_ratio": 0.1, "sort_order": 1},
                ]
            },
        )
        assert preview_resp.status_code == 201
        payload = preview_resp.json()["data"]
        assert len(payload["mask_regions"]) == 2
        assert payload["mask_regions"][0]["name"] == "mask_region_2"
        assert payload["mask_regions"][1]["name"] == "draft_1"

        list_resp = client.get(f"/api/v1/templates/{template_id}/mask-regions", headers=workspace_headers)
        assert list_resp.status_code == 200
        assert list_resp.json()["data"] == []
