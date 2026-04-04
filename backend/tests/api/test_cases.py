from __future__ import annotations

from tests.support.constants import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME
from tests.support.runtime import app_client


def test_invalid_template_assert_step_is_rejected_during_step_save():
    with app_client(reset=True) as client:
        login_resp = client.post(
            "/api/v1/sessions",
            json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
        )
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={
                "workspace_code": "unsupported_ws",
                "workspace_name": "Unsupported WS",
            },
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        case_resp = client.post(
            "/api/v1/test-cases",
            json={
                "case_code": "unsupported_case",
                "case_name": "Unsupported Case",
                "status": "published",
            },
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "template_assert",
                    "step_name": "Unsupported",
                    "payload_json": {},
                }
            ],
            headers=workspace_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "STEP_CONFIGURATION_INVALID"


def test_invalid_ocr_assert_step_is_rejected_during_step_save():
    with app_client(reset=True) as client:
        login_resp = client.post(
            "/api/v1/sessions",
            json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
        )
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={
                "workspace_code": "invalid_ocr_ws",
                "workspace_name": "Invalid OCR WS",
            },
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        case_resp = client.post(
            "/api/v1/test-cases",
            json={
                "case_code": "invalid_ocr_case",
                "case_name": "Invalid OCR Case",
                "status": "published",
            },
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "ocr_assert",
                    "step_name": "Invalid OCR",
                    "payload_json": {"selector": "#main"},
                }
            ],
            headers=workspace_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "STEP_CONFIGURATION_INVALID"


def test_new_step_types_are_saved_for_components_and_test_cases():
    with app_client(reset=True) as client:
        login_resp = client.post(
            "/api/v1/sessions",
            json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
        )
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "new_steps_ws", "workspace_name": "New Steps WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        component_resp = client.post(
            "/api/v1/components",
            json={
                "component_code": "cmp_new_steps",
                "component_name": "New Steps Component",
                "status": "published",
            },
            headers=workspace_headers,
        )
        component_id = component_resp.json()["data"]["id"]

        component_steps_resp = client.put(
            f"/api/v1/components/{component_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "navigate",
                    "step_name": "Open Details",
                    "payload_json": {"url": "/demo/acceptance-target?view=details"},
                    "timeout_ms": 21000,
                    "retry_times": 1,
                },
                {
                    "step_no": 2,
                    "step_type": "scroll",
                    "step_name": "Scroll Container",
                    "payload_json": {
                        "target": "element",
                        "selector": "[data-testid='scroll-container']",
                        "direction": "down",
                        "distance": 220,
                    },
                    "timeout_ms": 22000,
                    "retry_times": 2,
                },
                {
                    "step_no": 3,
                    "step_type": "long_press",
                    "step_name": "Press Target",
                    "payload_json": {
                        "selector": "[data-testid='long-press-target']",
                        "duration_ms": 800,
                    },
                    "timeout_ms": 23000,
                    "retry_times": 3,
                },
            ],
            headers=workspace_headers,
        )
        assert component_steps_resp.status_code == 200
        assert [item["step_type"] for item in component_steps_resp.json()["data"]] == [
            "navigate",
            "scroll",
            "long_press",
        ]
        assert [item["timeout_ms"] for item in component_steps_resp.json()["data"]] == [
            21000,
            22000,
            23000,
        ]
        assert [
            item["retry_times"] for item in component_steps_resp.json()["data"]
        ] == [1, 2, 3]

        case_resp = client.post(
            "/api/v1/test-cases",
            json={
                "case_code": "case_new_steps",
                "case_name": "Case New Steps",
                "status": "published",
            },
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        case_steps_resp = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "navigate",
                    "step_name": "Open Details",
                    "payload_json": {
                        "url": "/demo/acceptance-target?view=details",
                        "wait_until": "domcontentloaded",
                    },
                },
                {
                    "step_no": 2,
                    "step_type": "scroll",
                    "step_name": "Scroll Page",
                    "payload_json": {
                        "target": "page",
                        "direction": "down",
                        "distance": 360,
                        "behavior": "smooth",
                    },
                },
                {
                    "step_no": 3,
                    "step_type": "long_press",
                    "step_name": "Press Target",
                    "payload_json": {
                        "selector": "[data-testid='long-press-target']",
                        "duration_ms": 800,
                        "button": "left",
                    },
                },
            ],
            headers=workspace_headers,
        )
        assert case_steps_resp.status_code == 200
        assert [item["step_type"] for item in case_steps_resp.json()["data"]] == [
            "navigate",
            "scroll",
            "long_press",
        ]
        assert (
            case_steps_resp.json()["data"][0]["payload_json"]["wait_until"]
            == "domcontentloaded"
        )
        assert case_steps_resp.json()["data"][1]["payload_json"]["behavior"] == "smooth"


