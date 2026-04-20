# fleet-config

**Centralized configuration and feature-flag service for the agent fleet**

[![CI](https://github.com/your-org/fleet-config/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/fleet-config/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)

---

## Problem

As the agent fleet grows, configuration ends up scattered everywhere — environment variables baked into container images, YAML files copied between services, hardcoded constants deep in source, and ad-hoc feature toggles with no audit trail. There is no single source of truth, no way to roll out changes progressively, and no mechanism for agents to react to config updates without restarting.

**fleet-config** solves this by providing a centralized, versioned configuration and feature-flag service with:

- **A single source of truth** for all config and flags, backed by a durable store and full version history.
- **Rollout-aware feature flags** — percentage rollouts, rule-based matching, and gradual exposure.
- **A watch API** — agents subscribe to namespaces and receive real-time updates via SSE, eliminating restarts.

---

## Key Features

| Capability | Description |
|---|---|
| **Versioned config CRUD** | Create, read, update, and delete config keys with full version history and instant rollback. |
| **Feature flags** | Boolean, percentage-rollout, and rule-matched flags. Target by agent ID, group, environment, or arbitrary attributes. |
| **SSE watch / streaming** | Subscribe to a namespace and receive push updates in real time over Server-Sent Events. |
| **API-key auth** | Every request is authenticated via API keys scoped to read, write, or admin permissions. |
| **Audit log** | Immutable log of every change — who changed what, when, and the before/after diff. |
| **Python SDK** | First-class `fleetconfig` package with sync and async clients, type-safe config bindings, and automatic reconnection on watch streams. |

---

## Quickstart

### 1. Start the service

```bash
docker compose up -d
```

This starts the **fleet-config** API server on `http://localhost:8080` and a backing Postgres instance.

### 2. Create an API key

```bash
curl -s -X POST http://localhost:8080/v1/keys \
  -H "Content-Type: application/json" \
  -d '{
    "name": "admin-key",
    "role": "admin"
  }' | jq .
```

```json
{
  "id": "key_01HXYZ",
  "name": "admin-key",
  "role": "admin",
  "secret": "fc_admin_abc123...",
  "created_at": "2025-01-15T00:00:00Z"
}
```

> **Save the `secret`** — it is shown only once.

### 3. Set a config value

```bash
curl -s -X PUT http://localhost:8080/v1/config/agents/retry_count \
  -H "Authorization: Bearer fc_admin_abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "value": 5,
    "type": "int",
    "description": "Max retry attempts for agent tasks"
  }' | jq .
```

```json
{
  "key": "agents/retry_count",
  "value": 5,
  "type": "int",
  "version": 1,
  "updated_at": "2025-01-15T00:01:00Z"
}
```

### 4. Read it back

```bash
curl -s http://localhost:8080/v1/config/agents/retry_count \
  -H "Authorization: Bearer fc_admin_abc123..." | jq .
```

### 5. Create a feature flag with rollout

```bash
curl -s -X POST http://localhost:8080/v1/flags/use_memory_cache \
  -H "Authorization: Bearer fc_admin_abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "rollout_percent": 25,
    "rules": [
      { "attribute": "env", "operator": "eq", "value": "staging" }
    ],
    "description": "Enable in-memory caching layer for eligible agents"
  }' | jq .
```

```json
{
  "key": "use_memory_cache",
  "enabled": true,
  "rollout_percent": 25,
  "rules": [
    { "attribute": "env", "operator": "eq", "value": "staging" }
  ],
  "version": 1,
  "created_at": "2025-01-15T00:02:00Z"
}
```

### 6. Check a flag for a specific agent

```bash
curl -s "http://localhost:8080/v1/flags/use_memory_cache/evaluate" \
  -H "Authorization: Bearer fc_admin_abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent-42",
    "attributes": { "env": "staging", "group": "data-pipeline" }
  }' | jq .
```

```json
{
  "flag": "use_memory_cache",
  "result": true,
  "reason": "matched_rule"
}
```

### 7. Watch a namespace (SSE stream)

```bash
curl -N http://localhost:8080/v1/watch/agents \
  -H "Authorization: Bearer fc_admin_abc123..."
```

```
event: config_update
data: {"key":"agents/retry_count","value":10,"version":2,"updated_at":"2025-01-15T00:05:00Z"}

event: flag_update
data: {"key":"use_memory_cache","rollout_percent":50,"version":2,"updated_at":"2025-01-15T00:06:00Z"}
```

Press `Ctrl+C` to stop the stream.

---

## Architecture

For the full system design, data model, and deployment topology, see [**docs/ARCHITECTURE.md**](docs/ARCHITECTURE.md).

---

## API Reference

Complete endpoint documentation with request/response schemas is in [**docs/API.md**](docs/API.md).

---

## SDK

The Python SDK (`fleetconfig`) provides sync and async clients, typed config access, and a watch helper with automatic reconnection.

Installation:

```bash
pip install fleetconfig
```

Full usage guide: [**docs/SDK.md**](docs/SDK.md).

---

## Contributing

PRs are welcome. To contribute:

1. **Fork** the repo and create a feature branch.
2. **Lint and test** — CI enforces both. Run locally:
   ```bash
   make lint test
   ```
3. **Conventional commits** — use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `chore:`, etc.).
4. **Open a PR** against `main` with a clear description of the change and motivation.

---

## License

This project is licensed under the [MIT License](LICENSE).
