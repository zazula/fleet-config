# fleet-config — Backlog

> Master epic and task hierarchy. Each epic is a labeled GitHub issue; each task is a child issue linked to its parent.

---

## E1: Project Scaffolding

**Objective:** Establish the repo structure, tooling, and base application so every subsequent epic has a clean foundation to build on.

### T1.1: Initialize project structure
**Description:** Create `pyproject.toml` with all dependencies (fastapi, uvicorn, sqlalchemy[asyncio], aiosqlite, pydantic, pydantic-settings, httpx, ruff, mypy, pytest, pytest-asyncio). Set up the `src/fleet_config/` package layout with empty `__init__.py` files. Configure ruff and mypy in `pyproject.toml`.
**Acceptance Criteria:**
- [ ] `pyproject.toml` exists with all deps and dev-deps pinned
- [ ] `src/fleet_config/__init__.py` exists
- [ ] `ruff check src/` passes with zero errors
- [ ] `pip install -e ".[dev]"` succeeds
**Role:** engineer-core-api
**Labels:** mvp, role:engineer

### T1.2: Base FastAPI application
**Description:** Implement the app factory in `main.py` with a `create_app()` function. Add a `GET /health` endpoint returning `{"status": "healthy", "version": "0.1.0"}`. Configure settings via pydantic-settings (`DATABASE_URL`, `LOG_LEVEL`, `HOST`, `PORT`). Set up structured JSON logging with `structlog`.
**Acceptance Criteria:**
- [ ] `GET /health` returns 200 with status and version
- [ ] Settings are loaded from environment variables with defaults
- [ ] Logs are structured JSON
- [ ] `uvicorn fleet_config.main:app` starts without error
**Role:** engineer-core-api
**Labels:** mvp, role:engineer

### T1.3: Database setup
**Description:** Create the async SQLAlchemy engine factory, async session maker, and declarative base. Implement an `init_db()` function that creates all tables on startup (for SQLite dev mode). Support `DATABASE_URL` env var (default: `sqlite+aiosqlite:///./fleet_config.db`). Enable WAL mode for SQLite.
**Acceptance Criteria:**
- [ ] Async engine and session factory work with aiosqlite
- [ ] `init_db()` creates tables on first run
- [ ] WAL mode is enabled for SQLite
- [ ] Sessions are properly scoped (dependency injection via FastAPI)
**Role:** engineer-core-api
**Labels:** mvp, role:engineer

### T1.4: Pre-commit hooks + lint config
**Description:** Add `.pre-commit-config.yaml` with ruff, mypy, and trailing-whitespace hooks. Create a `Makefile` with targets: `lint`, `format`, `test`, `typecheck`, `all`. Add `ruff.toml` or `pyproject.toml` ruff section with line-length=120, target python 3.12.
**Acceptance Criteria:**
- [ ] `pre-commit run --all-files` passes
- [ ] `make lint` runs ruff + mypy
- [ ] `make test` runs pytest
- [ ] All targets documented in README
**Role:** devops-deploy
**Labels:** mvp, role:devops

### T1.5: Initial test harness
**Description:** Set up `pytest-asyncio` with auto mode. Create `tests/conftest.py` with fixtures for an in-memory SQLite test database, a test client (httpx AsyncClient), and a clean-database fixture that drops/creates tables between tests. Write a smoke test for `GET /health`.
**Acceptance Criteria:**
- [ ] `pytest` runs and passes the health smoke test
- [ ] Test database is in-memory and isolated per test
- [ ] Fixtures are reusable across test modules
- [ ] `conftest.py` provides `client`, `db_session`, and `app` fixtures
**Role:** qa-test
**Labels:** mvp, role:qa

---

## E2: Core Config CRUD

**Objective:** Implement the core configuration storage and API — the foundational value proposition of the service.

