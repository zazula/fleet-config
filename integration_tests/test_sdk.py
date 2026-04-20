from __future__ import annotations

import threading
import uuid

import pytest

from fleet_config import FleetConfigClient

BASE_URL = "http://127.0.0.1:8011"


@pytest.mark.integration
def test_sdk_round_trip_all_client_methods() -> None:
    namespace = f"sdk-{uuid.uuid4().hex[:8]}"
    key = f"cfg-{uuid.uuid4().hex[:8]}"
    flag = f"flag-{uuid.uuid4().hex[:8]}"

    client = FleetConfigClient(BASE_URL)
    try:
        created = client.set_config(key, "alpha", namespace=namespace)
        assert created.namespace == namespace
        assert created.key == key
        assert created.value == "alpha"
        assert created.version == 1

        fetched = client.get_config(key, namespace=namespace)
        assert fetched == created

        updated = client.set_config(key, "beta", namespace=namespace)
        assert updated.value == "beta"
        assert updated.version == 2

        listed = client.list_configs(namespace=namespace)
        assert len(listed) == 1
        assert listed[0] == updated

        import httpx

        with httpx.Client(base_url=BASE_URL, timeout=3.0) as http_client:
            create_flag = http_client.post(
                "/api/v1/flags",
                json={"name": flag, "enabled": True, "rollout_pct": 100, "rules": None},
            )
            assert create_flag.status_code == 201

        assert client.evaluate_flag(flag, "sdk-user") is True

        client.delete_config(key, namespace=namespace)
        assert client.list_configs(namespace=namespace) == []
    finally:
        client.close()
