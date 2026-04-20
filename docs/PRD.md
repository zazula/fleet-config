# fleet-config — Product Requirements Document

**Version:** 1.0  
**Owner:** zazula  
**Status:** Draft  
**Last Updated:** 2025-01-24  

---

## 1. Problem Statement

Config is sprawled across the zazula fleet. Environment variables, YAML files, JSON constants, and hardcoded defaults are scattered across dozens of services and scripts with no centralized registry, no versioning, and no audit trail. This creates three concrete failure modes that happen regularly:

- **Unknown provenance.** An operator notices a service behaving oddly. They trace it to a config value, but they cannot determine who set it, when, or what the prior value was. Investigation becomes archaeology.
- **Uncontrolled rollout.** A feature flag lives in a Python module constant. Enabling it for 5% of users requires code changes and a deploy — there is no gradual rollout path, no rollback, and no way to evaluate flag state without shipping new code.
- **Config drift.** Two services read from two different YAML files that were supposed to be in sync. They are not. Nobody notices until a production incident surfaces the divergence hours later.

fleet-config exists to eliminate these failure modes by serving as the single source of truth for all fleet configuration and feature flags, with versioned writes, full audit history, and real-time change propagation.

---

## 2. Target Users

### 2a. Fleet Operators (zazula)

The human operator who owns and evolves the fleet. They need a reliable, scriptable interface to read, write, list, and audit config across every namespace. Their primary interface is the Python SDK and the REST API — not a web UI.

### 2b. Agent Processes (Runtime Readers)

Every long-running agent process in the fleet needs config values at runtime. These processes must be able to:

- Read config values on startup and on-demand
- Subscribe to change events so they can react to config updates without restart
- Evaluate feature flags for specific user contexts (user ID, cohort, etc.)

Agents are not trusted with write access — they are read-only consumers.

### 2c. CI/CD Pipelines

CI/CD pipelines need to toggle feature flags as part of deploy workflows — enabling a flag for a specific branch, percentage rollout, or time-gated activation. Pipelines authenticate as service accounts with API keys scoped to write-only access to the flags API.

---

## 3. User Stories

### US-001: Set a Config Value

**As a** fleet operator  
**I want to** set a config value for a namespace and key  
**So that** the value is centralized and available to all readers immediately  

**Acceptance Criteria:**
- `PUT /api/v1/namespaces/{ns}/keys/{key}` stores the value with the current timestamp and operator identity
- The write is persisted and readable in subsequent reads
- The response includes the new version number

---

### US-002: Read a Config Value

**As a** fleet operator or agent process  
**I want to** read a config value by namespace and key  
**So that** I can use it in scripts or at runtime  

**Acceptance Criteria:**
- `GET /api/v1/namespaces/{ns}/keys/{key}` returns the latest value, version, and updated-at timestamp
- If the key does not exist, returns 404 with a descriptive message
- Authenticated readers see the value; unauthenticated requests are rejected

---

### US-003: List All Keys in a Namespace

**As a** fleet operator  
**I want to** list every config key in a namespace with their current values and metadata  
**So that** I can audit what config exists and spot stale or unexpected keys  

**Acceptance Criteria:**
- `GET /api/v1/namespaces/{ns}/keys` returns a paginated list of key entries (key, value, version, updated_at, updated_by)
- Supports cursor-based pagination with configurable page size
- Returns empty list with 200 for namespaces that have no keys (not a 404)

---

### US-004: View Config History

**As a** fleet operator  
**I want to** view the full version history of a key  
**So that** I can trace what changed, when, and by whom  

**Acceptance Criteria:**
- `GET /api/v1/namespaces/{ns}/keys/{key}/history` returns a chronological list of every version, each with: version number, value snapshot, changed_at timestamp, changed_by identity
- History is immutable — no entries are ever deleted or altered, only appended
- Returns 404 if the key has no history (key does not exist)

---

### US-005: Roll Back a Config Value

**As a** fleet operator  
**I want to** roll back a key to a previous version  
**So that** I can undo a bad change safely without manual re-entry  

