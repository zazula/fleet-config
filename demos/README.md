# Multi-Agent Coordination Demo

This demo launches a local `fleet-config` service on port `8002` and simulates a small swarm:

- one coordinator agent
- two worker agents subscribed to the SSE watch stream
- one feature flag decision used to choose parallel routing

## Run

```bash
python demos/multi_agent_demo.py
```

## What it does

1. Starts `fleet-config` with `uvicorn` on `http://127.0.0.1:8002`
2. Opens two SSE watchers on the `coordination` namespace
3. Creates and evaluates the `enable_parallel_processing` feature flag
4. Writes config keys:
   - `coordination/task = distribute_work`
   - `coordination/worker_count = 3`
5. Worker agents observe the config update and read back the assignment
6. Shuts down the service and cleans up the demo database

## Expected output

You should see a flow similar to:

```text
[system] fleet-config service started on http://127.0.0.1:8002
[worker-1] subscribing to namespace watch stream
[worker-2] subscribing to namespace watch stream
[coordinator] creating feature flag enable_parallel_processing
[coordinator] feature flag enable_parallel_processing => True (full rollout)
[coordinator] published task=distribute_work and worker_count=3
[worker-1] received SSE event for coordination/task v1
[worker-1] read assignment task=distribute_work worker_count=3
[worker-2] received SSE event for coordination/task v1
[worker-2] read assignment task=distribute_work worker_count=3
[coordinator] workers acknowledged assignment; demo complete
[system] fleet-config service stopped
```

The exact ordering of worker messages can vary slightly because both watchers run concurrently.
