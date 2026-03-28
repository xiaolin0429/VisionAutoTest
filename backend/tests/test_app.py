from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


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
    os.environ["VAT_DATABASE_URL"] = f"sqlite+pysqlite:///{temp_dir / 'visionautotest.db'}"
    os.environ["VAT_LOCAL_STORAGE_PATH"] = str(temp_dir / "media")


def test_healthz():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "ok"


def test_mvp_backend_smoke_flow():
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import RunReport

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": "admin", "password": "admin123456"})
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
            json={"case_code": "case_login", "case_name": "Login Case"},
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
            report_resp = client.get(f"/api/v1/reports/{report.id}", headers=workspace_headers)
            assert report_resp.status_code == 200
            assert report_resp.json()["data"]["summary_status"] == "passed"


def test_empty_suite_cannot_create_test_run():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": "admin", "password": "admin123456"})
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

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": "admin", "password": "admin123456"})
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
            json={"case_code": "cancel_case", "case_name": "Cancel Case"},
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

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": "admin", "password": "admin123456"})
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
            json={"case_code": "finalize_race_case", "case_name": "Finalize Race Case"},
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
