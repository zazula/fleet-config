from __future__ import annotations

import asyncio
import json
import uuid

import httpx
import pytest

BASE_URL = "http://127.0.0.1:8011"


async def _read_watch_event(namespace: str, key: str) -> dict[str, object]:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        async with client.stream("GET", f"/api/v1/watch/{namespace}") as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = json.loads(line.removeprefix("data: "))
                if payload.get("key") == key and payload.get("version") == 1:
                    return payload
    raise AssertionError("SSE stream ended before target event")


@pytest.mark.integration
@pytest.mark.anyio
async def test_watch_receives_config_mutation_within_three_seconds() -> None:
    namespace = f"watch-{uuid.uuid4().hex[:8]}"
    key = f"cfg-{uuid.uuid4().hex[:8]}"

    watch_task = asyncio.create_task(_read_watch_event(namespace, key))
    await asyncio.sleep(0.2)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=3.0) as client:
        response = await client.post(
            "/api/v1/configs",
            json={"namespace": namespace, "key": key, "value": {"enabled": True}},
        )
        assert response.status_code == 201

    event = await asyncio.wait_for(watch_task, timeout=3.0)
    assert event["type"] == "config_updated"
    assert event["namespace"] == namespace
    assert event["key"] == key
    assert event["version"] == 1
    assert isinstance(event["timestamp"], str)