**Acceptance Criteria:**
- `POST /api/v1/namespaces/{ns}/keys/{key}/rollback` accepts `{ "version": N }` and writes a new version with the value from version N
- The rollback operation itself is recorded in the audit log as a rollback event with the source version noted
- Rollback to the current version is a no-op that returns 200 without creating a new version
- The new version number is always current highest + 1 (not overwritten)

---

### US-006: Create a Feature Flag

**As a** fleet operator  
**I want to** create a feature flag with rollout rules  
**So that** I can control new features without code deploys  

**Acceptance Criteria:**
- `POST /api/v1/flags` accepts `{ "key": "my-flag", "namespace": "payments", "description": "...", "enabled": false, "default_value": false, "rules": [...] }`
- Rules support: `rollout_percentage` (integer 0–100), `user_id` allow-list, `cohort` matching
- Flag creation is idempotent on key+namespace — creating an existing flag returns the existing record without error
- Flag rules are evaluated in order; first matching rule wins

---

### US-007: Evaluate a Feature Flag for a User Context

**As a** fleet operator, agent process, or CI/CD pipeline  
**I want to** evaluate a feature flag for a specific context  
**So that** I can determine whether a feature is active for a user  

**Acceptance Criteria:**
- `POST /api/v1/flags/{flag_key}/evaluate` accepts `{ "namespace": "payments", "user_id": "u123", "cohort": "beta", "request_id": "req-456" }`
- Returns `{ "value": true/false, "source": "rule:3" | "default", "flag_key": "...", "evaluated_at": "..." }`
- If the flag does not exist, returns 404
- Evaluation is deterministic — same context always returns same result
- The evaluation decision is logged in the audit log with a 1-minute debounce per (flag_key, user_id) to prevent log flooding

---

### US-008: Watch a Namespace for Config Changes

**As a** agent process  
**I want to** subscribe to changes in a namespace via SSE  
**So that** I can reload config in real time without polling  

**Acceptance Criteria:**
- `GET /api/v1/namespaces/{ns}/watch` opens an SSE stream
- Events are delivered on every write, rollback, or flag evaluation within the namespace
- Events include: event type (`key_created`, `key_updated`, `key_rolled_back`, `flag_created`, `flag_updated`), key/flag name, new version, changed_by, changed_at
- Stream is authenticated via `Authorization: Bearer <api_key>` query param or header
- Client reconnection after disconnect re-sends the last-seen version marker

---

### US-009: Create an API Key

**As a** fleet operator  
**I want to** create a scoped API key for a service account  
**So that** agents and pipelines can authenticate without sharing my credentials  

**Acceptance Criteria:**
- `POST /api/v1/api-keys` accepts `{ "name": "payments-agent", "scopes": ["read:config", "write:flags", "evaluate:flags"] }`
- On creation, the API key is returned exactly once — it is not stored or retrievable after the initial response
- Key names are unique; creating a duplicate name returns 409 Conflict
- API key metadata (name, scopes, created_at, last_used_at, is_active) is stored; the key value itself is stored as a bcrypt hash

---

### US-010: Rotate an API Key

**As a** fleet operator  
**I want to** rotate an API key  
**So that** I can invalidate a compromised key without disrupting the service if the key is stored in a secrets manager  

**Acceptance Criteria:**
- `POST /api/v1/api-keys/{key_id}/rotate` generates a new key value, updates the stored hash, and returns the new key value exactly once
- The old key is invalidated immediately on rotation
- All active sessions using the old key receive an error on next request
- Rotation is recorded in the audit log with operator identity and key name

---

## 4. Goals

### 4.1 Single Source of Truth

Every config value and feature flag used by any fleet service must be readable from fleet-config. No service reads from an env var or YAML file that duplicates a value also managed in fleet-config. This goal has a 30-day success horizon after MVP launch.

### 4.2 Versioned Writes with Full History

Every write creates a new immutable version. No value is ever silently overwritten — every change is auditable. History is never deleted.

### 4.3 Gradual Rollout via Feature Flags

Flags support percentage-based rollout and rule-based matching (user ID, cohort). No code deploy is required to change rollout percentage or toggle a flag. Evaluations are fast and deterministic.

### 4.4 Real-Time Change Notification

Agents subscribe via SSE and receive change events within 500ms of the write completing. No polling required.

### 4.5 API-Key Auth with Audit Trail

