from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.routing import APIRoute

from src.main import app, watcher_registry
from src.watchers import WatcherRegistry


def test_watch_namespace_endpoint_exists() -> None:
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    watch_route = next(route for route in routes if route.path == "/api/v1/watch/{namespace}")
    assert "GET" in watch_route.methods


def test_watch_global_endpoint_exists() -> None:
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    watch_route = next(route for route in routes if route.path == "/api/v1/watch")
    assert "GET" in watch_route.methods


@pytest.mark.anyio
async def test_watcher_registry_streams_updated_namespace_only() -> None:
    registry = WatcherRegistry(poll_interval=0.05)

    watch_id, watch_queue = await registry.subscribe("agents")
    global_id, global_queue = await registry.subscribe()
    other_id, other_queue = await registry.subscribe("other")

    try:
        from src.database import SessionLocal
        from src.models.config_key import ConfigKey

        session = SessionLocal()
        try:
            config = ConfigKey(namespace="agents", key="retry_count", value=1, version=1)
            session.add(config)
            session.commit()
            session.refresh(config)

            config.value = 2
            config.version = 2
            session.add(config)
            session.commit()
            session.refresh(config)
        finally:
            session.close()

        event = await asyncio.wait_for(watch_queue.get(), timeout=2)
        global_event = await asyncio.wait_for(global_queue.get(), timeout=2)

        parsed = json.loads(event.removeprefix("data: ").strip())
        parsed_global = json.loads(global_event.removeprefix("data: ").strip())

        assert parsed["type"] == "config_updated"
        assert parsed["namespace"] == "agents"
        assert parsed["key"] == "retry_count"
        assert parsed["version"] == 1 or parsed["version"] == 2
        assert isinstance(parsed["timestamp"], str)

        assert parsed_global["namespace"] == "agents"
        assert parsed_global["key"] == "retry_count"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(other_queue.get(), timeout=0.2)
    finally:
        await registry.unsubscribe(watch_id)
        await registry.unsubscribe(global_id)
        await registry.unsubscribe(other_id)


@pytest.mark.anyio
async def test_app_registry_emits_updated_config_event() -> None:
    watch_id, watch_queue = await watcher_registry.subscribe("agents")

    try:
        from src.database import SessionLocal
        from src.models.config_key import ConfigKey

        session = SessionLocal()
        try:
            config = ConfigKey(namespace="agents", key="timeout", value=30, version=1)
            session.add(config)
            session.commit()
            session.refresh(config)

            config.value = 45
            config.version = 2
            session.add(config)
            session.commit()
        finally:
            session.close()

        deadline = asyncio.get_running_loop().time() + 2
        while True:
            event = await asyncio.wait_for(watch_queue.get(), timeout=2)
            parsed = json.loads(event.removeprefix("data: ").strip())
            if parsed["key"] == "timeout" and parsed["version"] == 2:
                assert parsed == {
                    "type": "config_updated",
                    "namespace": "agents",
                    "key": "timeout",
                    "version": 2,
                    "timestamp": parsed["timestamp"],
                }
                assert isinstance(parsed["timestamp"], str)
                break
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError("Timed out waiting for version 2 watch event")
    finally:
        await watcher_registry.unsubscribe(watch_id)