def test_invalid_navigate_step_is_rejected_during_step_save():
    with app_client(reset=True) as client:
        login_resp = client.post(
            "/api/v1/sessions",
            json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
        )
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={
                "workspace_code": "invalid_nav_ws",
                "workspace_name": "Invalid Navigate WS",
            },
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        case_resp = client.post(
            "/api/v1/test-cases",
            json={
                "case_code": "invalid_nav_case",
                "case_name": "Invalid Navigate Case",
                "status": "published",
            },
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "navigate",
                    "step_name": "Invalid Navigate",
                    "payload_json": {"url": "login", "wait_until": "ready"},
                }
            ],
            headers=workspace_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "STEP_CONFIGURATION_INVALID"


def test_invalid_scroll_step_is_rejected_during_step_save():
    with app_client(reset=True) as client:
        login_resp = client.post(
            "/api/v1/sessions",
            json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
        )
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={
                "workspace_code": "invalid_scroll_ws",
                "workspace_name": "Invalid Scroll WS",
            },
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        case_resp = client.post(
            "/api/v1/test-cases",
            json={
                "case_code": "invalid_scroll_case",
                "case_name": "Invalid Scroll Case",
                "status": "published",
            },
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "scroll",
                    "step_name": "Invalid Scroll",
                    "payload_json": {
                        "target": "element",
                        "direction": "down",
                        "distance": 0,
                    },
                }
            ],
            headers=workspace_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "STEP_CONFIGURATION_INVALID"


def test_invalid_long_press_step_is_rejected_during_step_save():
    with app_client(reset=True) as client:
        login_resp = client.post(
            "/api/v1/sessions",
            json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
        )
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={
                "workspace_code": "invalid_press_ws",
                "workspace_name": "Invalid Long Press WS",
            },
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        case_resp = client.post(
            "/api/v1/test-cases",
            json={
                "case_code": "invalid_press_case",
                "case_name": "Invalid Long Press Case",
                "status": "published",
            },
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "long_press",
                    "step_name": "Invalid Long Press",
                    "payload_json": {
                        "selector": "#target",
                        "duration_ms": -1,
                        "button": "right",
                    },
                }
            ],
            headers=workspace_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "STEP_CONFIGURATION_INVALID"


def test_conditional_branch_steps_are_saved_for_test_cases_only():
    with app_client(reset=True) as client:
        login_resp = client.post(
            "/api/v1/sessions",
            json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
        )
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={
                "workspace_code": "branch_steps_ws",
                "workspace_name": "Branch Steps WS",
            },
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        case_resp = client.post(
            "/api/v1/test-cases",
            json={
                "case_code": "branch_case",
                "case_name": "Branch Case",
                "status": "published",
            },
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "conditional_branch",
                    "step_name": "Conditional Step",
                    "payload_json": {
                        "branches": [
                            {
                                "branch_key": "if_a",
                                "branch_name": "出现A",
                                "condition": {
                                    "type": "selector_exists",
                                    "selector": ".state-a",
                                },
                                "steps": [
                                    {
                                        "step_type": "click",
                                        "step_name": "点击A",
                                        "payload_json": {"selector": ".btn-a"},
                                        "timeout_ms": 15000,
                                        "retry_times": 0,
                                    }
                                ],
                            }
                        ],
                        "else_branch": {
                            "enabled": True,
                            "branch_name": "默认分支",
                            "steps": [
                                {
                                    "step_type": "wait",
                                    "step_name": "等待",
                                    "payload_json": {"ms": 100},
                                    "timeout_ms": 15000,
                                    "retry_times": 0,
                                }
                            ],
                        },
                    },
                }
            ],
            headers=workspace_headers,
        )
        assert response.status_code == 200
        assert response.json()["data"][0]["step_type"] == "conditional_branch"