Every authenticated request is logged with: actor identity, action, target, timestamp, request ID. The audit log is append-only. API keys are bcrypt-hashed and scoped to specific operation types.

---

## 5. Non-Goals (MVP)

The following are explicitly out of scope for the MVP. They appear as stretch goals in §8.

| Item | Reason for Exclusion |
|------|----------------------|
| Admin web UI | Operators are comfortable with SDK/scripting; a UI is a distraction from core API work |
| Multi-tenant isolation | Single-operator; namespace isolation is sufficient for MVP |
| Secret encryption at rest | Config values are not secrets (secrets live in a separate system); no PII in MVP scope |
| Prometheus metrics | Observability is a post-MVP concern; basic health endpoint is sufficient |
| Rate limiting | Single operator; no untrusted callers in MVP |
| PostgreSQL backend | SQLite is sufficient for <100 namespaces and <10k keys; schema is designed for later migration |

---

## 6. Success Metrics

| Metric | Target | Measurement Method |
|--------|--------|--------------------|
| Fleet adoption | 100% of fleet services reading from fleet-config | Service audit script that checks for env-var and YAML-based config sources |
| Read latency p99 | <50ms | Synthetic monitoring hitting GET endpoints with SQLite under realistic read load |
| Config drift incidents | Zero | Monthly audit comparing fleet config state to fleet-config's recorded state |
| Test coverage | >90% line coverage | `pytest --cov` with threshold enforcement in CI |

---

## 7. MVP Scope

### 7.1 REST API

All endpoints serve under `/api/v1/`. JSON request/response bodies. Standard HTTP status codes. Auth via Bearer token (API key).

**Config API:**

```
GET    /namespaces/{ns}/keys              # list keys (paginated)
GET    /namespaces/{ns}/keys/{key}        # read a key
PUT    /namespaces/{ns}/keys/{key}        # set/update a key
DELETE /namespaces/{ns}/keys/{key}        # soft-delete a key (mark inactive, keep history)
GET    /namespaces/{ns}/keys/{key}/history # version history
POST   /namespaces/{ns}/keys/{key}/rollback # rollback to version N
GET    /namespaces/{ns}/watch             # SSE stream for namespace changes
POST   /namespaces/{ns}                    # create namespace (idempotent)
```

**Flags API:**

```
POST   /flags                              # create flag
GET    /flags/{flag_key}                   # read flag definition
PUT    /flags/{flag_key}                   # update flag
DELETE /flags/{flag_key}                   # delete flag
POST   /flags/{flag_key}/evaluate          # evaluate flag for context
GET    /namespaces/{ns}/flags              # list flags in namespace
```

**Auth API:**

```
POST   /api-keys                           # create API key
GET    /api-keys                           # list API key metadata (no values)
DELETE /api-keys/{key_id}                  # revoke API key
POST   /api-keys/{key_id}/rotate           # rotate key
```

**Health:**

```
GET    /health                             # 200 OK when service is running
```

---

### 7.2 Feature Flag Evaluation Rules

Flags support the following rule types, evaluated in order:

1. **`rollout_percentage`** — `{"type": "rollout", "percentage": N}`: Evaluate `hash(flag_key + user_id) % 100 < N`. Deterministic. Persisted across restarts.
2. **`user_allowlist`** — `{"type": "user_allowlist", "user_ids": ["u1", "u2"]}`: Match if `user_id in user_ids`. Exact string match.
3. **`cohort`** — `{"type": "cohort", "cohort": "beta"}`: Match if `cohort` in evaluation context matches `cohort` in rule.
4. **`default_value`** — The value returned when no rule matches or flag is disabled.

A flag's `enabled` field must be `true` for rules to be evaluated; otherwise `default_value` is returned.

---

### 7.3 SQLite Storage

**Schema (SQLite):**

