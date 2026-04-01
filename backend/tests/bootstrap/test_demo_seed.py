from __future__ import annotations

from tests.support.constants import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME
from tests.support.fakes import _install_fake_browser_adapter
from tests.support.runtime import _reset_local_data, app_client

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

    with app_client() as client:
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
