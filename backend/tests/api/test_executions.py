from __future__ import annotations

import pytest
from tests.support.constants import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME
from tests.support.api_helpers import _create_media_object, _create_template
from tests.support.fakes import _install_fake_browser_adapter, _install_noop_dispatcher, _install_visual_browser_adapter
from tests.support.runtime import _reset_local_data, app_client

def test_mvp_backend_smoke_flow(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.models import MediaObject, ReportArtifact, RunReport, StepResult

    _install_fake_browser_adapter(monkeypatch)

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        assert login_resp.status_code == 201
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "mvp_demo", "workspace_name": "MVP Demo"},
            headers=headers,
        )
        assert workspace_resp.status_code == 201
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        assert env_resp.status_code == 201
        environment_profile_id = env_resp.json()["data"]["id"]

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_login", "case_name": "Login Case", "status": "published"},
            headers=workspace_headers,
        )
        assert case_resp.status_code == 201
        test_case_id = case_resp.json()["data"]["id"]

        steps_resp = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "wait", "step_name": "Wait Render", "payload_json": {"ms": 100}}],
            headers=workspace_headers,
        )
        assert steps_resp.status_code == 200

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_smoke", "suite_name": "Smoke Suite", "status": "active"},
            headers=workspace_headers,
        )
        assert suite_resp.status_code == 201
        test_suite_id = suite_resp.json()["data"]["id"]

        suite_cases_resp = client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )
        assert suite_cases_resp.status_code == 200

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-001"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers=workspace_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "passed"

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        assert case_runs_resp.status_code == 200
        case_runs = case_runs_resp.json()["data"]
        assert len(case_runs) == 1
        assert case_runs[0]["status"] == "passed"

        step_results_resp = client.get(f"/api/v1/case-runs/{case_runs[0]['id']}/step-results", headers=workspace_headers)
        assert step_results_resp.status_code == 200
        assert len(step_results_resp.json()["data"]) == 1

        with SessionLocal() as db:
            report = db.query(RunReport).filter(RunReport.test_run_id == test_run_id).one()
            step_result = db.query(StepResult).filter(StepResult.case_run_id == case_runs[0]["id"]).one()
            media = db.query(MediaObject).filter(MediaObject.id == step_result.actual_media_object_id).one()
            artifact = db.query(ReportArtifact).filter(ReportArtifact.report_id == report.id).one()
            report_resp = client.get(f"/api/v1/reports/{report.id}", headers=workspace_headers)
            assert report_resp.status_code == 200
            assert report_resp.json()["data"]["summary_status"] == "passed"
            assert report_resp.json()["data"]["summary_json"]["status"] == "passed"
            assert report_resp.json()["data"]["summary_json"]["counts"]["passed"] == 1
            assert step_result.actual_media_object_id is not None
            assert media.usage == "artifact"
            assert artifact.media_object_id == media.id
            assert artifact.artifact_type == "run_screenshot"
            assert artifact.case_run_id == case_runs[0]["id"]
            assert artifact.step_result_id is None
            assert artifact.artifact_url == f"/api/v1/media-objects/{media.id}/content"

def test_empty_suite_cannot_create_test_run():
    with app_client(reset=True) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "empty_suite_ws", "workspace_name": "Empty Suite WS"},
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

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_empty", "suite_name": "Empty Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-empty"},
        )
        assert run_resp.status_code == 422
        assert run_resp.json()["error"]["code"] == "TEST_SUITE_EMPTY"