```sql
-- namespaces
CREATE TABLE namespaces (
  id          TEXT PRIMARY KEY,
  name        TEXT UNIQUE NOT NULL,
  created_at  TEXT NOT NULL,
  created_by  TEXT NOT NULL
);

-- config keys (current state)
CREATE TABLE config_keys (
  id          TEXT PRIMARY KEY,
  namespace   TEXT NOT NULL REFERENCES namespaces(name),
  key         TEXT NOT NULL,
  value       TEXT NOT NULL,          -- JSON-encoded string value
  version     INTEGER NOT NULL,
  created_at  TEXT NOT NULL,
  created_by  TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  updated_by  TEXT NOT NULL,
  is_active   INTEGER NOT NULL DEFAULT 1,
  UNIQUE(namespace, key)
);

-- config key history (immutable)
CREATE TABLE config_key_history (
  id          TEXT PRIMARY KEY,
  namespace   TEXT NOT NULL,
  key         TEXT NOT NULL,
  version     INTEGER NOT NULL,
  value       TEXT NOT NULL,
  event_type  TEXT NOT NULL,          -- 'created' | 'updated' | 'rolled_back'
  changed_at  TEXT NOT NULL,
  changed_by  TEXT NOT NULL
);

-- feature flags
CREATE TABLE flags (
  id           TEXT PRIMARY KEY,
  flag_key     TEXT NOT NULL,
  namespace    TEXT NOT NULL,
  description  TEXT,
  enabled      INTEGER NOT NULL DEFAULT 0,
  default_value INTEGER NOT NULL DEFAULT 0,
  rules        TEXT NOT NULL,         -- JSON array
  version      INTEGER NOT NULL,
  created_at   TEXT NOT NULL,
  created_by   TEXT NOT NULL,
  updated_at   TEXT NOT NULL,
  updated_by   TEXT NOT NULL,
  is_active    INTEGER NOT NULL DEFAULT 1,
  UNIQUE(flag_key, namespace)
);

-- feature flag history
CREATE TABLE flag_history (
  id          TEXT PRIMARY KEY,
  flag_key    TEXT NOT NULL,
  namespace   TEXT NOT NULL,
  version     INTEGER NOT NULL,
  description TEXT,
  enabled     INTEGER NOT NULL,
  default_value INTEGER NOT NULL,
  rules       TEXT NOT NULL,
  event_type  TEXT NOT NULL,
  changed_at  TEXT NOT NULL,
  changed_by  TEXT NOT NULL
);

-- api keys
CREATE TABLE api_keys (
  id           TEXT PRIMARY KEY,
  name         TEXT UNIQUE NOT NULL,
  key_hash     TEXT NOT NULL,         -- bcrypt hash
  scopes       TEXT NOT NULL,         -- JSON array of scope strings
  created_at   TEXT NOT NULL,
  created_by   TEXT NOT NULL,
  last_used_at TEXT,
  is_active    INTEGER NOT NULL DEFAULT 1
);

-- audit log
CREATE TABLE audit_log (
  id          TEXT PRIMARY KEY,
  timestamp   TEXT NOT NULL,
  actor       TEXT NOT NULL,          -- api_key name or 'system'
  action      TEXT NOT NULL,          -- e.g. 'config.set', 'flag.evaluate'
  target      TEXT NOT NULL,          -- e.g. 'ns:payments:key:timeout'
  request_id  TEXT NOT NULL,
  metadata    TEXT,                    -- JSON object
  debounce_key TEXT                   -- hash of (action, target) for debounce
);
```

Indexes on `config_keys(namespace, key)`, `config_key_history(namespace, key, version)`, `flags(flag_key, namespace)`, `audit_log(timestamp)`.

---

### 7.4 Python SDK

`fleet_config` — a Python client library with:

```python
from fleet_config import FleetConfigClient

client = FleetConfigClient(base_url="http://fleet-config:8080", api_key="...")

# Config
client.config.get(ns="payments", key="timeout_ms")
client.config.set(ns="payments", key="timeout_ms", value=5000)
client.config.list(ns="payments", cursor=None, limit=50)
client.config.history(ns="payments", key="timeout_ms")
client.config.rollback(ns="payments", key="timeout_ms", version=3)

# Flags
client.flags.create(key="new-checkout-flow", ns="payments", rules=[...])
client.flags.get(key="new-checkout-flow", ns="payments")
client.flags.evaluate(key="new-checkout-flow", ns="payments", user_id="u123")

# Watch
for event in client.watch("payments"):
    print(event)  # ServerSentEvent
    # event.type, event.key, event.version, event.changed_by, event.changed_at
```

