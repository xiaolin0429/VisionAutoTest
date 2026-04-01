from __future__ import annotations

from tests.support.constants import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME
from tests.support.runtime import _reset_local_data, app_client

def test_environment_secret_values_are_encrypted_at_rest():
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.models import EnvironmentVariable

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
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
            json={"var_key": "API_TOKEN", "value": "plain-secret-value", "is_secret": True},
        )
        assert create_resp.status_code == 201
        assert create_resp.json()["data"]["display_value"] == "******"

        with SessionLocal() as db:
            variable = db.query(EnvironmentVariable).filter(EnvironmentVariable.environment_profile_id == environment_profile_id).one()
            assert variable.var_value_ciphertext != "plain-secret-value"
            assert "plain-secret-value" not in variable.var_value_ciphertext
