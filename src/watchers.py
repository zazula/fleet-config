from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select

from src.database import SessionLocal
from src.models.config_key import ConfigKey


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def format_config_updated_event(
    *,
    namespace: str,
    key: str,
    version: int,
    timestamp: datetime,
) -> str:
    payload = json.dumps(
        {
            "type": "config_updated",
            "namespace": namespace,
            "key": key,
            "version": version,
            "timestamp": _normalize_timestamp(timestamp).isoformat().replace("+00:00", "Z"),
        }
    )
    return f"data: {payload}\n\n"


class WatcherRegistry:
    def __init__(self, poll_interval: float = 1.0) -> None:
        self._watchers: dict[int, tuple[str | None, asyncio.Queue[str]]] = {}
        self._next_id = 1
        self._lock = asyncio.Lock()
        self._poll_interval = poll_interval
        self._poller_task: asyncio.Task[None] | None = None
        self._last_emitted_at = datetime.min.replace(tzinfo=UTC)
        self._last_emitted_id = 0

    async def subscribe(self, namespace: str | None = None) -> tuple[int, asyncio.Queue[str]]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        async with self._lock:
            watcher_id = self._next_id
            self._next_id += 1
            self._watchers[watcher_id] = (namespace, queue)
            if self._poller_task is None or self._poller_task.done():
                self._poller_task = asyncio.create_task(self._poll_loop())
        return watcher_id, queue

    async def unsubscribe(self, watcher_id: int) -> None:
        poller_to_cancel: asyncio.Task[None] | None = None
        async with self._lock:
            self._watchers.pop(watcher_id, None)
            if not self._watchers and self._poller_task is not None:
                poller_to_cancel = self._poller_task
                self._poller_task = None

        if poller_to_cancel is not None:
            poller_to_cancel.cancel()
            try:
                await poller_to_cancel
            except asyncio.CancelledError:
                pass

    async def stream(self, namespace: str | None = None) -> AsyncIterator[str]:
        watcher_id, queue = await self.subscribe(namespace)
        try:
            while True:
                yield await queue.get()
        finally:
            await self.unsubscribe(watcher_id)

    async def _poll_loop(self) -> None:
        try:
            while True:
                await self._emit_changes()
                await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            raise

    async def _emit_changes(self) -> None:
        session = SessionLocal()
        try:
            statement = (
                select(ConfigKey)
                .where(
                    or_(
                        ConfigKey.updated_at > self._last_emitted_at,
                        and_(
                            ConfigKey.updated_at == self._last_emitted_at,
                            ConfigKey.id > self._last_emitted_id,
                        ),
                    )
                )
                .order_by(ConfigKey.updated_at.asc(), ConfigKey.id.asc())
            )
            changed_configs = session.scalars(statement).all()
        finally:
            session.close()

        for config in changed_configs:
            normalized_updated_at = _normalize_timestamp(config.updated_at)
            event = format_config_updated_event(
                namespace=config.namespace,
                key=config.key,
                version=config.version,
                timestamp=config.updated_at,
            )

            async with self._lock:
                queues = [
                    queue
                    for watcher_namespace, queue in self._watchers.values()
                    if watcher_namespace is None or watcher_namespace == config.namespace
                ]

            for queue in queues:
                await queue.put(event)

            self._last_emitted_at = normalized_updated_at
            self._last_emitted_id = config.id