def test_cancelling_test_run_transitions_to_cancelled(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.models import RunReport, TestRun
    from app.workers.execution import process_test_run as real_process_test_run

    _install_noop_dispatcher(monkeypatch)
    _install_fake_browser_adapter(monkeypatch)

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "cancel_ws", "workspace_name": "Cancel WS"},
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

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "cancel_case", "case_name": "Cancel Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "wait", "step_name": "Wait Render", "payload_json": {"ms": 100}}],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_cancel", "suite_name": "Cancel Suite", "status": "active"},
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
            headers=workspace_headers | {"Idempotency-Key": "run-cancel"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]
        assert run_resp.json()["data"]["status"] == "queued"

        cancelling_resp = client.patch(
            f"/api/v1/test-runs/{test_run_id}",
            json={"status": "cancelling"},
            headers=workspace_headers,
        )
        assert cancelling_resp.status_code == 200
        assert cancelling_resp.json()["data"]["status"] == "cancelling"

        real_process_test_run(test_run_id)

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers=workspace_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "cancelled"

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        assert case_runs_resp.status_code == 200
        assert case_runs_resp.json()["data"][0]["status"] == "cancelled"
        assert case_runs_resp.json()["data"][0]["failure_reason_code"] == "TEST_RUN_CANCELLED"
        assert case_runs_resp.json()["data"][0]["failure_summary"] == "Test run was cancelled."

        with SessionLocal() as db:
            test_run = db.get(TestRun, test_run_id)
            report = db.query(RunReport).filter(RunReport.test_run_id == test_run_id).one()
            assert test_run.status == "cancelled"
            assert report.summary_status == "cancelled"
            assert report.summary_json["cancelled_case_count"] == 1
            assert report.summary_json["failure"]["code"] == "TEST_RUN_CANCELLED"
            assert report.summary_json["failure"]["summary"] == "Test run was cancelled."

def test_cancelling_during_finalization_does_not_end_as_passed(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.models import RunReport, TestRun, User
    from app.services import execution as execution_service
    from app.services.execution import finalize_completed_test_run as real_finalize_completed_test_run
    from app.workers.execution import process_test_run as real_process_test_run
    from sqlalchemy import select

    _install_noop_dispatcher(monkeypatch)
    _install_fake_browser_adapter(monkeypatch)

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "finalize_race_ws", "workspace_name": "Finalize Race WS"},
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

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "finalize_race_case", "case_name": "Finalize Race Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "wait", "step_name": "Wait Render", "payload_json": {"ms": 100}}],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_finalize_race", "suite_name": "Finalize Race Suite", "status": "active"},
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
            headers=workspace_headers | {"Idempotency-Key": "run-finalize-race"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        patch_sent = {"done": False}

        def racing_finalize(db, test_run, *, passed_count: int, failed_count: int, error_count: int):
            if not patch_sent["done"]:
                patch_sent["done"] = True
                with SessionLocal() as competing_db:
                    latest_test_run = competing_db.get(TestRun, test_run.id)
                    current_user = competing_db.scalar(select(User).where(User.username == "admin"))
                    assert current_user is not None
                    updated = execution_service.update_test_run_status(
                        competing_db,
                        user=current_user,
                        test_run=latest_test_run,
                        status="cancelling",
                    )
                    assert updated.status == "cancelling"
            return real_finalize_completed_test_run(
                db,
                test_run,
                passed_count=passed_count,
                failed_count=failed_count,
                error_count=error_count,
            )

        monkeypatch.setattr("app.workers.execution.finalize_completed_test_run", racing_finalize)

        real_process_test_run(test_run_id)

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers=workspace_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "cancelled"

        with SessionLocal() as db:
            test_run = db.get(TestRun, test_run_id)
            report = db.query(RunReport).filter(RunReport.test_run_id == test_run_id).one()
            assert test_run.status == "cancelled"
            assert report.summary_status == "cancelled"

def test_adapter_initialization_failure_marks_test_run_error(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.models import RunReport

    monkeypatch.setattr("app.workers.execution.build_browser_execution_adapter", lambda: (_ for _ in ()).throw(RuntimeError("adapter init failed")))

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "adapter_failure_ws", "workspace_name": "Adapter Failure WS"},
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

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "adapter_failure_case", "case_name": "Adapter Failure Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "wait", "step_name": "Wait Render", "payload_json": {"ms": 100}}],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_adapter_failure", "suite_name": "Adapter Failure Suite", "status": "active"},
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
            headers=workspace_headers | {"Idempotency-Key": "run-adapter-failure"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers=workspace_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "error"
        assert detail_resp.json()["data"]["error_case_count"] == 1

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        assert case_runs_resp.status_code == 200
        assert case_runs_resp.json()["data"][0]["status"] == "error"
        assert case_runs_resp.json()["data"][0]["failure_reason_code"] == "TEST_RUN_EXECUTION_ERROR"

        with SessionLocal() as db:
            report = db.query(RunReport).filter(RunReport.test_run_id == test_run_id).one()
            assert report.summary_status == "error"
            assert "adapter init failed" in report.summary_json["message"]
            assert report.summary_json["failure"]["code"] == "TEST_RUN_EXECUTION_ERROR"

def test_component_call_steps_are_expanded_and_executed(monkeypatch):
    _reset_local_data()

    _install_fake_browser_adapter(monkeypatch)

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "component_call_ws", "workspace_name": "Component Call WS"},
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

        component_resp = client.post(
            "/api/v1/components",
            json={"component_code": "shared_login", "component_name": "Shared Login", "status": "published"},
            headers=workspace_headers,
        )
        assert component_resp.status_code == 201
        component = component_resp.json()["data"]
        assert component["published_at"] is not None
        component_id = component["id"]

        component_steps_resp = client.put(
            f"/api/v1/components/{component_id}/steps",
            json=[
                {"step_no": 1, "step_type": "wait", "step_name": "Wait In Component", "payload_json": {"ms": 100}},
                {"step_no": 2, "step_type": "click", "step_name": "Click In Component", "payload_json": {"selector": "#login"}},
            ],
            headers=workspace_headers,
        )
        assert component_steps_resp.status_code == 200

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_component_call", "case_name": "Component Call Case", "status": "published"},
            headers=workspace_headers,
        )
        assert case_resp.status_code == 201
        test_case_id = case_resp.json()["data"]["id"]

        case_steps_resp = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {"step_no": 1, "step_type": "wait", "step_name": "Outer Wait", "payload_json": {"ms": 100}},
                {"step_no": 2, "step_type": "component_call", "step_name": "Invoke Component", "component_id": component_id},
                {"step_no": 3, "step_type": "input", "step_name": "Outer Input", "payload_json": {"selector": "#username", "text": "admin"}},
            ],
            headers=workspace_headers,
        )
        assert case_steps_resp.status_code == 200

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_component_call", "suite_name": "Component Call Suite", "status": "active"},
            headers=workspace_headers,
        )
        assert suite_resp.status_code == 201
        test_suite_id = suite_resp.json()["data"]["id"]

        suite_cases_resp = client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )
        assert suite_cases_resp.status_code == 200

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-component-call"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        assert case_runs_resp.status_code == 200
        case_run_id = case_runs_resp.json()["data"][0]["id"]

        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        assert step_results_resp.status_code == 200
        step_results = step_results_resp.json()["data"]
        assert len(step_results) == 4
        assert [item["step_no"] for item in step_results] == [1, 2, 3, 4]
        assert [item["step_type"] for item in step_results] == ["wait", "wait", "click", "input"]
        assert all(item["status"] == "passed" for item in step_results)

