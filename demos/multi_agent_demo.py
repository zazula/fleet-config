from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from asyncio.subprocess import Process
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


HOST = "127.0.0.1"
PORT = 8002
BASE_URL = f"http://{HOST}:{PORT}"
REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"


def log(agent: str, message: str) -> None:
    print(f"[{agent}] {message}", flush=True)


def http_request(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"

    request = Request(urljoin(BASE_URL, path), data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=5) as response:
            body = response.read().decode()
            return json.loads(body) if body else None
    except HTTPError as exc:
        body = exc.read().decode()
        detail = body or exc.reason
        raise RuntimeError(f"{method} {path} failed with {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"{method} {path} failed: {exc.reason}") from exc


async def wait_for_service() -> None:
    for _ in range(60):
        try:
            response = await asyncio.to_thread(http_request, "GET", "/health")
        except RuntimeError:
            await asyncio.sleep(0.25)
            continue
        if response == {"status": "ok"}:
            return
    raise RuntimeError("fleet-config did not become healthy on port 8002")


async def start_service() -> Process:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(REPO_ROOT))
    database_path = REPO_ROOT / "demo_coordination.db"
    env["DATABASE_URL"] = f"sqlite:///{database_path}"
    python_executable = str(SERVICE_PYTHON if SERVICE_PYTHON.exists() else Path(sys.executable))
    process = await asyncio.create_subprocess_exec(
        python_executable,
        "-m",
        "uvicorn",
        "src.main:app",
        "--host",
        HOST,
        "--port",
        str(PORT),
        cwd=str(REPO_ROOT),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    await wait_for_service()
    log("system", f"fleet-config service started on {BASE_URL}")
    return process


async def stop_service(process: Process) -> None:
    if process.returncode is not None:
        return
    process.send_signal(signal.SIGINT)
    try:
        await asyncio.wait_for(process.wait(), timeout=10)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
    log("system", "fleet-config service stopped")


async def stream_service_logs(process: Process) -> None:
    if process.stdout is None:
        return
    while True:
        line = await process.stdout.readline()
        if not line:
            return
        text = line.decode().rstrip()
        if text:
            print(f"[fleet-config] {text}", flush=True)


async def worker_agent(name: str, ready: asyncio.Event, finished: asyncio.Event) -> None:
    log(name, "subscribing to namespace watch stream")
    reader, writer = await asyncio.open_connection(HOST, PORT)
    request = (
        "GET /api/v1/watch/coordination HTTP/1.1\r\n"
        f"Host: {HOST}:{PORT}\r\n"
        "Accept: text/event-stream\r\n"
        "Connection: keep-alive\r\n\r\n"
    )
    writer.write(request.encode())
    await writer.drain()

    headers = b""
    while b"\r\n\r\n" not in headers:
        chunk = await reader.read(1024)
        if not chunk:
            raise RuntimeError(f"{name} did not receive SSE headers")
        headers += chunk
    ready.set()
    log(name, "watch established; waiting for coordinator update")

    buffer = headers.split(b"\r\n\r\n", 1)[1].decode()
    try:
        while not finished.is_set():
            if "\n\n" not in buffer:
                chunk = await reader.read(1024)
                if not chunk:
                    break
                buffer += chunk.decode()
                continue

            event, buffer = buffer.split("\n\n", 1)
            for line in event.splitlines():
                if not line.startswith("data: "):
                    continue
                payload = json.loads(line[6:])
                log(name, f"received SSE event for {payload['namespace']}/{payload['key']} v{payload['version']}")
                assignment = await asyncio.to_thread(
                    http_request,
                    "GET",
                    f"/api/v1/configs/coordination/task",
                )
                worker_count = await asyncio.to_thread(
                    http_request,
                    "GET",
                    f"/api/v1/configs/coordination/worker_count",
                )
                log(
                    name,
                    "read assignment "
                    f"task={assignment['value']} worker_count={worker_count['value']}",
                )
                finished.set()
                return
    finally:
        writer.close()
        await writer.wait_closed()
        log(name, "watch stream closed")


async def coordinator(workers_ready: list[asyncio.Event], workers_done: asyncio.Event) -> None:
    for ready in workers_ready:
        await ready.wait()

    log("coordinator", "creating feature flag enable_parallel_processing")
    try:
        await asyncio.to_thread(
            http_request,
            "POST",
            "/api/v1/flags",
            {
                "name": "enable_parallel_processing",
                "enabled": True,
                "rollout_pct": 100,
                "rules": {"strategy": "parallel"},
            },
        )
    except RuntimeError as exc:
        if "409" not in str(exc):
            raise
        log("coordinator", "feature flag already exists; reusing it")

    evaluation = await asyncio.to_thread(
        http_request,
        "POST",
        "/api/v1/flags/enable_parallel_processing/evaluate",
        {"agent_id": "coordinator", "context": {"role": "coordinator"}},
    )
    log(
        "coordinator",
        f"feature flag enable_parallel_processing => {evaluation['enabled']} ({evaluation['reason']})",
    )

    log("coordinator", "writing coordination config keys")
    await asyncio.to_thread(
        http_request,
        "POST",
        "/api/v1/configs",
        {"namespace": "coordination", "key": "task", "value": "distribute_work"},
    )
    await asyncio.to_thread(
        http_request,
        "POST",
        "/api/v1/configs",
        {"namespace": "coordination", "key": "worker_count", "value": 3},
    )
    log("coordinator", "published task=distribute_work and worker_count=3")

    await asyncio.wait_for(workers_done.wait(), timeout=10)
    log("coordinator", "workers acknowledged assignment; demo complete")


async def main() -> int:
    service_process = await start_service()
    log_task = asyncio.create_task(stream_service_logs(service_process))
    ready_events = [asyncio.Event(), asyncio.Event()]
    finished = asyncio.Event()
    worker_tasks = [
        asyncio.create_task(worker_agent("worker-1", ready_events[0], finished)),
        asyncio.create_task(worker_agent("worker-2", ready_events[1], finished)),
    ]

    try:
        await coordinator(ready_events, finished)
        await asyncio.gather(*worker_tasks)
        return 0
    finally:
        for task in worker_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*worker_tasks, return_exceptions=True)
        log_task.cancel()
        await asyncio.gather(log_task, return_exceptions=True)
        await stop_service(service_process)
        database_path = REPO_ROOT / "demo_coordination.db"
        if database_path.exists():
            database_path.unlink()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
