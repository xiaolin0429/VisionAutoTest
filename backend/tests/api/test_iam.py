from __future__ import annotations

from datetime import timedelta

from tests.support.constants import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME
from tests.support.runtime import _reset_local_data, app_client

def test_session_login_returns_jwt_token_shape():
    with app_client(reset=True) as client:
        response = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        assert response.status_code == 201
        payload = response.json()["data"]
        assert payload["token_type"] == "Bearer"
        assert payload["access_token"].count(".") == 2
        assert payload["session_id"].startswith("ses_")

def test_refresh_token_expired_returns_specific_error_and_marks_status():
    _reset_local_data()

    from app.db.session import SessionLocal
    from app.models import RefreshToken

    with app_client() as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        assert login_resp.status_code == 201
        refresh_token = login_resp.json()["data"]["refresh_token"]

        with SessionLocal() as db:
            token = db.query(RefreshToken).filter(RefreshToken.status == "active").one()
            token.expires_at = token.expires_at - timedelta(days=8)
            db.commit()

        refresh_resp = client.post("/api/v1/session-refreshes", json={"refresh_token": refresh_token})
        assert refresh_resp.status_code == 401
        assert refresh_resp.json()["error"]["code"] == "REFRESH_TOKEN_EXPIRED"

        with SessionLocal() as db:
            token = db.query(RefreshToken).filter(RefreshToken.token_hash.is_not(None)).one()
            assert token.status == "expired"

def test_revoked_session_refresh_token_returns_revoked_error():
    with app_client(reset=True) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        assert login_resp.status_code == 201
        payload = login_resp.json()["data"]
        token = payload["access_token"]
        refresh_token = payload["refresh_token"]
        headers = {"Authorization": f"Bearer {token}"}

        revoke_resp = client.delete("/api/v1/sessions/current", headers=headers)
        assert revoke_resp.status_code == 204

        refresh_resp = client.post("/api/v1/session-refreshes", json={"refresh_token": refresh_token})
        assert refresh_resp.status_code == 401
        assert refresh_resp.json()["error"]["code"] == "REFRESH_TOKEN_REVOKED"

        current_user_resp = client.get("/api/v1/users/current", headers=headers)
        assert current_user_resp.status_code == 401
        assert current_user_resp.json()["error"]["code"] == "TOKEN_REVOKED"

def test_used_refresh_token_returns_invalid_error():
    with app_client(reset=True) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        assert login_resp.status_code == 201
        refresh_token = login_resp.json()["data"]["refresh_token"]

        first_refresh_resp = client.post("/api/v1/session-refreshes", json={"refresh_token": refresh_token})
        assert first_refresh_resp.status_code == 201

        second_refresh_resp = client.post("/api/v1/session-refreshes", json={"refresh_token": refresh_token})
        assert second_refresh_resp.status_code == 401
        assert second_refresh_resp.json()["error"]["code"] == "REFRESH_TOKEN_INVALID"

def test_logout_makes_stale_refresh_token_return_revoked_error():
    with app_client(reset=True) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        assert login_resp.status_code == 201
        initial_payload = login_resp.json()["data"]
        old_refresh_token = initial_payload["refresh_token"]

        refresh_resp = client.post("/api/v1/session-refreshes", json={"refresh_token": old_refresh_token})
        assert refresh_resp.status_code == 201
        latest_payload = refresh_resp.json()["data"]
        latest_access_token = latest_payload["access_token"]

        revoke_resp = client.delete(
            "/api/v1/sessions/current",
            headers={"Authorization": f"Bearer {latest_access_token}"},
        )
        assert revoke_resp.status_code == 204

        stale_refresh_resp = client.post("/api/v1/session-refreshes", json={"refresh_token": old_refresh_token})
        assert stale_refresh_resp.status_code == 401
        assert stale_refresh_resp.json()["error"]["code"] == "REFRESH_TOKEN_REVOKED"
