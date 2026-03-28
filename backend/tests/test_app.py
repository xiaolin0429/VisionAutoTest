from __future__ import annotations

import base64
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

TEST_ADMIN_USERNAME = "admin"
TEST_ADMIN_PASSWORD = "test-admin-password"


def _require_test_database_url() -> str:
    database_url = os.environ.get("VAT_TEST_DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "VAT_TEST_DATABASE_URL is required. Please prepare an external PostgreSQL test database before running backend tests."
        )
    return database_url


def _reset_local_data() -> None:
    if "app.db.session" in sys.modules:
        from app.db.session import engine

        engine.dispose()
    stale_modules = [module_name for module_name in sys.modules if module_name == "app" or module_name.startswith("app.")]
    for module_name in stale_modules:
        sys.modules.pop(module_name, None)
    backend_root = Path(__file__).resolve().parents[1]
    testdata_root = backend_root / ".testdata"
    testdata_root.mkdir(exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="case_", dir=testdata_root))
    os.environ["VAT_DATABASE_URL"] = _require_test_database_url()
    os.environ["VAT_APP_ENV"] = "test"
    os.environ["VAT_DATABASE_AUTO_CREATE"] = "false"
    os.environ["VAT_DATABASE_AUTO_MIGRATE"] = "true"
    os.environ.pop("VAT_DATABASE_ADMIN_URL", None)
    os.environ["VAT_LOCAL_STORAGE_PATH"] = str(temp_dir / "media")
    os.environ["VAT_DEFAULT_ADMIN_USERNAME"] = TEST_ADMIN_USERNAME
    os.environ["VAT_DEFAULT_ADMIN_PASSWORD"] = TEST_ADMIN_PASSWORD

    from app.db.migrations import reset_database_schema, upgrade_database

    reset_database_schema(database_url=os.environ["VAT_DATABASE_URL"])
    upgrade_database(database_url=os.environ["VAT_DATABASE_URL"])


def _install_fake_browser_adapter(monkeypatch) -> None:
    from app.workers.browser import BrowserArtifact, BrowserStepResult, CaseExecutionResult

    class FakeBrowserAdapter:
        supported_step_types = {"wait", "click", "input"}

        def execute_case(self, *, base_url: str, case_run_id: int, device_profile, steps):
            _ = (base_url, case_run_id, device_profile)
            step_results: list[BrowserStepResult] = []
            for step in steps:
                started_at = datetime.now(timezone.utc)
                finished_at = datetime.now(timezone.utc)
                if step.step_type not in self.supported_step_types:
                    step_results.append(
                        BrowserStepResult(
                            step_no=step.step_no,
                            step_type=step.step_type,
                            status="error",
                            started_at=started_at,
                            finished_at=finished_at,
                            duration_ms=1,
                            error_message=f"Unsupported step type: {step.step_type}",
                        )
                    )
                    return CaseExecutionResult(
                        status="error",
                        step_results=step_results,
                        failure_reason_code="STEP_NOT_SUPPORTED",
                        failure_summary=f"Unsupported step type: {step.step_type}",
                        artifact=BrowserArtifact(
                            file_name=f"case-run-{case_run_id}.png",
                            content_type="image/png",
                            content_bytes=base64.b64decode(
                                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9s2GoswAAAAASUVORK5CYII="
                            ),
                        ),
                    )

                step_results.append(
                    BrowserStepResult(
                        step_no=step.step_no,
                        step_type=step.step_type,
                        status="passed",
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_ms=1,
                        score_value=1.0,
                    )
                )

            return CaseExecutionResult(
                status="passed",
                step_results=step_results,
                artifact=BrowserArtifact(
                    file_name=f"case-run-{case_run_id}.png",
                    content_type="image/png",
                    content_bytes=base64.b64decode(
                        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9s2GoswAAAAASUVORK5CYII="
                    ),
                ),
            )

    monkeypatch.setattr("app.workers.execution.build_browser_execution_adapter", lambda: FakeBrowserAdapter())


def test_healthz():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "ok"


def test_mvp_backend_smoke_flow(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import MediaObject, ReportArtifact, RunReport, StepResult

    _install_fake_browser_adapter(monkeypatch)

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        assert login_resp.status_code == 201
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "mvp_demo", "name": "MVP Demo"},
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
            assert step_result.actual_media_object_id is not None
            assert media.usage == "artifact"
            assert artifact.media_object_id == media.id


def test_empty_suite_cannot_create_test_run():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "empty_suite_ws", "name": "Empty Suite WS"},
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
    from app.main import app
    from app.models import RunReport, TestRun
    from app.workers.execution import process_test_run as real_process_test_run

    monkeypatch.setattr("app.api.v1.executions.process_test_run", lambda _run_id: None)
    _install_fake_browser_adapter(monkeypatch)

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "cancel_ws", "name": "Cancel WS"},
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

        with SessionLocal() as db:
            test_run = db.get(TestRun, test_run_id)
            report = db.query(RunReport).filter(RunReport.test_run_id == test_run_id).one()
            assert test_run.status == "cancelled"
            assert report.summary_status == "cancelled"
            assert report.summary_json["cancelled_case_count"] == 1


def test_cancelling_during_finalization_does_not_end_as_passed(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import RunReport, TestRun, User
    from app.services import execution as execution_service
    from app.services.execution import finalize_completed_test_run as real_finalize_completed_test_run
    from app.workers.execution import process_test_run as real_process_test_run
    from sqlalchemy import select

    monkeypatch.setattr("app.api.v1.executions.process_test_run", lambda _run_id: None)
    _install_fake_browser_adapter(monkeypatch)

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "finalize_race_ws", "name": "Finalize Race WS"},
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


def test_unsupported_step_marks_test_run_error(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_fake_browser_adapter(monkeypatch)

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "unsupported_ws", "name": "Unsupported WS"},
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
            json={"case_code": "unsupported_case", "case_name": "Unsupported Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "template_assert", "step_name": "Unsupported", "payload_json": {}}],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_unsupported", "suite_name": "Unsupported Suite", "status": "active"},
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
            headers=workspace_headers | {"Idempotency-Key": "run-unsupported"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers=workspace_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "error"

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        case_run_id = case_runs_resp.json()["data"][0]["id"]
        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        assert step_results_resp.status_code == 200
        assert step_results_resp.json()["data"][0]["status"] == "error"


def test_adapter_initialization_failure_marks_test_run_error(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import RunReport

    monkeypatch.setattr("app.workers.execution.build_browser_execution_adapter", lambda: (_ for _ in ()).throw(RuntimeError("adapter init failed")))

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "adapter_failure_ws", "name": "Adapter Failure WS"},
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


def test_component_call_steps_are_expanded_and_executed(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_fake_browser_adapter(monkeypatch)

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "component_call_ws", "name": "Component Call WS"},
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


def test_non_active_suite_cannot_create_test_run():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "inactive_suite_ws", "name": "Inactive Suite WS"},
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
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "draft_case_ws", "name": "Draft Case WS"},
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
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "draft_component_ws", "name": "Draft Component WS"},
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