SDK handles: Bearer token injection, retry with backoff (3 attempts, 1s/2s/4s), request ID generation, SSE stream reconnection with `Last-Event-ID`.

---

### 7.5 Docker + Compose

`Dockerfile` — Alpine-based Python image, single-stage, <100MB.  
`docker-compose.yml` — defines `fleet-config` service with volume mount for SQLite DB file, health check, restart policy.

---

### 7.6 CI

- **Test runner:** `pytest` with `pytest-cov`, `ruff` linting, `mypy` type checking
- **Workflow triggers:** PR (all checks), push to `main` (all checks + deploy)
- **Secrets:** API key for deployment stored as repo secrets; no keys in source
- **Threshold enforcement:** Coverage fails if `<90%` lines covered

---

### 7.7 Documentation

- This PRD (current document)
- `docs/api.md` — Endpoint reference with request/response schemas
- `docs/sdk.md` — SDK usage guide with examples
- `docs/ops.md` — Operate, upgrade, and backup runbook
- `README.md` — Quick-start guide

---

## 8. Stretch Goals (Post-MVP Epics)

Ordered by priority.

### SG-1: PostgreSQL Backend
Migrate SQLite → PostgreSQL. Add connection pooling (PgBouncer). Schema changes are minimal (same tables, same columns). Needed when: fleet grows >100 namespaces or p99 read latency exceeds 50ms target.

### SG-2: Admin Web UI
Read-only and read-write admin interface for config and flag management. Built with FastAPI + HTMX or a lightweight React frontend. Needed for: onboarding non-operator contributors who prefer GUIs.

### SG-3: Per-Tenant Isolation
Namespace-scoped permissions: API keys can be scoped to specific namespaces. Enables safe sharing of fleet-config across multiple teams without namespace-cross read access.

### SG-4: Secret Encryption at Rest
Values flagged as `is_secret: true` are encrypted with Fernet (AES-128-CBC) before SQLite/PG storage. Key stored in env var or a KMS. Needed when: secrets must be stored in fleet-config rather than a dedicated secrets manager.

### SG-5: Prometheus Metrics Endpoint
`GET /metrics` exposes: request latency histogram, request count by endpoint, flag evaluation count by flag, SSE connection count. Enables dashboarding and alerting without third-party APM.

### SG-6: Rate Limiting
Per-API-key rate limits configurable per scope. In-memory token bucket for MVP; Redis-backed for Postgres backend. Needed when: fleet operators express concern about runaway agents creating evaluation storms.

### SG-7: Webhook Notifications
Flag evaluation and config write webhooks. Operators register a URL; fleet-config POSTs event payloads to it. Needed when: services outside the agent fleet need to react to config changes (slack notifications, external systems, etc.).

---

## 9. Constraints & Assumptions

### 9.1 Scale Boundaries

| Dimension | Limit | Rationale |
|-----------|-------|-----------|
| Namespaces | <100 | Fleet is not multi-tenant; namespace-per-service is sufficient |
| Config keys | <10,000 | Average of 100 keys per namespace; manageable in SQLite |
| Feature flags | <100 | Flags are created sparingly; low count expected |
| SSE connections | <500 | Estimated agent count; requires SSE scaling work in stretch goals |

### 9.2 Operational Assumptions

- **Single operator:** Only zazula creates namespaces, API keys, and writes config. No multi-user conflict resolution needed.
- **Persistent volume:** SQLite DB lives on a persistent volume. If the volume is lost, the audit log and history are lost. This is accepted at MVP stage; Postgres migration enables point-in-time recovery.
- **No horizontal scaling (MVP):** A single fleet-config instance handles all traffic. Operators are responsible for not exceeding the single-instance capacity envelope. Load testing is required before declaring the MVP complete.
- **Agents are trusted:** Agents that can connect to fleet-config are trusted processes on the fleet network. API key compromise is treated as equivalent to a compromised service account — rotation is the recovery path, not network-layer blocking.

### 9.3 Technology Choices

