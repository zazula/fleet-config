from __future__ import annotations

import httpx
import pytest

BASE_URL = "http://127.0.0.1:8011"


@pytest.mark.integration
def test_openapi_contract_exposes_required_paths_and_fields() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=3.0) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        payload = response.json()

    paths = payload["paths"]
    assert "/api/v1/configs" in paths
    assert "/api/v1/flags/{name}/evaluate" in paths
    assert "/api/v1/watch" in paths

    config_create = payload["components"]["schemas"]["ConfigCreate"]
    assert set(config_create["required"]) >= {"namespace", "key", "value"}

    config_update = payload["components"]["schemas"]["ConfigUpdate"]
    assert "value" in config_update["required"]

    evaluation_request = payload["components"]["schemas"]["FlagEvaluationRequest"]
    assert set(evaluation_request["required"]) >= {"agent_id", "context"}
