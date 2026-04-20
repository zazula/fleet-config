from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import StreamingResponse
from alembic import command
from alembic.config import Config

from src.database import check_database_connection, ensure_schema
from src.routers.configs import router as configs_router
from src.routers.flags import router as flags_router
from src.watchers import WatcherRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("fleet-config")
watcher_registry = WatcherRegistry()


def run_startup_migrations() -> None:
    alembic_ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    config = Config(str(alembic_ini))
    command.upgrade(config, "head")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    run_startup_migrations()
    ensure_schema()
    logger.info("startup", extra={"event": "startup", "service": "fleet-config"})
    yield


app = FastAPI(title="fleet-config", lifespan=lifespan)
app.include_router(configs_router)
app.include_router(flags_router)


async def watch_stream(request: Request, namespace: str | None = None) -> StreamingResponse:
    async def event_generator() -> AsyncIterator[str]:
        watcher_id, queue = await watcher_registry.subscribe(namespace)

        try:
            while True:
                if await request.is_disconnected():
                    break
                yield await queue.get()
        finally:
            await watcher_registry.unsubscribe(watcher_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/v1/watch")
async def watch_all(request: Request) -> StreamingResponse:
    return await watch_stream(request)


@app.get("/api/v1/watch/{namespace}")
async def watch_namespace(namespace: str, request: Request) -> StreamingResponse:
    return await watch_stream(request, namespace)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readiness")
async def readiness(response: Response) -> dict[str, str]:
    try:
        check_database_connection()
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready"}
    return {"status": "ready"}
