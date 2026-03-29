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
TINY_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9s2GoswAAAAASUVORK5CYII="
)


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

        def execute_case(self, *, base_url: str, case_run_id: int, device_profile, steps, template_contexts):
            _ = (base_url, case_run_id, device_profile, template_contexts)
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
                            content_bytes=TINY_PNG_BYTES,
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
                    content_bytes=TINY_PNG_BYTES,
                ),
            )

    monkeypatch.setattr("app.workers.execution.build_browser_execution_adapter", lambda: FakeBrowserAdapter())


def _install_visual_browser_adapter(monkeypatch, *, template_status: str = "passed", ocr_status: str = "passed") -> None:
    from app.workers.browser import BrowserArtifact, BrowserStepResult, CaseExecutionResult
    from app.workers.vision import VisionArtifact

    class FakeVisualBrowserAdapter:
        def execute_case(self, *, base_url: str, case_run_id: int, device_profile, steps, template_contexts):
            _ = (base_url, case_run_id, device_profile)
            step_results: list[BrowserStepResult] = []
            failure_reason_code: str | None = None
            failure_summary: str | None = None
            case_status = "passed"

            for step in steps:
                started_at = datetime.now(timezone.utc)
                finished_at = datetime.now(timezone.utc)
                status = "passed"
                error_message = None
                score_value = 1.0
                expected_media_object_id = None
                actual_artifact = None
                diff_artifact = None

                if step.step_type == "template_assert":
                    template_context = template_contexts[step.template_id]
                    expected_media_object_id = template_context.baseline_media_object_id
                    actual_artifact = VisionArtifact(
                        file_name=f"case-run-{case_run_id}-step-{step.step_no}-actual.png",
                        content_type="image/png",
                        content_bytes=TINY_PNG_BYTES,
                        artifact_type="actual_screenshot",
                    )
                    status = template_status
                    score_value = 0.98 if status == "passed" else 0.21
                    if status == "failed":
                        error_message = "Template assertion failed."
                        diff_artifact = VisionArtifact(
                            file_name=f"case-run-{case_run_id}-step-{step.step_no}-diff.png",
                            content_type="image/png",
                            content_bytes=TINY_PNG_BYTES,
                            artifact_type="diff_screenshot",
                        )
                        failure_reason_code = "TEMPLATE_ASSERTION_FAILED"
                        failure_summary = error_message
                        case_status = "failed"
                    elif status == "error":
                        error_message = "Template engine error."
                        failure_reason_code = "STEP_EXECUTION_ERROR"
                        failure_summary = error_message
                        case_status = "error"
                elif step.step_type == "ocr_assert":
                    actual_artifact = VisionArtifact(
                        file_name=f"case-run-{case_run_id}-step-{step.step_no}-ocr.png",
                        content_type="image/png",
                        content_bytes=TINY_PNG_BYTES,
                        artifact_type="ocr_screenshot",
                    )
                    status = ocr_status
                    score_value = 1.0 if status == "passed" else 0.0
                    if status == "failed":
                        error_message = "OCR assertion failed."
                        failure_reason_code = "OCR_ASSERTION_FAILED"
                        failure_summary = error_message
                        case_status = "failed"
                    elif status == "error":
                        error_message = "OCR engine error."
                        failure_reason_code = "STEP_EXECUTION_ERROR"
                        failure_summary = error_message
                        case_status = "error"

                step_results.append(
                    BrowserStepResult(
                        step_no=step.step_no,
                        step_type=step.step_type,
                        status=status,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_ms=1,
                        error_message=error_message,
                        score_value=score_value,
                        expected_media_object_id=expected_media_object_id,
                        actual_artifact=actual_artifact,
                        diff_artifact=diff_artifact,
                    )
                )

                if status in {"failed", "error"}:
                    break

            return CaseExecutionResult(
                status=case_status,
                step_results=step_results,
                failure_reason_code=failure_reason_code,
                failure_summary=failure_summary,
                artifact=BrowserArtifact(
                    file_name=f"case-run-{case_run_id}.png",
                    content_type="image/png",
                    content_bytes=TINY_PNG_BYTES,
                ),
            )

    monkeypatch.setattr("app.workers.execution.build_browser_execution_adapter", lambda: FakeVisualBrowserAdapter())


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
            "status": "draft",
            "original_media_object_id": media_object_id,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_healthz():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "ok"


def test_demo_acceptance_target_page_is_served():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/demo/acceptance-target")
        assert response.status_code == 200
        assert "VisionAutoTest Demo Target" in response.text
        assert "data-testid=\"cta-open-form\"" in response.text
        assert "data-testid=\"submit-button\"" in response.text


