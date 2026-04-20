from __future__ import annotations

import hashlib
import uuid

import httpx
import pytest

BASE_URL = "http://127.0.0.1:8011"


def expected_enabled(agent_id: str, name: str, rollout_pct: float) -> bool:
    digest = hashlib.sha256(f"{agent_id}{name}".encode()).hexdigest()
    bucket = int(digest, 16) % 100
    return bucket < rollout_pct


@pytest.mark.integration
def test_flag_evaluation_rollouts_are_correct_and_deterministic() -> None:
    names = {
        "zero": f"flag-zero-{uuid.uuid4().hex[:8]}",
        "half": f"flag-half-{uuid.uuid4().hex[:8]}",
        "full": f"flag-full-{uuid.uuid4().hex[:8]}",
    }
    agent_id = f"user-{uuid.uuid4().hex[:8]}"

    with httpx.Client(base_url=BASE_URL, timeout=3.0) as client:
        for name, rollout_pct in ((names["zero"], 0), (names["half"], 50), (names["full"], 100)):
            response = client.post(
                "/api/v1/flags",
                json={"name": name, "enabled": True, "rollout_pct": rollout_pct, "rules": None},
            )
            assert response.status_code == 201

        zero_response = client.post(
            f"/api/v1/flags/{names['zero']}/evaluate",
            json={"agent_id": agent_id, "context": {}},
        )
        assert zero_response.status_code == 200
        assert zero_response.json() == {
            "name": names["zero"],
            "enabled": False,
            "reason": "zero rollout",
        }

        full_response = client.post(
            f"/api/v1/flags/{names['full']}/evaluate",
            json={"agent_id": agent_id, "context": {}},
        )
        assert full_response.status_code == 200
        assert full_response.json() == {
            "name": names["full"],
            "enabled": True,
            "reason": "full rollout",
        }

        half_first = client.post(
            f"/api/v1/flags/{names['half']}/evaluate",
            json={"agent_id": agent_id, "context": {"env": "qa"}},
        )
        half_second = client.post(
            f"/api/v1/flags/{names['half']}/evaluate",
            json={"agent_id": agent_id, "context": {"env": "prod"}},
        )
        assert half_first.status_code == 200
        assert half_second.status_code == 200
        assert half_first.json() == half_second.json()
        body = half_first.json()
        assert body["name"] == names["half"]
        assert body["enabled"] is expected_enabled(agent_id, names["half"], 50)
        assert body["reason"].startswith("agent bucket ")
