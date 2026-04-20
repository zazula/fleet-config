from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status

from src.database import check_database_connection
from src.routers.configs import router as configs_router
from src.routers.flags import router as flags_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("fleet-config")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("startup", extra={"event": "startup", "service": "fleet-config"})
    yield


app = FastAPI(title="fleet-config", lifespan=lifespan)
app.include_router(configs_router)
app.include_router(flags_router)


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
