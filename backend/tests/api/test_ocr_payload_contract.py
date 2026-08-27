from __future__ import annotations

from tests.support.constants import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME
from tests.support.runtime import app_client


def test_new_and_legacy_ocr_payloads_are_validated_and_preserved() -> None:
    with app_client(reset=True) as client:
        login_response = client.post(
            "/api/v1/sessions",
            json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
        )
        token = login_response.json()["data"]["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}
        workspace_response = client.post(
            "/api/v1/workspaces",
            json={
                "workspace_code": "ocr_contract_ws",
                "workspace_name": "OCR Contract",
            },
            headers=auth_headers,
        )
        workspace_id = workspace_response.json()["data"]["id"]
        headers = auth_headers | {"X-Workspace-Id": str(workspace_id)}
        case_response = client.post(
            "/api/v1/test-cases",
            json={
                "case_code": "ocr_contract_case",
                "case_name": "OCR Contract Case",
                "status": "published",
            },
            headers=headers,
        )
        test_case_id = case_response.json()["data"]["id"]

        response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "click",
                    "step_name": "Pure OCR Click",
                    "payload_json": {
                        "locator": "ocr",
                        "ocr_target": {
                            "text": "提交",
                            "match_mode": "fuzzy",
                            "scope": "page",
                            "language": "zh_en",
                            "role": "button",
                            "min_confidence": 0.8,
                            "min_score": 0.85,
                            "ambiguity_margin": 0.12,
                            "relation": {
                                "type": "right_of",
                                "anchor_text": "操作",
                                "max_distance_ratio": 0.3,
                            },
                        },
                    },
                },
                {
                    "step_no": 2,
                    "step_type": "input",
                    "step_name": "Legacy OCR Input",
                    "payload_json": {
                        "locator": "ocr",
                        "ocr_text": "用户名",
                        "ocr_match_mode": "contains",
                        "ocr_occurrence": 1,
                        "text": "tester",
                    },
                },
                {
                    "step_no": 3,
                    "step_type": "ocr_assert",
                    "step_name": "Legacy OCR Assert",
                    "payload_json": {
                        "selector": "#result",
                        "expected_text": "成功",
                        "match_mode": "contains",
                    },
                },
                {
                    "step_no": 4,
                    "step_type": "ocr_assert",
                    "step_name": "Pure OCR Assert",
                    "payload_json": {
                        "scope": "viewport",
                        "ocr_target": {
                            "text": "^提交成功$",
                            "match_mode": "regex",
                            "language": "auto",
                            "role": "text",
                        },
                    },
                },
                {
                    "step_no": 5,
                    "step_type": "ocr_assert",
                    "step_name": "Page OCR Count",
                    "payload_json": {
                        "scope": "page",
                        "assertion": "count",
                        "expected_count": 2,
                        "ocr_target": {
                            "text": "保存",
                            "scope": "page",
                        },
                    },
                },
                {
                    "step_no": 6,
                    "step_type": "ocr_assert",
                    "step_name": "OCR Relation",
                    "payload_json": {
                        "scope": "viewport",
                        "assertion": "relation",
                        "ocr_target": {
                            "text": "提交",
                            "relation": {
                                "type": "right_of",
                                "anchor_text": "操作",
                                "max_distance_ratio": 0.3,
                            },
                        },
                    },
                },
                {
                    "step_no": 7,
                    "step_type": "conditional_branch",
                    "step_name": "OCR Branch",
                    "payload_json": {
                        "branches": [
                            {
                                "branch_key": "visible",
                                "branch_name": "Visible",
                                "condition": {
                                    "type": "ocr_text_visible",
                                    "ocr_target": {"text": "提交成功"},
                                },
                                "steps": [
                                    {
                                        "step_type": "ocr_assert",
                                        "step_name": "Nested OCR Assert",
                                        "payload_json": {
                                            "scope": "viewport",
                                            "assertion": "absent",
                                            "ocr_target": {"text": "错误"},
                                        },
                                    }
                                ],
                            }
                        ]
                    },
                },
            ],
            headers=headers,
        )

        assert response.status_code == 200
        saved_steps = response.json()["data"]
        assert saved_steps[0]["payload_json"]["ocr_target"]["match_mode"] == "fuzzy"
        assert "ocr_text" not in saved_steps[0]["payload_json"]
        assert saved_steps[1]["payload_json"]["ocr_text"] == "用户名"
        assert "scope" not in saved_steps[2]["payload_json"]
        assert saved_steps[3]["payload_json"]["scope"] == "viewport"
        assert saved_steps[4]["payload_json"]["expected_count"] == 2
        assert (
            saved_steps[5]["payload_json"]["ocr_target"]["relation"]["type"]
            == "right_of"
        )
        assert (
            saved_steps[6]["payload_json"]["branches"][0]["condition"][
                "ocr_target"
            ]["text"]
            == "提交成功"
        )

        component_response = client.post(
            "/api/v1/components",
            json={
                "component_code": "ocr_contract_component",
                "component_name": "OCR Contract Component",
                "status": "published",
            },
            headers=headers,
        )
        component_id = component_response.json()["data"]["id"]
        component_steps_response = client.put(
            f"/api/v1/components/{component_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "ocr_assert",
                    "step_name": "Component OCR Count",
                    "payload_json": {
                        "scope": "viewport",
                        "assertion": "count",
                        "expected_count": 1,
                        "ocr_target": {"text": "完成"},
                    },
                }
            ],
            headers=headers,
        )
        assert component_steps_response.status_code == 200

        invalid_response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "click",
                    "step_name": "Nested Target Wins",
                    "payload_json": {
                        "locator": "ocr",
                        "ocr_text": "valid legacy fallback",
                        "ocr_target": {"text": "", "match_mode": "exact"},
                    },
                }
            ],
            headers=headers,
        )
        assert invalid_response.status_code == 422
        assert invalid_response.json()["error"]["code"] == "STEP_CONFIGURATION_INVALID"

        invalid_count_response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "ocr_assert",
                    "step_name": "Invalid Count",
                    "payload_json": {
                        "scope": "viewport",
                        "assertion": "count",
                        "ocr_target": {"text": "完成"},
                    },
                }
            ],
            headers=headers,
        )
        assert invalid_count_response.status_code == 422
        assert (
            invalid_count_response.json()["error"]["code"]
            == "STEP_CONFIGURATION_INVALID"
        )

        invalid_relation_response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "ocr_assert",
                    "step_name": "Invalid Relation",
                    "payload_json": {
                        "scope": "viewport",
                        "assertion": "relation",
                        "ocr_target": {"text": "完成"},
                    },
                }
            ],
            headers=headers,
        )
        assert invalid_relation_response.status_code == 422
