from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient


def expected_enabled(agent_id: str, name: str, rollout_pct: float) -> bool:
    digest = hashlib.sha256(f"{agent_id}{name}".encode()).hexdigest()
    bucket = int(digest, 16) % 100
    return bucket < rollout_pct


def test_create_flag(client: TestClient) -> None:
    response = client.post(
        "/api/v1/flags",
        json={"name": "beta-ui", "enabled": True, "rollout_pct": 25, "rules": {"team": "qa"}},
    )
    assert response.status_code == 201
    assert response.json() == {
        "name": "beta-ui",
        "enabled": True,
        "rollout_pct": 25.0,
        "rules": {"team": "qa"},
    }


def test_evaluate_flag_at_full_rollout_returns_true(client: TestClient) -> None:
    client.post("/api/v1/flags", json={"name": "always-on", "enabled": True, "rollout_pct": 100})

    response = client.post(
        "/api/v1/flags/always-on/evaluate",
        json={"agent_id": "agent-1", "context": {}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "name": "always-on",
        "enabled": True,
        "reason": "full rollout",
    }


def test_evaluate_flag_at_zero_rollout_returns_false(client: TestClient) -> None:
    client.post("/api/v1/flags", json={"name": "always-off", "enabled": True, "rollout_pct": 0})

    response = client.post(
        "/api/v1/flags/always-off/evaluate",
        json={"agent_id": "agent-1", "context": {}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "name": "always-off",
        "enabled": False,
        "reason": "zero rollout",
    }


def test_evaluate_flag_at_half_rollout_is_deterministic(client: TestClient) -> None:
    client.post("/api/v1/flags", json={"name": "gradual", "enabled": True, "rollout_pct": 50})

    response = client.post(
        "/api/v1/flags/gradual/evaluate",
        json={"agent_id": "agent-42", "context": {"env": "test"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "gradual"
    assert body["enabled"] is expected_enabled("agent-42", "gradual", 50)


def test_flag_crud_round_trip(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/flags",
        json={"name": "canary", "enabled": True, "rollout_pct": 10, "rules": None},
    )
    assert create_response.status_code == 201

    read_response = client.get("/api/v1/flags/canary")
    assert read_response.status_code == 200
    assert read_response.json() == {
        "name": "canary",
        "enabled": True,
        "rollout_pct": 10.0,
        "rules": None,
    }

    update_response = client.put(
        "/api/v1/flags/canary",
        json={"enabled": True, "rollout_pct": 55, "rules": {"region": "us"}},
    )
    assert update_response.status_code == 200
    assert update_response.json() == {
        "name": "canary",
        "enabled": True,
        "rollout_pct": 55.0,
        "rules": {"region": "us"},
    }

    delete_response = client.delete("/api/v1/flags/canary")
    assert delete_response.status_code == 200
    assert delete_response.json() == {
        "name": "canary",
        "enabled": False,
        "rollout_pct": 55.0,
        "rules": {"region": "us"},
    }


def test_missing_flag_returns_404(client: TestClient) -> None:
    get_response = client.get("/api/v1/flags/missing")
    assert get_response.status_code == 404

    evaluate_response = client.post(
        "/api/v1/flags/missing/evaluate",
        json={"agent_id": "agent-1", "context": {}},
    )
    assert evaluate_response.status_code == 404