def test_conditional_branch_is_rejected_inside_component_steps():
    with app_client(reset=True) as client:
        login_resp = client.post(
            "/api/v1/sessions",
            json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
        )
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={
                "workspace_code": "branch_component_ws",
                "workspace_name": "Branch Component WS",
            },
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        component_resp = client.post(
            "/api/v1/components",
            json={
                "component_code": "component_branch",
                "component_name": "Component Branch",
                "status": "published",
            },
            headers=workspace_headers,
        )
        component_id = component_resp.json()["data"]["id"]

        response = client.put(
            f"/api/v1/components/{component_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "conditional_branch",
                    "step_name": "Invalid Branch",
                    "payload_json": {
                        "branches": [
                            {
                                "branch_key": "if_a",
                                "branch_name": "出现A",
                                "condition": {
                                    "type": "selector_exists",
                                    "selector": ".state-a",
                                },
                                "steps": [
                                    {
                                        "step_type": "wait",
                                        "step_name": "等待",
                                        "payload_json": {"ms": 100},
                                        "timeout_ms": 15000,
                                        "retry_times": 0,
                                    }
                                ],
                            }
                        ]
                    },
                }
            ],
            headers=workspace_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "STEP_CONFIGURATION_INVALID"


def test_conditional_branch_rejects_nested_branch_steps_and_component_calls():
    with app_client(reset=True) as client:
        login_resp = client.post(
            "/api/v1/sessions",
            json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
        )
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={
                "workspace_code": "branch_invalid_ws",
                "workspace_name": "Branch Invalid WS",
            },
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        case_resp = client.post(
            "/api/v1/test-cases",
            json={
                "case_code": "branch_invalid_case",
                "case_name": "Branch Invalid Case",
                "status": "published",
            },
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "conditional_branch",
                    "step_name": "Invalid Conditional Step",
                    "payload_json": {
                        "branches": [
                            {
                                "branch_key": "if_a",
                                "branch_name": "出现A",
                                "condition": {
                                    "type": "selector_exists",
                                    "selector": ".state-a",
                                },
                                "steps": [
                                    {
                                        "step_type": "conditional_branch",
                                        "step_name": "Nested",
                                        "payload_json": {},
                                        "timeout_ms": 15000,
                                        "retry_times": 0,
                                    }
                                ],
                            }
                        ]
                    },
                }
            ],
            headers=workspace_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "STEP_CONFIGURATION_INVALID"


def test_test_suite_execution_readiness_returns_unpublished_case_issue():
    with app_client(reset=True) as client:
        login_resp = client.post(
            "/api/v1/sessions",
            json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
        )
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={
                "workspace_code": "suite_ready_ws",
                "workspace_name": "Suite Ready WS",
            },
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        assert env_resp.status_code == 201

        case_resp = client.post(
            "/api/v1/test-cases",
            json={
                "case_code": "draft_case",
                "case_name": "Draft Case",
                "status": "draft",
            },
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={
                "suite_code": "suite_ready",
                "suite_name": "Suite Ready",
                "status": "active",
            },
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]

        replace_resp = client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )
        assert replace_resp.status_code == 200

        readiness_resp = client.get(
            f"/api/v1/test-suites/{test_suite_id}/execution-readiness",
            headers=workspace_headers,
        )
        assert readiness_resp.status_code == 200
        readiness = readiness_resp.json()["data"]
        assert readiness["scope"] == "test_suite"
        assert readiness["status"] == "blocked"
        assert readiness["active_environment_count"] == 1
        assert readiness["test_suite_id"] == test_suite_id
        assert any(
            issue["code"] == "PUBLISHED_VERSION_REQUIRED"
            and issue["resource_type"] == "test_case"
            and issue["resource_id"] == test_case_id
            for issue in readiness["issues"]
        )
