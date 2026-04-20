from __future__ import annotations

import json

import httpx
import pytest

from fleet_config.client import FleetConfigClient
from fleet_config.errors import ConfigNotFound, FlagNotFound, ServiceError


def test_get_config_returns_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/configs/agents/retry_count"
        return httpx.Response(
            200,
            json={"namespace": "agents", "key": "retry_count", "value": 3, "version": 1},
        )

    transport = httpx.MockTransport(handler)
    client = FleetConfigClient("https://example.test")
    client._client = httpx.Client(transport=transport, base_url="https://example.test")

    config = client.get_config("retry_count", namespace="agents")
    assert config.namespace == "agents"
    assert config.key == "retry_count"
    assert config.value == 3
    assert config.version == 1


def test_get_config_raises_not_found() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(404, json={"detail": "not found"})
    )
    client = FleetConfigClient("https://example.test")
    client._client = httpx.Client(transport=transport, base_url="https://example.test")

    with pytest.raises(ConfigNotFound):
        client.get_config("missing")


def test_set_config_creates_then_returns_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        payload = json.loads(request.content.decode())
        assert payload == {"namespace": "default", "key": "timeout", "value": "30"}
        return httpx.Response(
            201,
            json={"namespace": "default", "key": "timeout", "value": "30", "version": 1},
        )

    client = FleetConfigClient("https://example.test")
    client._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test")

    config = client.set_config("timeout", "30")
    assert config.version == 1


def test_set_config_updates_on_conflict() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        if request.method == "POST":
            return httpx.Response(409, json={"detail": "exists"})
        return httpx.Response(
            200,
            json={"namespace": "default", "key": "timeout", "value": "45", "version": 2},
        )

    client = FleetConfigClient("https://example.test")
    client._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test")

    config = client.set_config("timeout", "45")
    assert calls == ["POST", "PUT"]
    assert config.version == 2


def test_delete_config_raises_not_found() -> None:
    client = FleetConfigClient("https://example.test")
    client._client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(404)),
        base_url="https://example.test",
    )

    with pytest.raises(ConfigNotFound):
        client.delete_config("missing")


def test_list_configs_raises_service_error() -> None:
    client = FleetConfigClient("https://example.test")
    with pytest.raises(ServiceError):
        client.list_configs()


def test_evaluate_flag_returns_boolean() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/flags/beta/evaluate"
        return httpx.Response(200, json={"name": "beta", "enabled": True, "reason": "full rollout"})

    client = FleetConfigClient("https://example.test")
    client._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test")

    assert client.evaluate_flag("beta", "user-1") is True


def test_evaluate_flag_raises_not_found() -> None:
    client = FleetConfigClient("https://example.test")
    client._client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(404)),
        base_url="https://example.test",
    )

    with pytest.raises(FlagNotFound):
        client.evaluate_flag("missing", "user-1")
