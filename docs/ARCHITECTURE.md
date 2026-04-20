# fleet-config — Architecture Document

> **Version:** 1.0.0-draft
> **Last updated:** 2025-07-11
> **Status:** Design

---

## Table of Contents

1. [Overview](#1-overview)
2. [Component Diagram](#2-component-diagram)
3. [Tech Stack](#3-tech-stack)
4. [Data Model](#4-data-model)
5. [API Design Principles](#5-api-design-principles)
6. [Auth Model](#6-auth-model)
7. [Feature Flag Evaluation](#7-feature-flag-evaluation)
8. [Watch / SSE Design](#8-watch--sse-design)
9. [Deployment Topology](#9-deployment-topology)
10. [Directory Structure](#10-directory-structure)

---

## 1. Overview

**fleet-config** is a centralized configuration-management and feature-flag service designed for small-to-medium deployments that value operational simplicity over horizontal scale. It exposes a versioned key-value store for dynamic configuration alongside a full-featured feature-flag engine (percentage rollouts, attribute rules, allowlists). All mutations are audited, every read can be authorized by scoped API keys, and consumers can watch for changes in real time via Server-Sent Events (SSE). The system ships as a single stateless-fast container backed by SQLite (swappable to Postgres) so that teams can get going with zero infrastructure yet migrate to a managed database when they outgrow the single-node model.

---

## 2. Component Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              Docker Container                            │
│                                                                          │
│  ┌─────────────┐      ┌──────────────────────────────────────────────┐  │
│  │ Client SDK   │      │               FastAPI Application            │  │
│  │  (httpx)     │─────▶│                                              │  │
│  └─────────────┘      │  ┌────────────────┐   ┌───────────────────┐  │  │
│                        │  │ Auth Middleware │──▶│  Router Layer     │  │  │
│  ┌─────────────┐      │  └────────────────┘   └────────┬──────────┘  │  │
│  │ curl / HTTP │─────▶│                                 │             │  │
│  │  client     │      │                          ┌──────▼──────┐      │  │
│  └─────────────┘      │                          │ Service     │      │  │
│                        │                          │ Layer       │      │  │
│                        │                          └──┬────┬─────┘      │  │
│                        │                   ┌─────────┘    │            │  │
│                        │          ┌───────▼──────┐  ┌─────▼─────────┐  │  │
│                        │          │ Repository   │  │ SSE Watch     │  │  │
│                        │          │ Layer        │  │ Manager       │  │  │
│                        │          └───────┬──────┘  └───────────────┘  │  │
│                        │                  │                            │  │
│                        │          ┌───────▼──────┐                     │  │
│                        │          │  Database    │                     │  │
│                        │          │  (SQLAlchemy │                     │  │
│                        │          │   async)     │                     │  │
│                        │          └───────┬──────┘                     │  │
│                        └──────────────────┼───────────────────────────┘  │
│                                            │                              │
│                                   ┌────────▼────────┐                    │
│                                   │  SQLite File     │  ◄── mounted      │
│                                   │  (aiosqlite)     │      volume       │
│                                   └─────────────────┘                    │
│                                                                          │
│                        Port 8080 ◀──▶ uvicorn ASGI                      │
└──────────────────────────────────────────────────────────────────────────┘

Legend:
  ───▶  synchronous HTTP / internal call
  ─ ─ ▶  event publish (asyncio.Queue)
```

### Flow Summary

| # | Step |
|---|------|
| 1 | Client (SDK or raw HTTP) sends a request to `http://<host>:8080/api/v1/...`. |
| 2 | **Auth Middleware** extracts the `Authorization: Bearer <key>` header, hashes the token, looks up the API key, checks scopes, and attaches an identity object to `request.state`. Unauthenticated routes (health, ready) are exempted. |
| 3 | **Router Layer** validates the request path/method, delegates path/body parsing to Pydantic models, and calls into the Service Layer. |
| 4 | **Service Layer** enforces business rules (e.g., version bumping, audit logging, flag evaluation), then calls the Repository Layer for persistence and publishes change events to the SSE Watch Manager. |
| 5 | **Repository Layer** translates service-level calls into SQLAlchemy async queries. |
| 6 | **Database** engine executes against SQLite via aiosqlite (or psycopg async against Postgres). |
| 7 | **SSE Watch Manager** receives change events and fans them out to connected SSE subscribers via per-subscriber `asyncio.Queue` instances. |

---

## 3. Tech Stack

| Component | Library / Tool | Version | Rationale |
|-----------|---------------|---------|-----------|
| **Web Framework** | [FastAPI](https://fastapi.tiangolo.com/) | ≥ 0.111 | Native `async`/`await` support eliminates thread-per-request overhead. Automatic OpenAPI 3.1 docs (`/docs`, `/redoc`) give every consumer an interactive API reference with zero extra code. Request bodies and responses are validated through Pydantic integration, catching malformed input before it reaches business logic. Dependency-injection system cleanly wires auth, DB sessions, and services. |
| **ORM / Query Builder** | [SQLAlchemy](https://www.sqlalchemy.org/) 2.0 async | ≥ 2.0.30 | The async session API (`create_async_engine`, `AsyncSession`) provides a first-class coroutine interface while abstracting the underlying dialect. Swapping SQLite for Postgres is a single connection-string change — no query rewrites. The new 2.0-style `select()` / `insert()` DSL is type-safe and IDE-friendly. |
| **SQLite Async Driver** | [aiosqlite](https://github.com/omnilib/aiosqlite) | ≥ 0.20 | Wraps the stdlib `sqlite3` module in a background thread and exposes an `async` interface compatible with SQLAlchemy's `AsyncEngine`. Zero external dependencies. Perfect for single-node and development scenarios. |
| **Data Validation** | [Pydantic](https://docs.pydantic.dev/) v2 | ≥ 2.7 | Powers FastAPI's request/response serialization. Benchmarks show ~5-50× faster parsing than v1 via the Rust core. Settings management via `pydantic-settings` reads from env vars / `.env` files out of the box. |
| **ASGI Server** | [uvicorn](https://www.uvicorn.org/) | ≥ 0.30 | Production-grade ASGI server built on `uvloop` (fast event loop) and `httptools` (fast HTTP parser). Supports graceful shutdown, pipelining, and `--reload` for development. |
| **HTTP Client (SDK)** | [httpx](https://www.python-httpx.org/) | ≥ 0.27 | Synchronous client for the consumer SDK (no async dependency leaked to the consumer). Supports connection pooling, retries, and timeout configuration. The same API surface is available in async mode for future SDK evolution. |
| **Testing** | pytest + pytest-asyncio + httpx `AsyncClient` | latest | In-process `TestClient` backed by `httpx.AsyncClient` runs against the real FastAPI app without network hops. `pytest-asyncio` provides native `async def test_*` support. An in-memory SQLite database is created per-test for full isolation. |

### Non-library infrastructure

| Concern | Choice | Notes |
|---------|--------|-------|
| Container base image | `python:3.12-slim-bookworm` | Small attack surface, includes pip. |
| Dependency management | `uv` (via `pyproject.toml`) | Fast lockfile generation, `pip`-compatible. |
| Linting / formatting | `ruff` | Replaces flake8 + isort + black in one tool. |

---

## 4. Data Model

### 4.1 ERD Overview

```
┌────────────────┐       ┌────────────────────┐
│  config_values │──1:N──│  config_versions   │
└───────┬────────┘       └────────────────────┘
        │
        │  (logical grouping by namespace)
        │
┌───────┴────────┐       ┌────────────────────┐       ┌────────────┐
│ feature_flags  │       │     api_keys       │       │ audit_log  │
└────────────────┘       └────────────────────┘       └────────────┘
```

### 4.2 Table Definitions

#### `config_values`

Stores the live (current) value of every configuration key. Each row points to its current version in `config_versions`. Historical versions are retained for audit and rollback.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `INTEGER` | **PK**, autoincrement | Internal row ID. |
| `namespace` | `TEXT` | `NOT NULL` | Dot-separated grouping, e.g. `"payments.stripe"`. |
| `key` | `TEXT` | `NOT NULL` | Leaf key name within the namespace, e.g. `"webhook_url"`. |
| `value_json` | `TEXT` | `NOT NULL` | JSON-encoded current value. Stored as TEXT for SQLite compatibility; JSON on Postgres. |
| `value_type` | `TEXT` | `NOT NULL` | One of: `"string"`, `"integer"`, `"float"`, `"boolean"`, `"json"`. Drives deserialization hints. |
| `current_version_id` | `INTEGER` | `FK → config_versions.id`, `NULL` initially | Points to the latest approved version. `NULL` means the key exists but has never been set. |
| `created_at` | `TEXT` | `NOT NULL`, default `CURRENT_TIMESTAMP` | ISO-8601 UTC timestamp. |
| `updated_at` | `TEXT` | `NOT NULL`, default `CURRENT_TIMESTAMP` | ISO-8601 UTC timestamp. Updated on every write. |

**Indexes:**

```sql
UNIQUE (namespace, key)                    -- natural key, fast lookup
CREATE INDEX ix_config_values_namespace ON config_values (namespace);
```

---

#### `config_versions`

Immutable append-only log of every value a configuration key has ever held.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `INTEGER` | **PK**, autoincrement | Internal row ID. |
| `config_value_id` | `INTEGER` | `FK → config_values.id ON DELETE CASCADE`, `NOT NULL` | Parent config key. |
| `version_number` | `INTEGER` | `NOT NULL` | Monotonically increasing per `config_value_id`, starting at 1. |
| `value_json` | `TEXT` | `NOT NULL` | Snapshot of `config_values.value_json` at this version. |
| `actor` | `TEXT` | `NOT NULL` | API key name or identity that created this version. |
| `created_at` | `TEXT` | `NOT NULL`, default `CURRENT_TIMESTAMP` | ISO-8601 UTC timestamp. |

**Indexes:**

```sql
UNIQUE (config_value_id, version_number)
CREATE INDEX ix_config_versions_config_value_id ON config_versions (config_value_id);
```

---

#### `feature_flags`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `INTEGER` | **PK**, autoincrement | Internal row ID. |
| `name` | `TEXT` | `UNIQUE`, `NOT NULL` | Human-readable flag name, e.g. `"dark-mode"`. |
| `description` | `TEXT` | default `""` | Free-form explanation of the flag's purpose. |
| `enabled` | `BOOLEAN` | `NOT NULL`, default `FALSE` | Global kill switch. If `FALSE`, evaluation always returns `FALSE` regardless of rules. |
| `rollout_percentage` | `INTEGER` | `NOT NULL`, default `0`, check `0..100` | Percentage of eligible users who should see the flag as `TRUE`. Evaluated via deterministic hash (see §7). |
| `rules_json` | `TEXT` | `NOT NULL`, default `"[]"` | JSON array of rule objects (see §7.3). |
| `created_at` | `TEXT` | `NOT NULL`, default `CURRENT_TIMESTAMP` | ISO-8601 UTC. |
| `updated_at` | `TEXT` | `NOT NULL`, default `CURRENT_TIMESTAMP` | ISO-8601 UTC. |

**Indexes:**

```sql
UNIQUE (name)
```

**`rules_json` schema (each element in the array):**

```json
{
  "attribute": "country",
  "operator": "in",
  "values": ["US", "CA"]
}
```

Supported operators: `eq`, `neq`, `in`, `not_in`, `contains`, `gt`, `gte`, `lt`, `lte`, `regex`.

---

#### `api_keys`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `INTEGER` | **PK**, autoincrement | Internal row ID. |
| `name` | `TEXT` | `UNIQUE`, `NOT NULL` | Human-readable label, e.g. `"backend-prod"`. |
| `key_hash` | `TEXT` | `UNIQUE`, `NOT NULL` | SHA-256 hex digest of the raw key. The raw key is never stored. |
| `key_prefix` | `TEXT` | `NOT NULL` | First 8 characters of the raw key, used for visual identification in logs and UI without exposing the full key. |
| `scopes_json` | `TEXT` | `NOT NULL` | JSON array of scope strings (see §6). |
| `created_at` | `TEXT` | `NOT NULL`, default `CURRENT_TIMESTAMP` | ISO-8601 UTC. |
| `revoked_at` | `TEXT` | `NULL` | ISO-8601 UTC. Non-null means the key is revoked. |

**Indexes:**

```sql
CREATE INDEX ix_api_keys_key_hash ON api_keys (key_hash);
CREATE INDEX ix_api_keys_key_prefix ON api_keys (key_prefix);
```

---

#### `audit_log`

Immutable, append-only log of every mutating operation performed against the system.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `INTEGER` | **PK**, autoincrement | Internal row ID. |
| `actor` | `TEXT` | `NOT NULL` | API key name that performed the action. |
| `action` | `TEXT` | `NOT NULL` | Verb: `"create"`, `"update"`, `"delete"`, `"revoke"`. |
| `resource_type` | `TEXT` | `NOT NULL` | One of: `"config_value"`, `"feature_flag"`, `"api_key"`. |
| `resource_id` | `INTEGER` | `NOT NULL` | Primary key of the affected row in the resource table. |
| `detail_json` | `TEXT` | `NOT NULL`, default `"{}"` | Arbitrary JSON payload capturing before/after snapshots, diff, or contextual metadata. |
| `created_at` | `TEXT` | `NOT NULL`, default `CURRENT_TIMESTAMP` | ISO-8601 UTC. |

**Indexes:**

```sql
CREATE INDEX ix_audit_log_resource ON audit_log (resource_type, resource_id);
CREATE INDEX ix_audit_log_actor ON audit_log (actor);
CREATE INDEX ix_audit_log_created_at ON audit_log (created_at);
```

### 4.3 SQLAlchemy Model Sketch

```python
# src/fleet_config/models/config_value.py
from sqlalchemy import Column, Integer, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship, Mapped
from sqlalchemy.sql import func
from ..database import Base


class ConfigValue(Base):
    __tablename__ = "config_values"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    namespace: Mapped[str] = Column(Text, nullable=False)
    key: Mapped[str] = Column(Text, nullable=False)
    value_json: Mapped[str] = Column(Text, nullable=False)
    value_type: Mapped[str] = Column(Text, nullable=False)
    current_version_id: Mapped[int | None] = Column(
        Integer, ForeignKey("config_versions.id", use_alter=True), nullable=True
    )
    created_at: Mapped[str] = Column(Text, nullable=False, server_default=func.strftime("%Y-%m-%dT%H:%M:%SZ", "now"))
    updated_at: Mapped[str] = Column(Text, nullable=False, server_default=func.strftime("%Y-%m-%dT%H:%M:%SZ", "now"), onupdate=func.strftime("%Y-%m-%dT%H:%M:%SZ", "now"))

    versions: Mapped[list["ConfigVersion"]] = relationship(back_populates="config_value", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("namespace", "key", name="uq_config_values_namespace_key"),
        Index("ix_config_values_namespace", "namespace"),
    )


class ConfigVersion(Base):
    __tablename__ = "config_versions"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    config_value_id: Mapped[int] = Column(Integer, ForeignKey("config_values.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = Column(Integer, nullable=False)
    value_json: Mapped[str] = Column(Text, nullable=False)
    actor: Mapped[str] = Column(Text, nullable=False)
    created_at: Mapped[str] = Column(Text, nullable=False, server_default=func.strftime("%Y-%m-%dT%H:%M:%SZ", "now"))

    config_value: Mapped["ConfigValue"] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("config_value_id", "version_number", name="uq_config_versions_id_number"),
        Index("ix_config_versions_config_value_id", "config_value_id"),
    )
```

> The remaining models (`FeatureFlag`, `ApiKey`, `AuditLog`) follow the same pattern and live under `src/fleet_config/models/`.

---

## 5. API Design Principles

### 5.1 RESTful Conventions

| Convention | Implementation |
|-----------|----------------|
| **Resource URLs** | Plural nouns: `/api/v1/configs`, `/api/v1/flags`, `/api/v1/api-keys`, `/api/v1/audit-log`. |
| **HTTP methods** | `GET` (read), `POST` (create), `PUT` (full replace), `PATCH` (partial update), `DELETE` (delete). |
| **Idempotency** | `PUT` is fully idempotent. `DELETE` is idempotent (404 on re-delete). `POST` is not idempotent by design (creates a new version). |
| **Content type** | All request/response bodies are `application/json`. |
| **API versioning** | URL-prefix: `/api/v1`. Breaking changes bump the prefix; additive changes are non-breaking within the same prefix. |

### 5.2 Error Shape

Every error response uses a single consistent JSON envelope:

```json
{
  "error": {
    "code": "CONFIG_NOT_FOUND",
    "message": "No config value exists for namespace 'payments' and key 'webhook_url'.",
    "details": {
      "namespace": "payments",
      "key": "webhook_url"
    }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `error.code` | `string` | Machine-readable, UPPER_SNAKE_CASE error identifier that clients can switch on. |
| `error.message` | `string` | Human-readable description of what went wrong. Safe to log and display. |
| `error.details` | `object | null` | Optional structured metadata (field names, IDs, validation errors). |

### 5.3 HTTP Status Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| `200` | OK | Successful read or update. |
| `201` | Created | Successful resource creation (POST). |
| `204` | No Content | Successful deletion. |
| `400` | Bad Request | Malformed JSON, validation failure. |
| `401` | Unauthorized | Missing or invalid `Authorization` header. |
| `403` | Forbidden | Valid key but insufficient scope. |
| `404` | Not Found | Resource does not exist. |
| `409` | Conflict | Duplicate resource (e.g., config key already exists). |
| `422` | Unprocessable Entity | Semantically invalid payload (Pydantic validation). |
| `429` | Too Many Requests | Rate limit exceeded (future). |
| `500` | Internal Server Error | Unhandled exception. |

### 5.4 Pagination

All list endpoints support cursor-based pagination:

**Request parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | `string` | `null` | Opaque cursor returned by the previous page. |
| `limit` | `integer` | `50` | Page size. Max `500`. |

**Response shape:**

```json
{
  "data": [ ... ],
  "pagination": {
    "has_more": true,
    "next_cursor": "eyJpZCI6MTAwfQ=="
  }
}
```

- The cursor is a Base64-encoded JSON object containing the last seen `id` (or compound key).
- When `has_more` is `false`, `next_cursor` is `null`.
- An empty page returns `{"data": [], "pagination": {"has_more": false, "next_cursor": null}}`.

### 5.5 API Endpoint Summary

#### Configs

| Method | Path | Description | Required Scope |
|--------|------|-------------|----------------|
| `GET` | `/api/v1/configs` | List config values (filter by `namespace`). | `config:read` |
| `GET` | `/api/v1/configs/{namespace}/{key}` | Get a single config value. | `config:read` |
| `POST` | `/api/v1/configs` | Create a new config value. | `config:write` |
| `PUT` | `/api/v1/configs/{namespace}/{key}` | Update a config value (creates new version). | `config:write` |
| `DELETE` | `/api/v1/configs/{namespace}/{key}` | Delete a config value and all versions. | `config:write` |
| `GET` | `/api/v1/configs/{namespace}/{key}/versions` | List version history for a key. | `config:read` |
| `GET` | `/api/v1/configs/{namespace}/{key}/versions/{version}` | Get a specific version. | `config:read` |
| `POST` | `/api/v1/configs/{namespace}/{key}/rollback` | Roll back to a prior version. | `config:write` |

#### Feature Flags

| Method | Path | Description | Required Scope |
|--------|------|-------------|----------------|
| `GET` | `/api/v1/flags` | List all flags. | `flags:read` |
| `GET` | `/api/v1/flags/{name}` | Get a single flag. | `flags:read` |
| `POST` | `/api/v1/flags` | Create a new flag. | `flags:write` |
| `PUT` | `/api/v1/flags/{name}` | Replace a flag. | `flags:write` |
| `PATCH` | `/api/v1/flags/{name}` | Partially update a flag. | `flags:write` |
| `DELETE` | `/api/v1/flags/{name}` | Delete a flag. | `flags:write` |
| `POST` | `/api/v1/flags/{name}/evaluate` | Evaluate a flag for a given context. | `flags:read` |

#### API Keys

| Method | Path | Description | Required Scope |
|--------|------|-------------|----------------|
| `GET` | `/api/v1/api-keys` | List keys (omit hash). | `admin` |
| `POST` | `/api/v1/api-keys` | Create a key. Returns raw key **once**. | `admin` |
| `DELETE` | `/api/v1/api-keys/{name}` | Revoke a key. | `admin` |

#### Audit Log

| Method | Path | Description | Required Scope |
|--------|------|-------------|----------------|
| `GET` | `/api/v1/audit-log` | List entries (filterable by `resource_type`, `actor`). | `admin` |

#### Watch / SSE

| Method | Path | Description | Required Scope |
|--------|------|-------------|----------------|
| `GET` | `/api/v1/watch` | Open SSE stream for config/flag change events. | `config:read` or `flags:read` |

#### System

| Method | Path | Description | Required Scope |
|--------|------|-------------|----------------|
| `GET` | `/healthz` | Liveness check. | None |
| `GET` | `/readyz` | Readiness check (verifies DB connectivity). | None |

---

## 6. Auth Model

### 6.1 Authentication Flow

```
Request ──▶ Auth Middleware
               │
               ├─ No Authorization header ──▶ 401 Missing credentials
               │
               ├─ Header: "Bearer <token>"
               │       │
               │       ├─ SHA-256(token) ──▶ Lookup in api_keys WHERE key_hash = ? AND revoked_at IS NULL
               │       │                        │
               │       │                        ├─ Not found ──▶ 401 Invalid API key
               │       │                        │
               │       │                        └─ Found ──▶ Parse scopes_json ──▶ Attach to request.state
               │       │
               │       └─ Wrong scheme ──▶ 401 Unsupported auth scheme
               │
               └─ Route handler checks request.state.scopes against required scope
                        │
                        ├─ Scope present ──▶ continue
                        └─ Scope absent ──▶ 403 Insufficient scope
```

### 6.2 Key Generation

When creating an API key via `POST /api/v1/api-keys`:

1. Generate a cryptographically random 32-byte key.
2. Base64url-encode it (no padding): `fc_` prefix + 43 chars = **`fc_<43 chars>`** (total 46 chars).
   Example: `fc_a8Kj3mN9pQ2rS5tU8vW1xY4zA7bC0dFgHiJkLmNoPqR`
3. Store:
   - `key_hash` = `sha256(raw_key_bytes).hexdigest()` (64-char hex string).
   - `key_prefix` = first 8 characters of the raw key (e.g., `fc_a8Kj3`).
   - `scopes_json` = JSON array of granted scope strings.
4. Return the raw key in the response body **once**. The raw key is never stored and cannot be recovered.

### 6.3 Scopes

| Scope | Permits |
|-------|---------|
| `config:read` | Read config values and versions. |
| `config:write` | Create, update, delete config values. |
| `flags:read` | Read and evaluate feature flags. |
| `flags:write` | Create, update, delete feature flags. |
| `admin` | Full access: manage API keys, read audit log. Implies all other scopes. |

**Scope checking algorithm:**

```python
def has_scope(granted: list[str], required: str) -> bool:
    return "admin" in granted or required in granted
```

### 6.4 Middleware Implementation Sketch

```python
# src/fleet_config/middleware/auth.py
import hashlib
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from ..repositories.api_key import ApiKeyRepository

EXEMPT_PATHS = {"/healthz", "/readyz", "/docs", "/redoc", "/openapi.json"}


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, session_factory):
        super().__init__(app)
        self.session_factory = session_factory

    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(status_code=401, content=ERROR_MISSING_HEADER)

        parts = auth_header.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return JSONResponse(status_code=401, content=ERROR_BAD_SCHEME)

        raw_key = parts[1]
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

        async with self.session_factory() as session:
            repo = ApiKeyRepository(session)
            api_key = await repo.find_by_hash(key_hash)

        if api_key is None or api_key.revoked_at is not None:
            return JSONResponse(status_code=401, content=ERROR_INVALID_KEY)

        request.state.actor = api_key.name
        request.state.scopes = json.loads(api_key.scopes_json)

        return await call_next(request)
```

---

## 7. Feature Flag Evaluation

### 7.1 Evaluate Endpoint

`POST /api/v1/flags/{name}/evaluate`

**Request body:**

```json
{
  "user_id": "user-12345",
  "attributes": {
    "country": "US",
    "plan": "pro",
    "age": 29,
    "email": "alice@example.com"
  }
}
```

**Response:**

```json
{
  "flag": "dark-mode",
  "enabled": true,
  "reason": "rollout_percentage"
}
```

| `reason` value | Meaning |
|----------------|---------|
| `"disabled"` | Flag's `enabled` field is `false`. |
| `"allowlist"` | `user_id` appeared in the flag's allowlist. |
| `"rollout_percentage"` | Hash bucket fell within rollout. |
| `"rule_match"` | An attribute rule matched. |
| `"no_match"` | No condition matched; default `false`. |

### 7.2 Evaluation Algorithm (Pseudocode)

```python
def evaluate_flag(flag: FeatureFlag, user_id: str, attributes: dict) -> tuple[bool, str]:
    # Step 1: Global kill switch
    if not flag.enabled:
        return False, "disabled"

    # Step 2: Allowlist check
    # allowlist is extracted from rules_json where operator == "allowlist"
    allowlist = extract_allowlist(flag.rules_json)
    if user_id in allowlist:
        return True, "allowlist"

    # Step 3: Deterministic percentage rollout
    bucket = deterministic_bucket(user_id, flag.name)
    if bucket < flag.rollout_percentage:
        return True, "rollout_percentage"

    # Step 4: Attribute rules (excluding allowlist rules)
    for rule in extract_attribute_rules(flag.rules_json):
        if evaluate_rule(rule, attributes):
            return True, "rule_match"

    # Step 5: Default
    return False, "no_match"


def deterministic_bucket(user_id: str, flag_name: str) -> int:
    """Return an integer in [0, 99] derived from a stable hash."""
    raw = f"{user_id}:{flag_name}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return int(digest[:8], 16) % 100


def evaluate_rule(rule: dict, attributes: dict) -> bool:
    attr_name = rule["attribute"]
    if attr_name not in attributes:
        return False
    actual = attributes[attr_name]
    op = rule["operator"]
    expected = rule["values"] if "values" in rule else rule.get("value")

    match op:
        case "eq":
            return actual == expected
        case "neq":
            return actual != expected
        case "in":
            return actual in expected
        case "not_in":
            return actual not in expected
        case "contains":
            return expected in str(actual)
        case "gt":
            return float(actual) > float(expected)
        case "gte":
            return float(actual) >= float(expected)
        case "lt":
            return float(actual) < float(expected)
        case "lte":
            return float(actual) <= float(expected)
        case "regex":
            return bool(re.search(expected, str(actual)))
        case _:
            return False
```

### 7.3 Rules JSON Schema

Each flag's `rules_json` is an array of rule objects. There are two categories:

**Allowlist rule** (evaluated at Step 2):

```json
{
  "type": "allowlist",
  "user_ids": ["user-123", "user-456"]
}
```

**Attribute rules** (evaluated at Step 4):

```json
{
  "type": "attribute",
  "attribute": "country",
  "operator": "in",
  "values": ["US", "CA", "GB"]
}
```

Full example `rules_json`:

```json
[
  {
    "type": "allowlist",
    "user_ids": ["admin-1", "admin-2"]
  },
  {
    "type": "attribute",
    "attribute": "plan",
    "operator": "eq",
    "values": "pro"
  },
  {
    "type": "attribute",
    "attribute": "age",
    "operator": "gte",
    "values": 18
  }
]
```

---

## 8. Watch / SSE Design

### 8.1 Architecture

```
┌───────────────┐      change event      ┌──────────────────┐
│ Service Layer │───────────────────────▶│  SSE WatchManager │
└───────────────┘                        │                   │
                                          │  ┌─────────────┐ │
                                          │  │ subscribers  │ │
                                          │  │  [Queue, …]  │ │
                                          │  └─────────────┘ │
                                          └────────┬─────────┘
                                                   │
                                          ┌────────▼─────────┐
                                          │  SSE Endpoint     │
                                          │  GET /api/v1/watch│
                                          └──────────────────┘
```

### 8.2 Event Bus Internals

The `WatchManager` is a process-level singleton:

```python
# src/fleet_config/watch/manager.py
import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class WatchEvent:
    event_id: str          # e.g. "config:payments.webhook_url:42"
    event_type: str        # "config.changed" | "flag.changed"
    data: dict
    timestamp: str


class WatchManager:
    def __init__(self):
        self._subscribers: list[asyncio.Queue[WatchEvent | None]] = []
        self._last_event_id: int = 0

    def subscribe(self, last_event_id: str | None) -> asyncio.Queue[WatchEvent | None]:
        """Create a new subscriber queue. Replay missed events if last_event_id given."""
        q: asyncio.Queue[WatchEvent | None] = asyncio.Queue(maxsize=256)
        self._subscribers.append(q)
        # Replay logic: if last_event_id is provided, the manager can
        # query the database for events newer than that ID.
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.remove(q)

    async def publish(self, event: WatchEvent) -> None:
        self._last_event_id += 1
        event.event_id = str(self._last_event_id)
        dead = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.remove(q)

    async def stream(self, q: asyncio.Queue) -> AsyncIterator[str]:
        """Yield SSE-formatted lines from the subscriber queue."""
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Heartbeat
                    yield ": heartbeat\n\n"
                    continue

                if event is None:
                    return  # Sentinel: unsubscribe signal

                yield (
                    f"id: {event.event_id}\n"
                    f"event: {event.event_type}\n"
                    f"data: {json.dumps(event.data)}\n\n"
                )
        finally:
            self.unsubscribe(q)
```

### 8.3 SSE Endpoint

```python
# In src/fleet_config/routers/watch.py
from fastapi import Request
from fastapi.responses import StreamingResponse
from ..watch.manager import WatchManager

@router.get("/api/v1/watch")
async def watch(request: Request):
    """
    Open an SSE connection to receive config and flag change events.

    Query parameters:
      - `namespaces`: comma-separated list of namespaces to watch (optional, default: all)
      - `flags`: comma-separated list of flag names to watch (optional, default: all)
    """
    last_event_id = request.headers.get("Last-Event-ID")
    manager: WatchManager = request.app.state.watch_manager
    q = manager.subscribe(last_event_id)

    return StreamingResponse(
        manager.stream(q),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
```

### 8.4 Reconnect Semantics

1. Client disconnects (network blip, restart, etc.).
2. Client reconnects and sends `Last-Event-ID: <id>` header (the last event ID it successfully processed).
3. `WatchManager.subscribe(last_event_id)` creates a new queue and replays missed events by querying the `audit_log` table for events with `id > last_event_id`.
4. If the gap exceeds 1000 events, the manager sends a `"state_resync"` event instructing the client to do a full refresh.
5. Heartbeat every 30 seconds prevents intermediaries from closing idle connections.

### 8.5 Event Shapes

**Config changed:**

```
event: config.changed
id: 42
data: {
  "namespace": "payments.stripe",
  "key": "webhook_url",
  "version": 7,
  "actor": "backend-prod",
  "timestamp": "2025-07-11T14:23:00Z"
}
```

**Flag changed:**

```
event: flag.changed
id: 43
data: {
  "name": "dark-mode",
  "enabled": true,
  "rollout_percentage": 50,
  "actor": "backend-prod",
  "timestamp": "2025-07-11T14:24:00Z"
}
```

---

## 9. Deployment Topology

### 9.1 Single Container

The entire service runs as one container. SQLite is the only stateful component, and its file lives on a Docker volume mount.

```
┌─────────────────────────────────────┐
│         fleet-config container       │
│                                     │
│  uvicorn fleet_config.main:app      │
│  --host 0.0.0.0 --port 8080        │
│  --workers 1                        │
│                                     │
│  /data/fleet-config.db  ◀── volume  │
└──────────────┬──────────────────────┘
               │ port 8080
        ┌──────▼──────┐
        │  Reverse    │  (optional: nginx / caddy / cloud LB)
        │  Proxy / LB │
        └──────┬──────┘
               │ port 443
         External traffic
```

### 9.2 Dockerfile

```dockerfile
# docker/Dockerfile
FROM python:3.12-slim-bookworm AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

COPY src/ src/

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

CMD ["uvicorn", "fleet_config.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
```

> **Why `--workers 1`?** SQLite allows only one writer at a time. Multiple uvicorn workers would cause `database is locked` errors under concurrent writes. When migrating to Postgres, increase `--workers` to match CPU cores.

### 9.3 docker-compose.yml

```yaml
# docker/docker-compose.yml
version: "3.9"

services:
  fleet-config:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "8080:8080"
    volumes:
      - fleet-config-data:/data
    environment:
      - FLEET_CONFIG_DATABASE_URL=sqlite+aiosqlite:///data/fleet-config.db
      - FLEET_CONFIG_LOG_LEVEL=info
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/healthz"]
      interval: 10s
      timeout: 3s
      start_period: 5s
      retries: 3
    restart: unless-stopped

volumes:
  fleet-config-data:
    driver: local
```

### 9.4 Configuration via Environment Variables

All settings are loaded by `pydantic-settings` from environment variables (with optional `.env` file fallback):

| Variable | Default | Description |
|----------|---------|-------------|
| `FLEET_CONFIG_DATABASE_URL` | `sqlite+aiosqlite:///data/fleet-config.db` | SQLAlchemy async connection string. |
| `FLEET_CONFIG_HOST` | `0.0.0.0` | Uvicorn bind host. |
| `FLEET_CONFIG_PORT` | `8080` | Uvicorn bind port. |
| `FLEET_CONFIG_LOG_LEVEL` | `info` | Python log level. |
| `FLEET_CONFIG_WORKERS` | `1` | Uvicorn worker count. |
| `FLEET_CONFIG_CORS_ORIGINS` | `*` | Comma-separated allowed origins (or `*`). |
| `FLEET_CONFIG_HEARTBEAT_INTERVAL` | `30` | Seconds between SSE heartbeats. |

### 9.5 Migrating to Postgres

1. Change `FLEET_CONFIG_DATABASE_URL` to `postgresql+asyncpg://user:pass@host:5432/fleetconfig`.
2. Add `asyncpg` to dependencies.
3. Increase `FLEET_CONFIG_WORKERS` to `4` (or number of CPU cores).
4. Run Alembic migrations (future work; initial deployment uses `create_all`).
5. No application code changes are required — the Repository Layer isolates all dialect-specific SQL.

---

## 10. Directory Structure

```
fleet-config/
├── src/
│   └── fleet_config/
│       ├── __init__.py              # Package init, version string
│       ├── main.py                  # FastAPI app factory, lifespan, middleware registration
│       ├── config.py                # Settings class (pydantic-settings)
│       ├── database.py              # AsyncEngine, AsyncSession factory, Base declarative
│       ├── errors.py                # Custom exceptions, global error handlers
│       ├── models/
│       │   ├── __init__.py          # Re-exports all models
│       │   ├── config_value.py      # ConfigValue + ConfigVersion ORM models
│       │   ├── feature_flag.py      # FeatureFlag ORM model
│       │   ├── api_key.py           # ApiKey ORM model
│       │   └── audit_log.py         # AuditLog ORM model
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── config.py            # ConfigCreate, ConfigUpdate, ConfigResponse, ConfigVersionResponse
│       │   ├── flag.py              # FlagCreate, FlagUpdate, FlagResponse, EvaluateRequest, EvaluateResponse
│       │   ├── api_key.py           # ApiKeyCreate, ApiKeyResponse (omits hash), ApiKeyCreatedResponse (includes raw key)
│       │   ├── audit.py             # AuditLogResponse
│       │   └── common.py            # ErrorBody, PaginationParams, PaginatedResponse
│       ├── repositories/
│       │   ├── __init__.py
│       │   ├── base.py              # BaseRepository with generic CRUD helpers
│       │   ├── config_value.py      # ConfigValueRepository
│       │   ├── config_version.py    # ConfigVersionRepository
│       │   ├── feature_flag.py      # FeatureFlagRepository
│       │   ├── api_key.py           # ApiKeyRepository
│       │   └── audit_log.py         # AuditLogRepository
│       ├── services/
│       │   ├── __init__.py
│       │   ├── config_service.py    # Config CRUD, version bumping, rollback logic
│       │   ├── flag_service.py      # Flag CRUD, evaluation engine
│       │   ├── api_key_service.py   # Key generation, hashing, revocation
│       │   ├── audit_service.py     # Audit log writes + queries
│       │   └── watch_service.py     # Bridges service-layer events to WatchManager
│       ├── routers/
│       │   ├── __init__.py
│       │   ├── config.py            # /api/v1/configs routes
│       │   ├── flags.py             # /api/v1/flags routes
│       │   ├── api_keys.py          # /api/v1/api-keys routes
│       │   ├── audit.py             # /api/v1/audit-log routes
│       │   ├── watch.py             # /api/v1/watch SSE endpoint
│       │   └── system.py            # /healthz, /readyz
│       ├── middleware/
│       │   ├── __init__.py
│       │   └── auth.py              # AuthMiddleware: Bearer token validation, scope enforcement
│       └── watch/
│           ├── __init__.py
│           └── manager.py           # WatchManager: in-process event bus, subscriber queues
├── tests/
│   ├── conftest.py                  # Shared fixtures: test client, in-memory DB, seed data
│   ├── test_config_crud.py
│   ├── test_config_versions.py
│   ├── test_flag_evaluation.py
│   ├── test_api_keys.py
│   ├── test_audit_log.py
│   ├── test_auth_middleware.py
│   └── test_watch_sse.py
├── docs/
│   ├── ARCHITECTURE.md              # This document
│   ├── API.md                       # Generated or hand-written API reference
│   └── SDK.md                       # Client SDK usage guide
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── pyproject.toml                   # Project metadata, dependencies, tool config
├── uv.lock                          # Lockfile
└── README.md                        # Quick-start guide
```

### Layer Dependency Rules

Dependency flows **strictly downward**:

```
routers ──▶ services ──▶ repositories ──▶ database
   │               │
   │               └──▶ watch/manager (publish events)
   │
   └──▶ schemas (request/response shapes)
   
middleware ──▶ repositories (key lookup)
```

- **Routers** never import repositories directly.
- **Services** never import FastAPI objects (`Request`, `Response`).
- **Repositories** never import services or routers.
- **Schemas** are pure data classes with no business logic.
- **Models** are SQLAlchemy ORM classes with no FastAPI coupling.

---

*End of Architecture Document.*
