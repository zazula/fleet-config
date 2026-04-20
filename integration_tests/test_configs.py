from __future__ import annotations

import uuid

import httpx
import pytest

BASE_URL = "http://127.0.0.1:8011"


@pytest.mark.integration
def test_configs_crud_lifecycle_and_namespace_isolation() -> None:
    key = f"retry-{uuid.uuid4().hex[:8]}"
    ns1 = f"ns1-{uuid.uuid4().hex[:6]}"
    ns2 = f"ns2-{uuid.uuid4().hex[:6]}"

    with httpx.Client(base_url=BASE_URL, timeout=3.0) as client:
        create_response = client.post(
            "/api/v1/configs",
            json={"namespace": ns1, "key": key, "value": {"retries": 3}},
        )
        assert create_response.status_code == 201
        assert create_response.json() == {
            "namespace": ns1,
            "key": key,
            "value": {"retries": 3},
            "version": 1,
        }

        read_response = client.get(f"/api/v1/configs/{ns1}/{key}")
        assert read_response.status_code == 200
        assert read_response.json() == create_response.json()

        isolated_response = client.get(f"/api/v1/configs/{ns2}/{key}")
        assert isolated_response.status_code == 404

        update_response = client.put(
            f"/api/v1/configs/{ns1}/{key}",
            json={"value": {"retries": 5, "backoff": "exp"}},
        )
        assert update_response.status_code == 200
        assert update_response.json() == {
            "namespace": ns1,
            "key": key,
            "value": {"retries": 5, "backoff": "exp"},
            "version": 2,
        }

        list_response = client.get("/api/v1/configs")
        assert list_response.status_code == 200
        listed = list_response.json()
        assert any(item["namespace"] == ns1 and item["key"] == key for item in listed)
        assert all(not (item["namespace"] == ns2 and item["key"] == key) for item in listed)

        filtered_list_response = client.get("/api/v1/configs", params={"namespace": ns1})
        assert filtered_list_response.status_code == 200
        assert filtered_list_response.json() == [update_response.json()]

        delete_response = client.delete(f"/api/v1/configs/{ns1}/{key}")
        assert delete_response.status_code == 200
        assert delete_response.json() == update_response.json()

        missing_after_delete = client.get(f"/api/v1/configs/{ns1}/{key}")
        assert missing_after_delete.status_code == 404

        empty_list_response = client.get("/api/v1/configs", params={"namespace": ns1})
        assert empty_list_response.status_code == 200
        assert empty_list_response.json() == []
