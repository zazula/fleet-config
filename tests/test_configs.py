from __future__ import annotations

from fastapi.testclient import TestClient


def test_config_crud_round_trip(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/configs",
        json={"namespace": "agents", "key": "retry_count", "value": 3},
    )
    assert create_response.status_code == 201
    assert create_response.json() == {
        "namespace": "agents",
        "key": "retry_count",
        "value": 3,
        "version": 1,
    }

    read_response = client.get("/api/v1/configs/agents/retry_count")
    assert read_response.status_code == 200
    assert read_response.json() == create_response.json()

    update_response = client.put(
        "/api/v1/configs/agents/retry_count",
        json={"value": {"max": 5}},
    )
    assert update_response.status_code == 200
    assert update_response.json() == {
        "namespace": "agents",
        "key": "retry_count",
        "value": {"max": 5},
        "version": 2,
    }

    delete_response = client.delete("/api/v1/configs/agents/retry_count")
    assert delete_response.status_code == 200
    assert delete_response.json() == {
        "namespace": "agents",
        "key": "retry_count",
        "value": {"max": 5},
        "version": 2,
    }

    missing_after_delete = client.get("/api/v1/configs/agents/retry_count")
    assert missing_after_delete.status_code == 404


def test_missing_config_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/configs/missing/key")
    assert response.status_code == 404


def test_update_increments_version(client: TestClient) -> None:
    client.post(
        "/api/v1/configs",
        json={"namespace": "agents", "key": "timeout", "value": 30},
    )

    response = client.put("/api/v1/configs/agents/timeout", json={"value": 45})
    assert response.status_code == 200
    assert response.json()["version"] == 2