### T2.1: Config SQLAlchemy models
**Description:** Create `config_values` and `config_versions` tables per `docs/ARCHITECTURE.md`. `config_values`: id (INTEGER PK), namespace (TEXT NOT NULL), key (TEXT NOT NULL), value_json (TEXT NOT NULL), value_type (TEXT NOT NULL), current_version_id (INTEGER FK→config_versions.id), created_at, updated_at. Unique constraint on (namespace, key). `config_versions`: id (INTEGER PK), config_value_id (INTEGER FK), version_number (INTEGER NOT NULL), value_json (TEXT NOT NULL), actor (TEXT NOT NULL), created_at.
**Acceptance Criteria:**
- [ ] Models defined with correct columns, types, constraints, indexes
- [ ] Unique constraint on (namespace, key) in config_values
- [ ] Index on namespace for fast listing
- [ ] Foreign keys properly defined
**Role:** engineer-core-api
**Labels:** mvp, role:engineer

### T2.2: Config repository
**Description:** Implement an async data access layer (`ConfigRepository`) with methods: `get(namespace, key)`, `set(namespace, key, value, value_type, actor)`, `delete(namespace, key)`, `list_by_namespace(namespace, prefix, cursor, limit)`. The `set` method should create a new config_values row if not exists, or update + create a version row if exists.
**Acceptance Criteria:**
- [ ] All CRUD methods work against async session
- [ ] `set` creates version row on every write
- [ ] `list_by_namespace` supports prefix filtering and cursor pagination
- [ ] `get` returns None for missing keys
- [ ] `delete` raises if key not found
**Role:** engineer-core-api
**Labels:** mvp, role:engineer

### T2.3: Config service
**Description:** Business logic layer (`ConfigService`) that wraps the repository. On `set`: validate value against value_type (e.g., "int" must be int-convertible), create version, update current_version_id. On `delete`: verify key exists first. On `list`: build cursor from last id. Publish change event to watch bus (if available).
**Acceptance Criteria:**
- [ ] Type validation rejects invalid values (e.g., "abc" for type "int")
- [ ] Version numbers are monotonically increasing per key
- [ ] `current_version_id` always points to latest version
- [ ] Change events published on set/delete
**Role:** engineer-core-api
**Labels:** mvp, role:engineer

### T2.4: Config router
**Description:** FastAPI router at `/config` prefix. Endpoints: `PUT /config/{namespace}/{key}`, `GET /config/{namespace}/{key}`, `DELETE /config/{namespace}/{key}`, `GET /config/{namespace}`. Request/response schemas via Pydantic models. Proper HTTP status codes (200, 201, 204, 404, 422). Auth: require `config:read` for GET, `config:write` for PUT/DELETE.
**Acceptance Criteria:**
- [ ] All four endpoints return correct status codes
- [ ] Request validation with Pydantic (422 on bad input)
- [ ] 404 for missing keys/namespaces
- [ ] OpenAPI docs auto-generated at `/docs`
**Role:** engineer-core-api
**Labels:** mvp, role:engineer

### T2.5: Config CRUD integration tests
**Description:** Full test suite covering: create new key, update existing key (version increments), read current value, delete key (404 after), list with pagination, list with prefix filter, concurrent writes to different keys, concurrent writes to same key (last-write-wins).
**Acceptance Criteria:**
- [ ] All happy paths tested
- [ ] Error paths tested (404, 422)
- [ ] Pagination tested (cursor returns next page, empty cursor at end)
- [ ] Concurrent write test passes
- [ ] Coverage >90% for config module
**Role:** qa-test
**Labels:** mvp, role:qa

---

## E3: Auth & API Keys

**Objective:** Secure the API with bearer-token authentication backed by API keys stored in the database.

### T3.1: API key model
**Description:** Create `api_keys` table: id (INTEGER PK), name (TEXT NOT NULL UNIQUE), key_hash (TEXT NOT NULL), key_prefix (TEXT NOT NULL), scopes_json (TEXT NOT NULL, default '["admin"]'), created_at, revoked_at (nullable). Index on key_hash for fast lookup, index on key_prefix for identification.
**Acceptance Criteria:**
- [ ] Model defined with all columns and indexes
- [ ] `key_hash` is SHA-256 hex of the full key
- [ ] `key_prefix` stores first 8 chars for identification
- [ ] `revoked_at` nullable, used for soft-delete
**Role:** engineer-core-api
**Labels:** mvp, role:engineer

