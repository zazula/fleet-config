from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime

import httpx

from fleet_config.models import ConfigChangeEvent


class WatchStream:
    def __init__(self, client: httpx.Client, url: str) -> None:
        self._client = client
        self._url = url
        self._response_cm: httpx.Response | None = None

    def __iter__(self) -> Iterator[ConfigChangeEvent]:
        with self._client.stream(
            "GET",
            self._url,
            headers={"Accept": "text/event-stream"},
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload = json.loads(line.removeprefix("data: "))
                yield ConfigChangeEvent(
                    type=payload["type"],
                    namespace=payload["namespace"],
                    key=payload["key"],
                    version=payload["version"],
                    timestamp=datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00")),
                )
