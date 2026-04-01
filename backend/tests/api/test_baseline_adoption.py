from __future__ import annotations

import pytest
pytestmark = pytest.mark.vision

from tests.support.constants import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME, TINY_PNG_BYTES
from tests.support.api_helpers import _create_media_object, _create_template
from tests.support.fakes import _install_visual_browser_adapter
from tests.support.runtime import _reset_local_data, app_client

def test_failure_evidence_can_be_adopted_as_new_baseline(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.models import BaselineRevision, Template

    _install_visual_browser_adapter(monkeypatch, template_status="failed")

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "baseline_adopt_ws", "workspace_name": "Baseline Adopt WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_adopt_source",
            template_name="Adopt Source Template",
        )

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_adopt_source", "case_name": "Adopt Source Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "template_assert",
                    "step_name": "Adopt Source Step",
                    "template_id": template_id,
                    "payload_json": {},
                }
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_adopt_source", "suite_name": "Adopt Source Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-baseline-adopt"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        case_run_id = case_runs_resp.json()["data"][0]["id"]
        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_result = step_results_resp.json()["data"][0]
        report_resp = client.get(f"/api/v1/test-runs/{test_run_id}/report", headers=workspace_headers)
        report_id = report_resp.json()["data"]["id"]

        adopt_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions",
            headers=workspace_headers,
            json={
                "media_object_id": step_result["actual_media_object_id"],
                "source_type": "adopted_from_failure",
                "source_report_id": report_id,
                "source_case_run_id": case_run_id,
                "source_step_result_id": step_result["id"],
                "remark": "accept latest screenshot",
                "is_current": True,
            },
        )
        assert adopt_resp.status_code == 201
        baseline = adopt_resp.json()["data"]
        assert baseline["source_type"] == "adopted_from_failure"
        assert baseline["source_report_id"] == report_id
        assert baseline["source_case_run_id"] == case_run_id
        assert baseline["source_step_result_id"] == step_result["id"]
        assert baseline["media_object_id"] == step_result["actual_media_object_id"]

        with SessionLocal() as db:
            template = db.get(Template, template_id)
            assert template is not None
            assert template.current_baseline_revision_id == baseline["id"]
            revisions = db.query(BaselineRevision).filter(BaselineRevision.template_id == template_id).order_by(BaselineRevision.revision_no.asc()).all()
            assert revisions[-1].source_report_id == report_id
            assert revisions[-1].source_case_run_id == case_run_id
            assert revisions[-1].source_step_result_id == step_result["id"]
            assert revisions[-1].is_current is True
            assert revisions[0].is_current is False

def test_baseline_adoption_rejects_mismatched_failure_chain(monkeypatch):
    _reset_local_data()

    _install_visual_browser_adapter(monkeypatch, template_status="failed")

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "baseline_mismatch_ws", "workspace_name": "Baseline Mismatch WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        media_object_id = _create_media_object(client, headers=workspace_headers)
        source_template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_mismatch_source",
            template_name="Mismatch Source Template",
        )
        other_media_resp = client.post(
            "/api/v1/media-objects",
            headers=workspace_headers,
            data={"usage": "artifact"},
            files={"file": ("other-baseline.png", TINY_PNG_BYTES + b"-other-template", "image/png")},
        )
        assert other_media_resp.status_code == 201
        other_media_object_id = other_media_resp.json()["data"]["id"]
        target_template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=other_media_object_id,
            template_code="tpl_mismatch_target",
            template_name="Mismatch Target Template",
        )

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_mismatch_source", "case_name": "Mismatch Source Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "template_assert",
                    "step_name": "Mismatch Step",
                    "template_id": source_template_id,
                    "payload_json": {},
                }
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_mismatch_source", "suite_name": "Mismatch Source Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-baseline-mismatch"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        case_run_id = case_runs_resp.json()["data"][0]["id"]
        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_result = step_results_resp.json()["data"][0]

        mismatch_resp = client.post(
            f"/api/v1/templates/{target_template_id}/baseline-revisions",
            headers=workspace_headers,
            json={
                "media_object_id": step_result["actual_media_object_id"],
                "source_type": "adopted_from_failure",
                "source_step_result_id": step_result["id"],
                "is_current": True,
            },
        )
        assert mismatch_resp.status_code == 422
        assert mismatch_resp.json()["error"]["code"] == "BASELINE_ADOPTION_MISMATCH"

def test_baseline_adoption_rejects_diff_media_object(monkeypatch):
    _reset_local_data()

    _install_visual_browser_adapter(monkeypatch, template_status="failed")

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "baseline_diff_ws", "workspace_name": "Baseline Diff WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_diff_source",
            template_name="Diff Source Template",
        )

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_diff_source", "case_name": "Diff Source Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "template_assert",
                    "step_name": "Diff Step",
                    "template_id": template_id,
                    "payload_json": {},
                }
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_diff_source", "suite_name": "Diff Source Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-baseline-diff"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        case_run_id = case_runs_resp.json()["data"][0]["id"]
        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_result = step_results_resp.json()["data"][0]

        invalid_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions",
            headers=workspace_headers,
            json={
                "media_object_id": step_result["diff_media_object_id"],
                "source_type": "adopted_from_failure",
                "source_step_result_id": step_result["id"],
                "is_current": True,
            },
        )
        assert invalid_resp.status_code == 422
        assert invalid_resp.json()["error"]["code"] == "BASELINE_ADOPTION_INVALID"

def test_baseline_adoption_rejects_cross_workspace_media_object(monkeypatch):
    _reset_local_data()

    _install_visual_browser_adapter(monkeypatch, template_status="failed")

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "baseline_cross_ws", "workspace_name": "Baseline Cross WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_cross_ws",
            template_name="Cross Workspace Template",
        )

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_cross_ws", "case_name": "Cross Workspace Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "template_assert",
                    "step_name": "Cross Workspace Step",
                    "template_id": template_id,
                    "payload_json": {},
                }
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_cross_ws", "suite_name": "Cross Workspace Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        other_workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "baseline_cross_other_ws", "workspace_name": "Baseline Cross Other WS"},
            headers=headers,
        )
        other_workspace_id = other_workspace_resp.json()["data"]["id"]
        other_workspace_headers = headers | {"X-Workspace-Id": str(other_workspace_id)}
        foreign_media_object_id = _create_media_object(client, headers=other_workspace_headers)

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-baseline-cross"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        case_run_id = case_runs_resp.json()["data"][0]["id"]
        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_result = step_results_resp.json()["data"][0]

        cross_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions",
            headers=workspace_headers,
            json={
                "media_object_id": foreign_media_object_id,
                "source_type": "adopted_from_failure",
                "source_step_result_id": step_result["id"],
                "is_current": True,
            },
        )
        assert cross_resp.status_code == 404
        assert cross_resp.json()["error"]["code"] == "MEDIA_OBJECT_NOT_FOUND"
