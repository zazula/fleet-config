from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from src.main import app, watcher_registry


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    if os.path.exists("test.db"):
        os.remove("test.db")
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    yield
    if os.path.exists("test.db"):
        os.remove("test.db")


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_config_keys() -> Iterator[None]:
    watcher_registry._last_emitted_at = datetime.min.replace(tzinfo=UTC)  # type: ignore[attr-defined]
    watcher_registry._last_emitted_id = 0  # type: ignore[attr-defined]
    yield
    from src.database import SessionLocal
    from src.models.config_key import ConfigKey
    from src.models.feature_flag import FeatureFlag

    session = SessionLocal()
    try:
        session.query(FeatureFlag).delete()
        session.query(ConfigKey).delete()
        session.commit()
    finally:
        session.close()