### T3.2: Key management service
**Description:** Implement `ApiKeyService` with methods: `create_key(name, scopes)` — generates a 32-byte random key, formats as `fc_live_<hex>`, stores SHA-256 hash, returns the full key once; `validate_key(raw_key)` — hashes input, looks up in DB, checks not revoked, returns key record; `revoke_key(key_id)` — sets revoked_at; `list_keys()` — returns all keys with masked hashes.
**Acceptance Criteria:**
- [ ] Generated keys are 64-char hex prefixed with `fc_live_`
- [ ] Hash comparison is constant-time (hmac.compare_digest)
- [ ] Revoked keys return None from validate_key
- [ ] Full key is only returned once (at creation time)
**Role:** engineer-core-api
**Labels:** mvp, role:engineer

### T3.3: Auth middleware
**Description:** FastAPI dependency (`get_current_actor`) that extracts `Authorization: Bearer <token>` header, validates via `ApiKeyService`, injects `actor` (key name) and `scopes` (list) into request state. Returns 401 on missing/invalid header, 403 if key is valid but scope doesn't match the endpoint requirement. `GET /health` is exempt.
**Acceptance Criteria:**
- [ ] Bearer token extracted and validated on every non-health endpoint
- [ ] 401 on missing or malformed Authorization header
- [ ] 403 on valid key but insufficient scope
- [ ] Actor identity available in route handlers via request state
**Role:** engineer-core-api
**Labels:** mvp, role:engineer