def test_component_call_can_expand_new_browser_steps(monkeypatch):
    _reset_local_data()

    _install_fake_browser_adapter(monkeypatch)

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "component_new_steps_ws", "workspace_name": "Component New Steps WS"},
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

        component_resp = client.post(
            "/api/v1/components",
            json={"component_code": "shared_interactions", "component_name": "Shared Interactions", "status": "published"},
            headers=workspace_headers,
        )
        component_id = component_resp.json()["data"]["id"]

        component_steps_resp = client.put(
            f"/api/v1/components/{component_id}/steps",
            json=[
                {"step_no": 1, "step_type": "scroll", "step_name": "Scroll Container", "payload_json": {"target": "element", "selector": "[data-testid='scroll-container']", "direction": "down", "distance": 180}},
                {"step_no": 2, "step_type": "long_press", "step_name": "Long Press In Component", "payload_json": {"selector": "[data-testid='long-press-target']", "duration_ms": 800}},
            ],
            headers=workspace_headers,
        )
        assert component_steps_resp.status_code == 200

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_component_new_steps", "case_name": "Component New Steps Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        case_steps_resp = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {"step_no": 1, "step_type": "navigate", "step_name": "Navigate First", "payload_json": {"url": "/demo/acceptance-target?view=details"}},
                {"step_no": 2, "step_type": "component_call", "step_name": "Invoke Component", "component_id": component_id},
            ],
            headers=workspace_headers,
        )
        assert case_steps_resp.status_code == 200

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_component_new_steps", "suite_name": "Component New Steps Suite", "status": "active"},
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
            json={"test_suite_id": test_suite_id, "environment_profile_id": environment_profile_id, "trigger_source": "manual"},
            headers=workspace_headers | {"Idempotency-Key": "run-component-new-steps"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        case_run_id = case_runs_resp.json()["data"][0]["id"]
        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_results = step_results_resp.json()["data"]
        assert [item["step_type"] for item in step_results] == ["navigate", "scroll", "long_press"]
        assert all(item["status"] == "passed" for item in step_results)

@pytest.mark.vision
def test_new_browser_steps_work_with_ocr_assert_execution(monkeypatch):
    _reset_local_data()

    _install_visual_browser_adapter(monkeypatch, ocr_status="passed")

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "browser_ocr_ws", "workspace_name": "Browser OCR WS"},
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

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_browser_ocr", "case_name": "Browser OCR Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {"step_no": 1, "step_type": "navigate", "step_name": "Navigate", "payload_json": {"url": "/demo/acceptance-target?view=details"}},
                {"step_no": 2, "step_type": "long_press", "step_name": "Long Press", "payload_json": {"selector": "[data-testid='long-press-target']", "duration_ms": 800}},
                {"step_no": 3, "step_type": "ocr_assert", "step_name": "OCR Check", "payload_json": {"selector": "[data-testid='result-banner']", "expected_text": "details"}},
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_browser_ocr", "suite_name": "Browser OCR Suite", "status": "active"},
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
            json={"test_suite_id": test_suite_id, "environment_profile_id": environment_profile_id, "trigger_source": "manual"},
            headers=workspace_headers | {"Idempotency-Key": "run-browser-ocr"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers=workspace_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "passed"

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        case_run_id = case_runs_resp.json()["data"][0]["id"]
        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_results = step_results_resp.json()["data"]
        assert [item["step_type"] for item in step_results] == ["navigate", "long_press", "ocr_assert"]
        assert all(item["status"] == "passed" for item in step_results)

def test_template_assert_requires_matching_template_strategy_before_execution():
    with app_client(reset=True) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_strategy_ws", "workspace_name": "Template Strategy WS"},
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
            template_code="tpl_ocr_only",
            template_name="OCR Template",
            match_strategy="ocr",
        )

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_template_strategy", "case_name": "Template Strategy Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        case_steps_resp = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "template_assert",
                    "step_name": "Template Assert",
                    "template_id": template_id,
                    "payload_json": {},
                }
            ],
            headers=workspace_headers,
        )
        assert case_steps_resp.status_code == 422
        assert case_steps_resp.json()["error"]["code"] == "STEP_CONFIGURATION_INVALID"

