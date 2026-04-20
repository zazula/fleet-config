from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from src.main import app


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    yield
    if os.path.exists("test.db"):
        os.remove("test.db")


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
