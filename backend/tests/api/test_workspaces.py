from __future__ import annotations

from tests.support.constants import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME
from tests.support.runtime import _reset_local_data, app_client


def test_environment_secret_values_are_encrypted_at_rest():
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.models import EnvironmentVariable

    with app_client() as client:
        login_resp = client.post(
            "/api/v1/sessions",
            json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
        )
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "env_secret_ws", "workspace_name": "Env Secret WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "secret-env", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        create_resp = client.post(
            f"/api/v1/environment-profiles/{environment_profile_id}/variables",
            headers=workspace_headers,
            json={
                "var_key": "API_TOKEN",
                "value": "plain-secret-value",
                "is_secret": True,
            },
        )
        assert create_resp.status_code == 201
        assert create_resp.json()["data"]["display_value"] == "******"

        with SessionLocal() as db:
            variable = (
                db.query(EnvironmentVariable)
                .filter(
                    EnvironmentVariable.environment_profile_id == environment_profile_id
                )
                .one()
            )
            assert variable.var_value_ciphertext != "plain-secret-value"
            assert "plain-secret-value" not in variable.var_value_ciphertext


def test_workspace_execution_readiness_reports_blocking_issues():
    _reset_local_data()

    with app_client() as client:
        login_resp = client.post(
            "/api/v1/sessions",
            json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
        )
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "readiness_ws", "workspace_name": "Readiness WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]

        readiness_resp = client.get(
            f"/api/v1/workspaces/{workspace_id}/execution-readiness",
            headers=headers,
        )
        assert readiness_resp.status_code == 200
        readiness = readiness_resp.json()["data"]
        assert readiness["scope"] == "workspace"
        assert readiness["status"] == "blocked"
        assert readiness["active_environment_count"] == 0
        assert readiness["active_test_suite_count"] == 0
        assert {issue["code"] for issue in readiness["issues"]} == {
            "ENVIRONMENT_PROFILE_REQUIRED",
            "TEST_SUITE_REQUIRED",
        }


def test_environment_and_device_profiles_reject_invalid_execution_configuration():
    _reset_local_data()

    with app_client() as client:
        login_resp = client.post(
            "/api/v1/sessions",
            json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
        )
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "config_guard_ws", "workspace_name": "Config Guard WS"},
            headers=headers,
        )
        workspace_headers = headers | {
            "X-Workspace-Id": str(workspace_resp.json()["data"]["id"])
        }

        invalid_environment = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "invalid", "base_url": "www.feishu.cn"},
            headers=workspace_headers,
        )
        assert invalid_environment.status_code == 422
        assert invalid_environment.json()["error"]["code"] == "ENVIRONMENT_BASE_URL_INVALID"

        valid_environment = client.post(
            "/api/v1/environment-profiles",
            json={
                "profile_name": "local",
                "base_url": "  http://localhost:8080/app  ",
            },
            headers=workspace_headers,
        )
        assert valid_environment.status_code == 201
        environment_id = valid_environment.json()["data"]["id"]
        assert valid_environment.json()["data"]["base_url"] == "http://localhost:8080/app"

        invalid_patch = client.patch(
            f"/api/v1/environment-profiles/{environment_id}",
            json={"base_url": "ftp://example.com"},
            headers=workspace_headers,
        )
        assert invalid_patch.status_code == 422
        assert invalid_patch.json()["error"]["code"] == "ENVIRONMENT_BASE_URL_INVALID"
        unchanged_environment = client.get(
            f"/api/v1/environment-profiles/{environment_id}",
            headers=workspace_headers,
        )
        assert unchanged_environment.json()["data"]["base_url"] == "http://localhost:8080/app"

        invalid_device = client.post(
            "/api/v1/device-profiles",
            json={
                "profile_name": "broken",
                "device_type": "web",
                "viewport_width": 0,
                "viewport_height": 768,
                "device_scale_factor": 1,
            },
            headers=workspace_headers,
        )
        assert invalid_device.status_code == 422
        assert invalid_device.json()["error"]["code"] == "DEVICE_PROFILE_INVALID"