### T3.4: Key management router
**Description:** Endpoints: `POST /keys` (create, requires `admin` scope), `GET /keys` (list, requires `admin` scope), `DELETE /keys/{id}` (revoke, requires `admin` scope). Request/response schemas per `docs/API.md`. Response masks key_hash, shows prefix only.
**Acceptance Criteria:**
- [ ] POST returns full key in response (only time it's visible)
- [ ] GET returns list with masked keys
- [ ] DELETE sets revoked_at (idempotent on already-revoked)
- [ ] All endpoints require `admin` scope
**Role:** engineer-core-api
**Labels:** mvp, role:engineer

### T3.5: Auth integration tests
**Description:** Test suite: create key → use it to auth a request, create key with limited scopes → verify scope enforcement, revoke key → verify 401 on next request, missing header → 401, bad token → 401, health endpoint → no auth required.
**Acceptance Criteria:**
- [ ] Full auth lifecycle tested
- [ ] Scope enforcement verified for each scope
- [ ] Health endpoint confirmed exempt
- [ ] Key prefix appears in list response
**Role:** qa-test
**Labels:** mvp, role:qa

---

## E4: Versioning & Audit Log

**Objective:** Provide full change history and an audit trail for compliance and debugging.

### T4.1: Audit log model
**Description:** Create `audit_log` table: id (INTEGER PK), actor (TEXT NOT NULL), action (TEXT NOT NULL, e.g., "config.set", "config.delete", "flag.create"), resource_type (TEXT NOT NULL), resource_id (TEXT NOT NULL, composite like "agents/default_model"), detail_json (TEXT), created_at. Index on (actor, created_at), (action, created_at), (resource_type, resource_id).
**Acceptance Criteria:**
- [ ] Model matches ARCHITECTURE.md spec
- [ ] Indexes support common query patterns
- [ ] `detail_json` stores arbitrary metadata
**Role:** engineer-core-api
**Labels:** mvp, role:engineer

### T4.2: Version history service
**Description:** Extend `ConfigService.set` to auto-create a `config_versions` row with incrementing version_number. Implement `get_history(namespace, key, cursor, limit)` returning versions in descending order (newest first). Publish audit events on every write (config.set, config.delete).
**Acceptance Criteria:**
- [ ] Every config.set creates a version row
- [ ] Version numbers are sequential per key
- [ ] History returns newest first with cursor pagination
- [ ] Audit log rows created on every mutation
**Role:** engineer-core-api
**Labels:** mvp, role:engineer

### T4.3: History endpoint
**Description:** `GET /config/{namespace}/{key}/history` returns `{"versions": [...], "next_cursor": "..."}`. Each version includes version_number, value, actor, created_at. Cursor is the version id. Requires `config:read` scope.
**Acceptance Criteria:**
- [ ] Returns versions in descending order
- [ ] Cursor pagination works correctly
- [ ] 404 for non-existent key
- [ ] Response shape matches API.md
**Role:** engineer-core-api
**Labels:** mvp, role:engineer

### T4.4: Audit log endpoint
**Description:** `GET /audit` with query params: `actor`, `action`, `resource_type`, `from` (ISO timestamp), `to` (ISO timestamp), `cursor`, `limit`. Returns `{"entries": [...], "next_cursor": "..."}`. Requires `admin` scope. Default limit 50, max 200.
**Acceptance Criteria:**
- [ ] All filter params work individually and combined
- [ ] Date range filtering inclusive on both ends
- [ ] Default limit 50, max enforced at 200
- [ ] Requires `admin` scope (403 otherwise)
**Role:** engineer-core-api
**Labels:** mvp, role:engineer

### T4.5: Versioning + audit tests
**Description:** Tests: verify version_number increments on each write, history ordering is descending, audit log captures every mutation (set, delete, key create, key revoke), audit filters work, cursor pagination across large history.
**Acceptance Criteria:**
- [ ] Version sequence verified over 5+ writes
- [ ] History ordering verified
- [ ] Audit log entries match mutations 1:1
- [ ] Filter combinations tested
**Role:** qa-test
**Labels:** mvp, role:qa

---

## E5: Feature Flags

**Objective:** Implement the feature-flag engine with rollout percentage and rule-based evaluation.

### T5.1: Feature flag model
**Description:** Create `feature_flags` table: id (INTEGER PK), name (TEXT NOT NULL UNIQUE), description (TEXT), enabled (BOOLEAN DEFAULT TRUE), rollout_percentage (INTEGER DEFAULT 100, CHECK 0-100), rules_json (TEXT, default "[]"), created_at, updated_at. Index on name.
**Acceptance Criteria:**
- [ ] Model matches ARCHITECTURE.md
- [ ] CHECK constraint on rollout_percentage (0-100)
- [ ] rules_json stored as JSON array of rule objects
**Role:** engineer-flags
**Labels:** mvp, role:engineer

### T5.2: Flag repository + service
**Description:** `FeatureFlagRepository` with get/upsert/delete/list. `FeatureFlagService` wrapping repo with business logic: validate rules_json structure on write (each rule has "field", "operator", and either "value" or "values"), validate rollout_percentage in range.
**Acceptance Criteria:**
- [ ] CRUD operations work for flags
- [ ] Invalid rules_json (missing fields) rejected with 422
- [ ] rollout_percentage clamped/validated to 0-100
- [ ] Upsert creates or updates based on name
**Role:** engineer-flags
**Labels:** mvp, role:engineer

### T5.3: Flag evaluation engine
**Description:** Implement `evaluate_flag(flag, user_id, attributes)`:
1. If not `enabled`, return `False, reason="disabled"`.
2. Check `rules` for `user_id` allowlist (`{"field": "user_id", "operator": "in", "values": [...]}`) — if matched, return `True, reason="allowlist"`.
3. Deterministic bucket: `hashlib.sha256(f"{user_id}:{flag.name}".encode()).hexdigest()` → take first 8 chars as int, mod 100 → if < rollout_percentage, return `True, reason="rollout"`.
4. Check attribute rules (`{"field": "tier", "operator": "eq", "value": "premium"}`) — if any match, return `True, reason="rule_match"`.
5. Default: return `False, reason="default"`.
**Acceptance Criteria:**
- [ ] Deterministic: same user_id + flag always same result
- [ ] 0% rollout → always False (except allowlist)
- [ ] 100% rollout → always True (if enabled)
- [ ] Allowlist takes priority over rollout
- [ ] Attribute rules evaluated after rollout
**Role:** engineer-flags
**Labels:** mvp, role:engineer

### T5.4: Flag router
**Description:** FastAPI router at `/flags` prefix. `PUT /flags/{name}` create/update, `GET /flags/{name}` evaluate (query: `user_id` required, `attributes` optional JSON), `GET /flags` list all, `DELETE /flags/{name}` delete. Evaluation response: `{"flag": "name", "enabled": true, "reason": "rollout"}`.
**Acceptance Criteria:**
- [ ] All endpoints match API.md spec
- [ ] Evaluation requires `user_id` query param
- [ ] List returns definitions (not evaluations)
- [ ] Auth: `flags:read` for GET, `flags:write` for PUT/DELETE
**Role:** engineer-flags
**Labels:** mvp, role:engineer

### T5.5: Flag evaluation tests
**Description:** Comprehensive test suite for flag evaluation: 0% rollout blocks everyone, 100% allows everyone, allowlisted user bypasses 0% rollout, non-allowlisted user at 50% rollout (verify deterministic), attribute eq rule matches, attribute in rule matches, disabled flag returns false, multiple rules (any match = true), edge case: empty user_id.
**Acceptance Criteria:**
- [ ] All edge cases tested
- [ ] Determinism verified (same inputs, same output, 1000 iterations)
- [ ] Rule priority order verified: disabled < allowlist < rollout < attribute
- [ ] 100% coverage of evaluation function
**Role:** qa-test
**Labels:** mvp, role:qa

### T5.6: Flag concurrency tests
**Description:** Test concurrent flag updates (two writers updating rollout % simultaneously), read-after-write consistency (update flag then immediately evaluate), and flag deletion during evaluation.
**Acceptance Criteria:**
- [ ] Concurrent writes don't corrupt data
- [ ] Read-after-write returns updated value
- [ ] Delete during evaluation returns graceful result (not crash)
**Role:** qa-test
**Labels:** mvp, role:qa

---

## E6: Watch / SSE

**Objective:** Provide a real-time streaming API so clients can react to config changes instantly.

### T6.1: Event bus
**Description:** Implement `WatchManager` as a process-level singleton: maintains a dict of `namespace → list[asyncio.Queue]`. Method `subscribe(namespace) → asyncio.Queue` registers a subscriber. Method `publish(event)` pushes to all subscribers for the event's namespace. Event shape: `{"event": "config.changed", "namespace": "...", "key": "...", "version": N, "timestamp": "..."}`. Queue max size 100; drop oldest on overflow.
**Acceptance Criteria:**
- [ ] Subscribers receive events for their namespace only
- [ ] Multiple subscribers on same namespace all get events
- [ ] Queue overflow drops oldest events (not blocks)
- [ ] No memory leak: unsubscribed queues are cleaned up
**Role:** engineer-sdk-watch
**Labels:** mvp, role:engineer

### T6.2: SSE endpoint
**Description:** `GET /watch/{namespace}` — returns `text/event-stream`. Yields SSE events from the watch manager. Includes heartbeat comment (`: ping`) every 30 seconds to keep connections alive. Closes cleanly on client disconnect. Auth: `config:read` scope.
**Acceptance Criteria:**
- [ ] SSE stream delivers config.change events in real-time
- [ ] Heartbeat comment sent every 30s
- [ ] Client disconnect detected and queue cleaned up
- [ ] Multiple concurrent subscribers work
**Role:** engineer-sdk-watch
**Labels:** mvp, role:engineer

### T6.3: Reconnect support
**Description:** Process `Last-Event-ID` header. On reconnect, replay missed events by querying version history since the given version ID. If too many events missed (or ID too old), send a `config.resync` event advising client to do a full fetch.
**Acceptance Criteria:**
- [ ] `Last-Event-ID` header parsed correctly
- [ ] Missed events replayed from history
- [ ] `config.resync` event sent when gap too large
- [ ] Works after server restart (no in-memory state needed for reconnect)
**Role:** engineer-sdk-watch
**Labels:** mvp, role:engineer

### T6.4: Watch integration tests
**Description:** Tests: subscribe and receive an event after a config write, multiple subscribers receive the same event, heartbeat is sent within 35s, disconnect and reconnect with Last-Event-ID replays events, namespace isolation (subscriber on "a" doesn't get events for "b").
**Acceptance Criteria:**
- [ ] Event delivery verified end-to-end
- [ ] Heartbeat timing verified
- [ ] Reconnect replay verified
- [ ] Namespace isolation verified
**Role:** qa-test
**Labels:** mvp, role:qa

---

## E7: Python Client SDK

**Objective:** Ship an idiomatic, type-safe Python client that makes fleet-config trivially easy to adopt.

### T7.1: SDK package structure
**Description:** Create `src/fleet_config/client/` package (separate from server code). Structure: `__init__.py` (exports Client), `client.py` (main Client class), `models.py` (Pydantic response models), `errors.py` (exception hierarchy), `watch.py` (SSE iterator). Include `py.typed` marker file.
**Acceptance Criteria:**
- [ ] Package installs as part of fleet-config (or separate)
- [ ] `from fleet_config import Client` works
- [ ] `py.typed` present for mypy support
- [ ] `__all__` exports clean public API
**Role:** engineer-sdk-watch
**Labels:** mvp, role:engineer

### T7.2: Config client methods
**Description:** Implement `client.config.get(ns, key) → ConfigValue`, `client.config.set(ns, key, value, *, type=None) → ConfigValue`, `client.config.delete(ns, key) → None`, `client.config.list(ns, *, prefix=None, limit=50) → list[ConfigValue]`, `client.config.history(ns, key, *, limit=50) → list[ConfigVersion]`. Typed with Pydantic response models.
**Acceptance Criteria:**
- [ ] All methods hit correct API endpoints
- [ ] Response models parse correctly
- [ ] Type auto-detected from Python value when not specified
- [ ] delete raises NotFoundError on 404
**Role:** engineer-sdk-watch
**Labels:** mvp, role:engineer

### T7.3: Flag client methods
**Description:** Implement `client.flags.create(name, *, description=None, enabled=True, rollout_percentage=100, rules=None) → FeatureFlag`, `client.flags.check(name, *, user_id, attributes=None) → FlagEvaluation`, `client.flags.get(name) → FeatureFlag`, `client.flags.delete(name) → None`, `client.flags.list() → list[FeatureFlag]`.
**Acceptance Criteria:**
- [ ] All methods hit correct API endpoints
- [ ] FlagEvaluation includes enabled + reason
- [ ] check sends user_id and attributes as query params
- [ ] Typed responses with Pydantic models
**Role:** engineer-sdk-watch
**Labels:** mvp, role:engineer

### T7.4: Watch client
**Description:** Implement `client.watch(namespace) → Iterator[WatchEvent]` using httpx SSE support or manual SSE parsing. Auto-reconnect on disconnect using Last-Event-ID. Yield WatchEvent objects. Make it usable as `for event in client.watch("agents"): ...`.
**Acceptance Criteria:**
- [ ] SSE events parsed into WatchEvent objects
- [ ] Auto-reconnect on disconnect with Last-Event-ID
- [ ] Clean shutdown on iterator close / client close
- [ ] Works as a simple for-loop
**Role:** engineer-sdk-watch
**Labels:** mvp, role:engineer

### T7.5: Error handling + retries
**Description:** Implement custom exception hierarchy: `FleetConfigError` (base), `AuthenticationError` (401), `PermissionDeniedError` (403), `NotFoundError` (404), `ValidationError` (422), `ConflictError` (409), `ServerError` (5xx), `ConnectionError`. All have `.status_code`, `.error_code`, `.message`. Retry logic: exponential backoff with jitter on 429/5xx/ConnectionError, max 3 retries.
**Acceptance Criteria:**
- [ ] All HTTP errors mapped to correct exception type
- [ ] Retry on 429, 500, 502, 503, 504
- [ ] No retry on 4xx (except 429)
- [ ] Backoff increases: ~0.5s, ~1s, ~2s
**Role:** engineer-sdk-watch
**Labels:** mvp, role:engineer

### T7.6: SDK tests
**Description:** Mock-based unit tests for all client methods (mock httpx responses). Integration tests against live service (started in test fixture). Verify error handling, retries, watch event parsing.
**Acceptance Criteria:**
- [ ] All public methods tested with mocked responses
- [ ] Error scenarios tested (each exception type)
- [ ] At least 2 integration tests against live service
- [ ] Retry behavior verified with mocked failures
**Role:** qa-test
**Labels:** mvp, role:qa

---

## E8: Deploy & Observability

**Objective:** Make the service one-command deployable and production-ready with CI.

### T8.1: Dockerfile
**Description:** Multi-stage Dockerfile: stage 1 installs deps, stage 2 copies app. Run as non-root user. EXPOSE 8080. Healthcheck `curl -f http://localhost:8080/health || exit 1`. Final image <150MB.
**Acceptance Criteria:**
- [ ] `docker build .` succeeds
- [ ] Container runs as non-root
- [ ] Healthcheck passes
- [ ] Image size <150MB
**Role:** devops-deploy
**Labels:** mvp, role:devops

### T8.2: docker-compose
**Description:** `docker-compose.yml` with `fleet-config` service: build from local Dockerfile, ports 8080:8080, volume mount for SQLite data, env vars (DATABASE_URL, LOG_LEVEL), healthcheck, restart policy.
**Acceptance Criteria:**
- [ ] `docker-compose up -d` starts service
- [ ] Volume persists data across restarts
- [ ] Healthcheck shows healthy in `docker-compose ps`
- [ ] Logs visible via `docker-compose logs`
**Role:** devops-deploy
**Labels:** mvp, role:devops

### T8.3: GitHub Actions CI
**Description:** `.github/workflows/ci.yml` triggered on PR to main. Jobs: lint (ruff check), typecheck (mypy src/), test (pytest with in-memory SQLite), build (docker build). All must pass before merge.
**Acceptance Criteria:**
- [ ] Workflow triggers on PRs to main
- [ ] All four jobs run in parallel
- [ ] Failing lint/typecheck/test/built blocks merge
- [ ] Uses Python 3.12
**Role:** devops-deploy
**Labels:** mvp, role:devops

### T8.4: Structured logging
**Description:** Configure `structlog` for JSON output. Add request-ID middleware that generates a UUID per request and includes it in all log lines. Log level configurable via `LOG_LEVEL` env var (default INFO). Log all requests (method, path, status, duration).
**Acceptance Criteria:**
- [ ] All logs are valid JSON
- [ ] Request ID present in every request log
- [ ] Log level changes take effect without restart
- [ ] Request log includes method, path, status, duration_ms
**Role:** devops-deploy
**Labels:** mvp, role:devops

### T8.5: Smoke test suite
**Description:** End-to-end test script (`tests/smoke_test.sh` or pytest): starts docker-compose, waits for healthy, creates API key, sets config values, reads them, creates flag, evaluates flag, watches for change, stops compose. Exit 0 on success.
**Acceptance Criteria:**
- [ ] Script runs end-to-end against docker-compose
- [ ] All major features exercised (config, flags, watch, auth)
- [ ] Clean teardown on success and failure
- [ ] Can be run locally and in CI
**Role:** qa-test
**Labels:** mvp, role:qa

---

## Summary Table

| Epic | Tasks | Primary Roles | Phase |
|------|-------|---------------|-------|
| E1: Project Scaffolding | 5 | engineer-core-api, devops, qa | 1 |
| E2: Core Config CRUD | 5 | engineer-core-api, qa | 1 |
| E3: Auth & API Keys | 5 | engineer-core-api, qa | 1 |
| E4: Versioning & Audit Log | 5 | engineer-core-api, qa | 1 |
| E5: Feature Flags | 6 | engineer-flags, qa | 2 |
| E6: Watch / SSE | 4 | engineer-sdk-watch, qa | 2 |
| E7: Python Client SDK | 6 | engineer-sdk-watch, qa | 3 |
| E8: Deploy & Observability | 5 | devops, qa | 3 |
| **Total** | **41** | | |
