from __future__ import annotations

import httpx

from fleet_config.client import FleetConfigClient


def test_watch_stream_parses_sse_events() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = (
            b'data: {"type": "config_updated", "namespace": "agents", "key": "timeout", '
            b'"version": 2, "timestamp": "2026-04-20T20:00:00Z"}\n\n'
        )
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=body,
        )

    client = FleetConfigClient("https://example.test")
    client._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test")

    stream = client.watch(namespace="agents")
    event = next(iter(stream))

    assert event.type == "config_updated"
    assert event.namespace == "agents"
    assert event.key == "timeout"
    assert event.version == 2
    assert event.timestamp.isoformat() == "2026-04-20T20:00:00+00:00"