def test_bootstrap_seeds_demo_acceptance_bundle(monkeypatch):
    _reset_local_data()
    from app.db.bootstrap import (
        DEMO_CASE_CODE,
        DEMO_CASE_STEPS,
        DEMO_DEVICE_PROFILE_NAME,
        DEMO_ENV_PROFILE_NAME,
        DEMO_SUITE_CODE,
        DEMO_TEMPLATE_CODE,
        DEMO_WORKSPACE_CODE,
        seed_default_admin,
        seed_demo_acceptance_data,
    )
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import BaselineRevision, DeviceProfile, EnvironmentProfile, Template, TestCase, TestCaseStep, TestSuite, Workspace, WorkspaceMember

    _install_fake_browser_adapter(monkeypatch)
    seed_default_admin()
    seed_demo_acceptance_data(force=True)
    seed_demo_acceptance_data(force=True)

    with SessionLocal() as db:
        workspace = db.query(Workspace).filter(Workspace.workspace_code == DEMO_WORKSPACE_CODE, Workspace.is_deleted.is_(False)).one()
        environment = db.query(EnvironmentProfile).filter(
            EnvironmentProfile.workspace_id == workspace.id,
            EnvironmentProfile.profile_name == DEMO_ENV_PROFILE_NAME,
            EnvironmentProfile.is_deleted.is_(False),
        ).one()
        device = db.query(DeviceProfile).filter(
            DeviceProfile.workspace_id == workspace.id,
            DeviceProfile.profile_name == DEMO_DEVICE_PROFILE_NAME,
            DeviceProfile.is_deleted.is_(False),
        ).one()
        template = db.query(Template).filter(
            Template.workspace_id == workspace.id,
            Template.template_code == DEMO_TEMPLATE_CODE,
            Template.is_deleted.is_(False),
        ).one()
        baseline = db.query(BaselineRevision).filter(BaselineRevision.id == template.current_baseline_revision_id).one()
        test_case = db.query(TestCase).filter(
            TestCase.workspace_id == workspace.id,
            TestCase.case_code == DEMO_CASE_CODE,
            TestCase.is_deleted.is_(False),
        ).one()
        suite = db.query(TestSuite).filter(
            TestSuite.workspace_id == workspace.id,
            TestSuite.suite_code == DEMO_SUITE_CODE,
            TestSuite.is_deleted.is_(False),
        ).one()
        member = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == workspace.owner_user_id,
        ).one()
        steps = db.query(TestCaseStep).filter(TestCaseStep.test_case_id == test_case.id).order_by(TestCaseStep.step_no.asc()).all()

        assert environment.base_url.endswith("/demo/acceptance-target")
        assert device.is_default is True
        assert template.current_baseline_revision_id is not None
        assert baseline.media_object_id is not None
        assert test_case.status == "published"
        assert suite.status == "active"
        assert member.workspace_role == "workspace_admin"
        assert len(steps) == len(DEMO_CASE_STEPS)

        workspace_id = workspace.id
        environment_profile_id = environment.id
        test_suite_id = suite.id

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        assert login_resp.status_code == 201
        token = login_resp.json()["data"]["access_token"]
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Workspace-Id": str(workspace_id),
            "Idempotency-Key": "seeded-demo-run",
        }

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=headers,
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers={"Authorization": f"Bearer {token}"})
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "passed"


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


def test_invalid_template_assert_step_is_rejected_during_step_save():
    _reset_local_data()
    from app.main import app

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

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "unsupported_case", "case_name": "Unsupported Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "template_assert", "step_name": "Unsupported", "payload_json": {}}],
            headers=workspace_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "STEP_SEQUENCE_INVALID"


def test_invalid_ocr_assert_step_is_rejected_during_step_save():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "invalid_ocr_ws", "name": "Invalid OCR WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "invalid_ocr_case", "case_name": "Invalid OCR Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "ocr_assert", "step_name": "Invalid OCR", "payload_json": {"selector": "#main"}}],
            headers=workspace_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "STEP_SEQUENCE_INVALID"


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


def test_template_assert_requires_matching_template_strategy_before_execution():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_strategy_ws", "name": "Template Strategy WS"},
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
        assert case_steps_resp.status_code == 200

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_template_strategy", "suite_name": "Template Strategy Suite", "status": "active"},
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
            headers=workspace_headers | {"Idempotency-Key": "run-template-strategy"},
        )
        assert run_resp.status_code == 422
        assert run_resp.json()["error"]["code"] == "STEP_CONFIGURATION_INVALID"


def test_template_assert_success_persists_expected_and_actual_media(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_visual_browser_adapter(monkeypatch, template_status="passed")

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_pass_ws", "name": "Template Pass WS"},
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


def test_template_assert_failure_marks_run_failed_and_persists_diff_media(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_visual_browser_adapter(monkeypatch, template_status="failed")

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_fail_ws", "name": "Template Fail WS"},
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
        case_run_id = case_runs_resp.json()["data"][0]["id"]

        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_result = step_results_resp.json()["data"][0]
        assert step_result["status"] == "failed"
        assert step_result["expected_media_object_id"] is not None
        assert step_result["actual_media_object_id"] is not None
        assert step_result["diff_media_object_id"] is not None


def test_ocr_assert_failure_marks_run_failed(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_visual_browser_adapter(monkeypatch, ocr_status="failed")

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "ocr_fail_ws", "name": "OCR Fail WS"},
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