@pytest.mark.vision
def test_template_assert_success_persists_expected_and_actual_media(monkeypatch):
    _reset_local_data()

    _install_visual_browser_adapter(monkeypatch, template_status="passed")

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_pass_ws", "workspace_name": "Template Pass WS"},
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
            template_code="tpl_pass",
            template_name="Pass Template",
        )

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_template_pass", "case_name": "Template Pass Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "template_assert",
                    "step_name": "Template Pass",
                    "template_id": template_id,
                    "payload_json": {},
                }
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_template_pass", "suite_name": "Template Pass Suite", "status": "active"},
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
            headers=workspace_headers | {"Idempotency-Key": "run-template-pass"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers=workspace_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "passed"

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        case_run_id = case_runs_resp.json()["data"][0]["id"]
        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_result = step_results_resp.json()["data"][0]
        assert step_result["status"] == "passed"
        assert step_result["expected_media_object_id"] is not None
        assert step_result["actual_media_object_id"] is not None
        assert step_result["diff_media_object_id"] is None
        report_resp = client.get(f"/api/v1/test-runs/{test_run_id}/report", headers=workspace_headers)
        artifacts_resp = client.get(f"/api/v1/reports/{report_resp.json()['data']['id']}/artifacts", headers=workspace_headers)
        assert artifacts_resp.status_code == 200
        assert {item["artifact_type"] for item in artifacts_resp.json()["data"]} == {"run_screenshot", "step_actual"}

@pytest.mark.vision
def test_template_assert_failure_marks_run_failed_and_persists_diff_media(monkeypatch):
    _reset_local_data()

    _install_visual_browser_adapter(monkeypatch, template_status="failed")

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_fail_ws", "workspace_name": "Template Fail WS"},
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
            template_code="tpl_fail",
            template_name="Fail Template",
        )

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_template_fail", "case_name": "Template Fail Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "template_assert",
                    "step_name": "Template Fail",
                    "template_id": template_id,
                    "payload_json": {},
                }
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_template_fail", "suite_name": "Template Fail Suite", "status": "active"},
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
            headers=workspace_headers | {"Idempotency-Key": "run-template-fail"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers=workspace_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "failed"

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        assert case_runs_resp.json()["data"][0]["status"] == "failed"
        assert case_runs_resp.json()["data"][0]["failure_reason_code"] == "TEMPLATE_ASSERTION_FAILED"
        assert case_runs_resp.json()["data"][0]["failure_summary"] == "Template assertion failed."
        case_run_id = case_runs_resp.json()["data"][0]["id"]

        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_result = step_results_resp.json()["data"][0]
        assert step_result["status"] == "failed"
        assert step_result["expected_media_object_id"] is not None
        assert step_result["actual_media_object_id"] is not None
        assert step_result["diff_media_object_id"] is not None
        report_resp = client.get(f"/api/v1/test-runs/{test_run_id}/report", headers=workspace_headers)
        assert report_resp.json()["data"]["summary_json"]["failure"]["code"] == "TEMPLATE_ASSERTION_FAILED"
        assert report_resp.json()["data"]["summary_json"]["failure"]["summary"] == "Template assertion failed."
        artifacts_resp = client.get(f"/api/v1/reports/{report_resp.json()['data']['id']}/artifacts", headers=workspace_headers)
        assert artifacts_resp.status_code == 200
        assert {item["artifact_type"] for item in artifacts_resp.json()["data"]} == {"run_screenshot", "step_actual", "step_diff"}
        assert all(item["artifact_url"] == f"/api/v1/media-objects/{item['media_object_id']}/content" for item in artifacts_resp.json()["data"])

@pytest.mark.vision
def test_ocr_assert_failure_marks_run_failed(monkeypatch):
    _reset_local_data()

    _install_visual_browser_adapter(monkeypatch, ocr_status="failed")

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "ocr_fail_ws", "workspace_name": "OCR Fail WS"},
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

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_ocr_fail", "case_name": "OCR Fail Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "ocr_assert",
                    "step_name": "OCR Fail",
                    "payload_json": {"selector": "#main", "expected_text": "expected text"},
                }
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_ocr_fail", "suite_name": "OCR Fail Suite", "status": "active"},
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
            headers=workspace_headers | {"Idempotency-Key": "run-ocr-fail"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers=workspace_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "failed"

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        assert case_runs_resp.json()["data"][0]["status"] == "failed"
        case_run_id = case_runs_resp.json()["data"][0]["id"]

        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_result = step_results_resp.json()["data"][0]
        assert step_result["status"] == "failed"
        assert step_result["actual_media_object_id"] is not None
        assert step_result["diff_media_object_id"] is None
        report_resp = client.get(f"/api/v1/test-runs/{test_run_id}/report", headers=workspace_headers)
        assert report_resp.json()["data"]["summary_json"]["failure"]["code"] == "OCR_ASSERTION_FAILED"
        assert report_resp.json()["data"]["summary_json"]["failure"]["summary"] == "OCR assertion failed."
        artifacts_resp = client.get(f"/api/v1/reports/{report_resp.json()['data']['id']}/artifacts", headers=workspace_headers)
        assert artifacts_resp.status_code == 200
        assert {item["artifact_type"] for item in artifacts_resp.json()["data"]} == {"run_screenshot", "step_ocr"}
        assert all(item["artifact_url"] == f"/api/v1/media-objects/{item['media_object_id']}/content" for item in artifacts_resp.json()["data"])

@pytest.mark.vision
def test_partial_failed_run_has_stable_report_failure_summary(monkeypatch):
    _reset_local_data()

    _install_visual_browser_adapter(monkeypatch, template_status="failed")

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "partial_failed_ws", "workspace_name": "Partial Failed WS"},
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

        pass_case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "partial_pass_case", "case_name": "Partial Pass Case", "status": "published"},
            headers=workspace_headers,
        )
        pass_case_id = pass_case_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-cases/{pass_case_id}/steps",
            json=[{"step_no": 1, "step_type": "wait", "step_name": "Pass Wait", "payload_json": {"ms": 100}}],
            headers=workspace_headers,
        )

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_partial_fail",
            template_name="Partial Fail Template",
        )
        fail_case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "partial_fail_case", "case_name": "Partial Fail Case", "status": "published"},
            headers=workspace_headers,
        )
        fail_case_id = fail_case_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-cases/{fail_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "template_assert",
                    "step_name": "Fail Template",
                    "template_id": template_id,
                    "payload_json": {},
                }
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_partial_fail", "suite_name": "Partial Fail Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[
                {"test_case_id": pass_case_id, "sort_order": 1},
                {"test_case_id": fail_case_id, "sort_order": 2},
            ],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-partial-fail"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        report_resp = client.get(f"/api/v1/test-runs/{test_run_id}/report", headers=workspace_headers)
        assert report_resp.status_code == 200
        assert report_resp.json()["data"]["summary_status"] == "partial_failed"
        assert report_resp.json()["data"]["summary_json"]["failure"]["code"] == "TEMPLATE_ASSERTION_FAILED"
        assert report_resp.json()["data"]["summary_json"]["failure"]["summary"] == "Template assertion failed."