- **FastAPI** — Python ASGI framework for the API server. Chosen for Pydantic validation, auto-generated OpenAPI docs, and native SSE support.
- **SQLite** — File-based storage via `aiosqlite` for async API. Chosen for operational simplicity (no DB server process) and acceptable read performance at MVP scale.
- **bcrypt** — For API key hashing. Parameters: `cost=12`.
- **sse-starlette** — SSE streaming for watch endpoints. Supports `Last-Event-ID` for reconnection.

---

## 10. Risks

### Risk 1: SQLite Concurrency Limits

**Severity:** Medium  
**Likelihood:** Medium  
**Description:** SQLite uses file-level locking. Concurrent reads are fine; concurrent writes serialize through a write lock. Under active config writes from multiple sources, write latency can spike and reads can be briefly blocked. With <100 namespaces and <10k keys, the probability of concurrent writes is low in the single-operator model, but CI pipelines and agents could create write contention during a deploy storm.

**Mitigation:**
- Use `WAL` mode (`PRAGMA journal_mode=WAL`) to allow concurrent reads during writes
- Use `IMMEDIATE` transaction mode for writes to fail fast rather than block
- Monitor write latency; if p99 exceeds 200ms, prioritize the Postgres migration
- Document that operators should batch flag updates rather than concurrent writes during deploy windows

---

### Risk 2: SSE Connection Scaling

**Severity:** Medium  
**Likelihood:** Low (MVP) → Medium (stretch)  
**Description:** Each SSE watch consumes a goroutine/thread and holds a DB connection for the SSE cursor. At scale (>100 concurrent watchers), this can exhaust connection pools and memory.

**Mitigation:**
- SSE cursors use an in-memory ring buffer of recent events rather than a persistent DB cursor
- Connection per SSE session uses a short-lived read connection rather than a held connection
- Cap concurrent SSE connections at 500; return 503 when cap is hit
- Add connection count metric as part of SG-5 (Prometheus metrics)

---

### Risk 3: API Key Leakage

**Severity:** High  
**Likelihood:** Medium  
**Description:** An API key written to a log file, pasted in a Slack message, or committed to a git repo is a full compromise. The key grants access to config write and flag manipulation depending on scope.

**Mitigation:**
- API key is returned only at creation time and on rotation — no retrieval mechanism exists
- SDK does not log request headers or API key values
- Operate runbook (§7.4 in `docs/ops.md`) specifies: store keys in a secrets manager, rotate immediately on any suspected exposure
- Rotate operation (§3, US-010) provides a fast recovery path
- Audit log captures every action taken with each key, enabling post-hoc forensic tracing of unauthorized use
- No admin UI in MVP reduces the attack surface (no browser-based key exposure)

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| Namespace | A logical grouping of config keys and flags (e.g., `payments`, `auth`, `notifications`). Analogy: a database schema. |
| Config Key | A named, versioned, typed config value within a namespace. Analogous to a config map entry in Kubernetes. |
| Feature Flag | A named toggle with optional rules that returns a boolean value for a given evaluation context. |
| Rollout % | Percentage of users who receive a feature-enabled evaluation, determined by deterministic hashing of `flag_key + user_id`. |
| Rule | An evaluation condition attached to a feature flag. Rules are evaluated in order; first match wins. |
| API Key | A bearer token scoped to specific operations. Stored as bcrypt hash; plaintext shown exactly once at creation. |
| Audit Log | An immutable append-only log of all authenticated operations with actor, action, target, timestamp, and request ID. |
| SSE Watch | Server-Sent Events stream from a namespace; delivers change events to connected clients in real time. |
| Debounce | Suppression of duplicate audit log entries for the same (action, target) pair within a 60-second window. Used for flag evaluations to prevent log flooding during load. |

---

## Appendix B: Open Questions

| # | Question | Status | Resolution Owner |
|---|----------|--------|------------------|
| OQ-1 | Should flag rules support a `date_range` condition (enable between dates)? | Open | zazula |
| OQ-2 | Should config key values be schema-validated via JSON Schema at write time? | Open | zazula |
| OQ-3 | What is the SQLite WAL checkpoint frequency? Does ops need to configure it? | Open | zazula |
| OQ-4 | Will agents use the SSE watch in practice, or will they prefer short polling? | Open | zazula |
| OQ-5 | Should the SDK provide a context manager for watch streams with auto-reconnect? | Open | zazula |

---
