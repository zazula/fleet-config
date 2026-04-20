from __future__ import annotations

import os
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import uvicorn

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = 'http://127.0.0.1:8011'


@pytest.fixture(scope='session', autouse=True)
def live_service() -> Iterator[None]:
    os.environ.pop('DATABASE_URL', None)
    os.chdir(ROOT)

    config = uvicorn.Config('src.main:app', host='127.0.0.1', port=8011, log_level='warning')
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                response = httpx.get(f'{BASE_URL}/health', timeout=0.5)
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
        else:
            raise RuntimeError('Timed out waiting for live service')
        yield
    finally:
        server.should_exit = True
        thread.join(timeout=5)