def test_non_active_suite_cannot_create_test_run():
    with app_client(reset=True) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "inactive_suite_ws", "workspace_name": "Inactive Suite WS"},
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

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "published_case", "case_name": "Published Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "wait", "step_name": "Wait Render", "payload_json": {"ms": 100}}],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_draft", "suite_name": "Draft Suite", "status": "draft"},
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
            headers=workspace_headers | {"Idempotency-Key": "run-inactive-suite"},
        )
        assert run_resp.status_code == 422
        assert run_resp.json()["error"]["code"] == "TEST_SUITE_NOT_ACTIVE"

def test_draft_test_case_cannot_create_test_run():
    with app_client(reset=True) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "draft_case_ws", "workspace_name": "Draft Case WS"},
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

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "draft_case", "case_name": "Draft Case", "status": "draft"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "wait", "step_name": "Wait Render", "payload_json": {"ms": 100}}],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_active_case", "suite_name": "Active Suite", "status": "active"},
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
            headers=workspace_headers | {"Idempotency-Key": "run-draft-case"},
        )
        assert run_resp.status_code == 422
        assert run_resp.json()["error"]["code"] == "PUBLISHED_VERSION_REQUIRED"

def test_draft_component_cannot_create_test_run():
    with app_client(reset=True) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "draft_component_ws", "workspace_name": "Draft Component WS"},
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

        component_resp = client.post(
            "/api/v1/components",
            json={"component_code": "draft_component", "component_name": "Draft Component", "status": "draft"},
            headers=workspace_headers,
        )
        component_id = component_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/components/{component_id}/steps",
            json=[{"step_no": 1, "step_type": "wait", "step_name": "Wait In Component", "payload_json": {"ms": 100}}],
            headers=workspace_headers,
        )

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "published_case_with_component", "case_name": "Published Case With Component", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "component_call", "step_name": "Invoke Draft Component", "component_id": component_id}],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_draft_component", "suite_name": "Draft Component Suite", "status": "active"},
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
            headers=workspace_headers | {"Idempotency-Key": "run-draft-component"},
        )
        assert run_resp.status_code == 422
        assert run_resp.json()["error"]["code"] == "PUBLISHED_VERSION_REQUIRED"
