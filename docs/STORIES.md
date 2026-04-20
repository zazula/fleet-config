# fleet-config — Epic Story Breakdown

This document breaks epics `E1` through `E8` into INVEST-compliant user stories derived from `docs/PRD.md`, `docs/BACKLOG.md`, and `docs/ROADMAP.md`.

## Estimation scale

- `1` — tiny change, low risk
- `2` — small change
- `3` — moderate change
- `5` — larger change with coordination or edge cases
- `8` — complex story with notable technical risk

---

## E1 — Scaffolding

### E1-US-01 — Bootstrap the Python service project
- **As a** core API engineer
- **I want** a working Python project layout with dependencies and quality tooling configured
- **So that** the team can build features on a consistent and installable codebase
- **Acceptance Criteria**
  - `pyproject.toml` defines runtime and development dependencies required by the MVP
  - The `src/fleet_config/` package structure exists and is importable
  - Linting and type-checking configuration is committed and executable locally
  - A developer can run the editable install successfully using the documented command
- **Points**: 3

### E1-US-02 — Run a minimal FastAPI app with health check
- **As a** fleet operator
- **I want** the service to expose a health endpoint and startup configuration
- **So that** I can confirm the service is alive before using it
- **Acceptance Criteria**
  - The app exposes `GET /health`
  - `GET /health` returns HTTP 200 with service status and version information
  - Environment-backed settings load with sensible defaults for local development
  - The service starts successfully via the documented ASGI entrypoint
- **Points**: 3

### E1-US-03 — Initialize the database on startup
- **As a** core API engineer
- **I want** the service to create and connect to its database automatically in development
- **So that** local setup is fast and reliable
- **Acceptance Criteria**
  - The service creates an async database engine and session factory from configuration
  - Startup initialization creates tables when they do not yet exist
  - SQLite development mode enables WAL mode
  - Database sessions are available through FastAPI dependency injection
- **Points**: 3

### E1-US-04 — Standardize local developer workflows
- **As a** developer on the project
- **I want** repeatable lint, format, type-check, and test commands
- **So that** contributors can validate changes consistently before review
- **Acceptance Criteria**
  - Pre-commit hooks are configured for the agreed checks
  - A `Makefile` or equivalent task runner exposes lint, format, type-check, and test commands
  - The documented commands run against the repo without requiring undocumented setup
  - The contributor workflow is documented in the project README or equivalent docs
- **Points**: 2

### E1-US-05 — Provide a reusable automated test harness
- **As a** QA engineer
- **I want** test fixtures for the app, database, and HTTP client
- **So that** feature teams can add reliable automated tests quickly
- **Acceptance Criteria**
  - `pytest` runs a smoke test for `GET /health`
  - Test fixtures provide an isolated database per test run
  - Test fixtures expose reusable app and HTTP client objects to test modules
  - The default test run succeeds in a fresh development environment
- **Points**: 3

---

## E2 — Core Config CRUD

### E2-US-01 — Create and update config values
- **As a** fleet operator
- **I want** to create or update a config value by namespace and key
- **So that** fleet configuration is centralized and current
- **Acceptance Criteria**
  - The write API accepts namespace, key, value, and value type
  - Creating a new key stores it durably and returns the stored record metadata
  - Updating an existing key replaces the current value and updates metadata
  - Invalid payloads are rejected with a descriptive validation error
- **Points**: 5

### E2-US-02 — Read a config value by namespace and key
- **As a** fleet operator or runtime agent
- **I want** to retrieve the latest value for a specific config key
- **So that** scripts and services can use the current configuration
- **Acceptance Criteria**
  - The read API returns the latest stored value and metadata for an existing key
  - A missing namespace/key combination returns HTTP 404 with a descriptive message
  - The response shape is consistent for both operator and service consumers
  - Reads do not mutate stored state
- **Points**: 2

### E2-US-03 — List config keys within a namespace
- **As a** fleet operator
- **I want** to browse config keys in a namespace with pagination and prefix filtering
- **So that** I can audit and navigate configuration safely at scale
- **Acceptance Criteria**
  - The list API returns keys for a namespace in a stable order
  - The list API supports cursor-based pagination with a caller-provided page size limit
  - The list API supports optional prefix filtering
  - An empty namespace returns HTTP 200 with an empty list
- **Points**: 3

### E2-US-04 — Delete a config key safely
- **As a** fleet operator
- **I want** to delete an obsolete config key
- **So that** stale configuration does not remain discoverable as active state
- **Acceptance Criteria**
  - The delete API removes the key from active reads
  - Deleting an existing key returns a success response with no ambiguity
  - Deleting a missing key returns a descriptive not-found response
  - Deletion behavior is covered by automated integration tests
- **Points**: 3

### E2-US-05 — Enforce config schema and payload constraints
- **As a** fleet operator
- **I want** config writes to validate supported value types and size limits
- **So that** malformed or dangerous payloads do not enter the system
- **Acceptance Criteria**
  - Supported value types are validated before persistence
  - Values larger than the documented maximum are rejected
  - Validation failures return machine-readable error details
  - Successful writes persist normalized values consistently
- **Points**: 3

---

## E3 — Auth & API Keys

### E3-US-01 — Issue scoped API keys
- **As a** fleet operator
- **I want** to create API keys with explicit scope and namespace access
- **So that** human and machine clients receive only the permissions they need
- **Acceptance Criteria**
  - An authenticated operator can create an API key with read and/or write scopes
  - A key can be restricted to one or more namespaces
  - The plaintext key is shown only at creation time
  - Stored key material is not persisted in plaintext
- **Points**: 5

### E3-US-02 — Rotate an API key without losing access control
- **As a** fleet operator
- **I want** to rotate a compromised or expiring API key
- **So that** I can preserve security without manual reconfiguration of permissions
- **Acceptance Criteria**
  - Rotating a key creates a new credential with the same effective scope unless explicitly changed
  - The old key is no longer accepted after rotation completes
  - Rotation events are attributable to an actor and timestamp
  - The newly issued key is returned once at rotation time
- **Points**: 3

### E3-US-03 — Revoke an API key
- **As a** fleet operator
- **I want** to revoke an API key
- **So that** lost, leaked, or deprecated credentials stop working immediately
- **Acceptance Criteria**
  - A revoked key is rejected on subsequent requests
  - Revocation does not delete historical attribution tied to the key
  - Revoking an already revoked key is idempotent
  - Revocation is exposed through the management API
- **Points**: 2

### E3-US-04 — Enforce authentication and authorization on API requests
- **As a** service owner
- **I want** every API request to be checked for valid credentials and permissions
- **So that** reads and writes are protected by least privilege
- **Acceptance Criteria**
  - Requests with missing credentials are rejected
  - Requests with invalid or expired credentials are rejected
  - Requests outside the key’s scope or namespace permissions return forbidden
  - Authorized requests reach the target endpoint without additional manual checks
- **Points**: 5

### E3-US-05 — Manage API keys through an operator API
- **As a** fleet operator
- **I want** to list and inspect issued API keys without exposing secrets
- **So that** I can audit active access and clean up stale credentials
- **Acceptance Criteria**
  - The management API lists issued keys with metadata, scopes, status, and safe identifiers
  - Secret values are never returned for previously created keys
  - Results can be filtered by status or namespace when requested
  - Key management endpoints are covered by integration tests
- **Points**: 3

---

## E4 — Versioning & Audit Log

### E4-US-01 — Record a new version for every config write
- **As a** fleet operator
- **I want** each config write to create a distinct immutable version
- **So that** I can trace how values changed over time
- **Acceptance Criteria**
  - Every successful config write creates a new version record
  - Version numbers increase monotonically per key
  - The current config record references the latest version
  - Version creation occurs atomically with the write
- **Points**: 5

### E4-US-02 — View version history for a config key
- **As a** fleet operator
- **I want** to retrieve the full history of a config key
- **So that** I can investigate prior states and change timing
- **Acceptance Criteria**
  - The history API returns all recorded versions for a key in chronological or clearly documented order
  - Each history entry includes version number, value snapshot, actor, and timestamp
  - A missing key returns a descriptive not-found response
  - History entries cannot be edited or deleted through the API
- **Points**: 3

### E4-US-03 — Roll back a config key to a previous version
- **As a** fleet operator
- **I want** to restore a prior version of a config key
- **So that** I can recover quickly from a bad change
- **Acceptance Criteria**
  - The rollback API accepts a target version identifier for an existing key
  - Rolling back creates a new current version using the selected prior value
  - Rolling back to the current version behaves as a no-op success
  - The response returns the new effective version metadata
- **Points**: 5

### E4-US-04 — Capture an auditable event trail for config changes
- **As a** fleet operator
- **I want** writes, deletes, and rollbacks recorded in an audit log
- **So that** I can understand who changed what and when
- **Acceptance Criteria**
  - Audit events are recorded for create, update, delete, and rollback actions
  - Each event includes actor, action type, namespace, key, timestamp, and relevant version references
  - Audit records are append-only
  - Audit logging does not expose sensitive credential material
- **Points**: 3

### E4-US-05 — Query the audit log efficiently
- **As a** fleet operator
- **I want** to filter audit entries by namespace, key, actor, and time window
- **So that** incident review and compliance checks are practical
- **Acceptance Criteria**
  - The audit API supports filtering by namespace, key, actor, and time range
  - Results are paginated for large histories
  - Returned entries are ordered predictably for investigation workflows
  - Filtering behavior is verified by automated tests
- **Points**: 3

---

## E5 — Feature Flags

### E5-US-01 — Create and maintain feature flag definitions
- **As a** fleet operator
- **I want** to create, update, and archive feature flags
- **So that** rollout controls are managed centrally instead of in code constants
- **Acceptance Criteria**
  - The flag API supports create, read, update, list, and archive operations
  - A flag definition stores its type, default behavior, and targeting rules
  - Archived flags are excluded from active evaluation unless explicitly requested
  - Invalid flag definitions are rejected with descriptive validation errors
- **Points**: 5

### E5-US-02 — Evaluate boolean flags for a runtime context
- **As a** runtime agent
- **I want** to evaluate a boolean feature flag for a user or request context
- **So that** application behavior can change without redeploying code
- **Acceptance Criteria**
  - The evaluation API accepts a flag key and context attributes such as user identifier
  - The response returns a boolean decision and the rule or default source used
  - Missing flags return a descriptive not-found response or documented fallback behavior
  - Boolean evaluation is covered by automated tests for default-on and default-off cases
- **Points**: 5

### E5-US-03 — Evaluate multivariate flags deterministically
- **As a** product service
- **I want** to evaluate variant flags for a runtime context
- **So that** I can support experiments and segmented experiences
- **Acceptance Criteria**
  - The evaluation engine returns one configured variant for a valid multivariate flag
  - The same user context yields the same variant for the same flag and configuration
  - Invalid variant configurations are rejected before activation
  - Variant evaluation behavior is covered by automated tests
- **Points**: 5

### E5-US-04 — Support percentage rollouts and segment targeting
- **As a** fleet operator
- **I want** rollout rules based on user percentage and attributes
- **So that** I can gradually enable changes for specific cohorts
- **Acceptance Criteria**
  - Targeting rules support percentage rollout using a deterministic hash strategy
  - Targeting rules support matching documented context attributes or segments
  - Rule precedence is documented and applied consistently
  - Evaluation tests cover mixed rule combinations and edge cases
- **Points**: 8

### E5-US-05 — Keep flag evaluations safe under concurrent access
- **As a** platform engineer
- **I want** flag reads and updates to behave correctly under concurrent load
- **So that** rollout decisions remain trustworthy during production traffic
- **Acceptance Criteria**
  - Concurrent reads and writes do not return malformed or partial flag data
  - Deterministic rollout behavior remains stable under repeated concurrent evaluations
  - The implementation is covered by concurrency-focused automated tests
  - Documented performance expectations are met for the MVP release criteria
- **Points**: 5

---

## E6 — Watch / SSE

### E6-US-01 — Subscribe to real-time config change events
- **As a** runtime agent
- **I want** to open an SSE stream for namespace changes
- **So that** I can react to config updates without restarting
- **Acceptance Criteria**
  - The watch API exposes an SSE endpoint for subscribing to change events
  - The stream emits events for relevant config and flag changes in the subscribed scope
  - Event payloads include enough metadata to identify the changed resource and version
  - Unauthorized watch requests are rejected before the stream opens
- **Points**: 5

### E6-US-02 — Replay missed events after reconnect
- **As a** runtime agent
- **I want** to resume a watch stream from my last event identifier
- **So that** brief disconnects do not cause config drift
- **Acceptance Criteria**
  - The SSE endpoint accepts `Last-Event-ID` or equivalent resume information
  - The service replays missed events still within the supported replay window
  - If replay is no longer possible, the service responds with a documented recovery path
  - Reconnect behavior is covered by automated integration tests
- **Points**: 5

### E6-US-03 — Bound watch service behavior under load
- **As a** platform engineer
- **I want** watcher limits and backpressure behavior enforced
- **So that** watch traffic does not degrade service stability
- **Acceptance Criteria**
  - The service enforces the documented maximum concurrent watcher limit
  - Requests above the limit receive a retryable response with backoff guidance
  - Idle or disconnected clients are cleaned up without leaking resources
  - Watcher count and cleanup behavior are verified by automated tests
- **Points**: 5

### E6-US-04 — Publish change events from write operations
- **As a** runtime agent
- **I want** config and flag writes to emit watch events automatically
- **So that** subscribers receive a consistent stream of state changes
- **Acceptance Criteria**
  - Successful create, update, delete, rollback, and flag changes publish watch events
  - Event ordering is consistent per resource stream
  - Failed writes do not emit misleading success events
  - End-to-end tests verify publication from write API to SSE subscriber
- **Points**: 3

---

## E7 — Python Client SDK

### E7-US-01 — Install and initialize a typed Python client
- **As a** Python service developer
- **I want** an installable SDK with a typed client and configuration options
- **So that** my service can adopt fleet-config with minimal custom plumbing
- **Acceptance Criteria**
  - The `fleetconfig` package is installable from the project’s distribution workflow
  - The SDK exposes a typed `Client` entrypoint
  - The client can be configured with base URL, credentials, and timeouts
  - Basic usage is documented for local development and CI usage
- **Points**: 3

### E7-US-02 — Read and write config values through the SDK
- **As a** Python service developer
- **I want** SDK methods for config CRUD operations
- **So that** my application can manage configuration without hand-coding HTTP calls
- **Acceptance Criteria**
  - The SDK exposes methods for get, set, delete, and list config operations
  - Method inputs and outputs are typed with documented models
  - HTTP errors are translated into SDK exceptions rather than leaked raw responses
  - Config client methods are covered by unit tests
- **Points**: 5

### E7-US-03 — Evaluate feature flags through the SDK
- **As a** Python service developer
- **I want** helper methods for boolean and multivariate flag evaluation
- **So that** application code can consume rollout decisions cleanly
- **Acceptance Criteria**
  - The SDK exposes methods for boolean and variant flag evaluation
  - Evaluation methods accept a typed context model or documented mapping
  - Evaluation results include the resolved value and useful metadata when available
  - Flag client methods are covered by unit tests
- **Points**: 5

### E7-US-04 — Consume watch events through the SDK
- **As a** Python service developer
- **I want** an SDK watch iterator with reconnect support
- **So that** my service can subscribe to changes using a simple Python interface
- **Acceptance Criteria**
  - The SDK exposes a watch interface that yields typed watch events
  - The watch interface reconnects automatically using the last received event identifier
  - The watch stream shuts down cleanly when the client closes or iteration stops
  - Watch client behavior is covered by unit or integration tests
- **Points**: 5

### E7-US-05 — Handle transient failures with retries and typed exceptions
- **As a** Python service developer
- **I want** retry behavior and a clear exception hierarchy in the SDK
- **So that** client applications can recover gracefully and handle errors consistently
- **Acceptance Criteria**
  - The SDK maps HTTP error classes to documented exception types
  - Retries occur for retryable failures only, with bounded exponential backoff
  - Non-retryable client errors are surfaced immediately
  - Retry and exception behavior are validated by automated tests
- **Points**: 3

### E7-US-06 — Verify the SDK against a live service
- **As a** release engineer
- **I want** automated SDK tests against a running fleet-config instance
- **So that** package releases prove compatibility with real service behavior
- **Acceptance Criteria**
  - The SDK test suite includes integration coverage against a live service fixture
  - Integration tests cover config methods, flag evaluation, and watch behavior
  - The SDK passes linting, type-checking, and automated tests in CI
  - Release documentation identifies the package versioning expectations
- **Points**: 5

---

## E8 — Deploy & Observability

### E8-US-01 — Build a production-ready container image
- **As a** platform engineer
- **I want** a secure, runnable container image for the service
- **So that** deployments are consistent across environments
- **Acceptance Criteria**
  - The project provides a Dockerfile that builds successfully
  - The runtime container runs as a non-root user
  - The image exposes the documented service port and health check
  - The resulting image meets the documented size or optimization target
- **Points**: 3

### E8-US-02 — Start the service stack with one compose command
- **As a** fleet operator
- **I want** a working `docker-compose` setup for local and production-like environments
- **So that** I can bring up the service quickly with persistent data and health checks
- **Acceptance Criteria**
  - `docker-compose up` starts the service successfully with documented environment variables
  - Persistent storage survives a restart in the compose setup
  - Compose health status reflects the service health endpoint accurately
  - Logs are accessible through the compose workflow
- **Points**: 3

### E8-US-03 — Enforce CI checks on pull requests
- **As a** maintainer
- **I want** pull requests to run lint, type-check, test, and build jobs automatically
- **So that** regressions are caught before merge
- **Acceptance Criteria**
  - A CI workflow triggers on pull requests to the main branch
  - Lint, type-check, test, and build jobs all execute automatically
  - A failing required job blocks merge under the repository policy
  - The workflow uses the project’s supported Python version
- **Points**: 3

### E8-US-04 — Emit structured logs with request correlation
- **As a** fleet operator
- **I want** structured JSON logs with per-request correlation identifiers
- **So that** I can troubleshoot production behavior efficiently
- **Acceptance Criteria**
  - Application logs are emitted as valid JSON
  - Each request log includes a request identifier, method, path, status, and duration
  - The effective log level is configurable through service settings
  - Logging output does not leak secret values
- **Points**: 3

### E8-US-05 — Publish basic operational dashboards and smoke tests
- **As a** fleet operator
- **I want** a smoke test and starter observability artifacts
- **So that** I can verify deployments and inspect service health quickly
- **Acceptance Criteria**
  - A smoke test exercises the major supported workflows against the deployed stack
  - The smoke test performs clean setup and teardown on success and failure
  - A starter dashboard artifact is committed for the documented observability stack
  - The deployment workflow documents how to run the smoke test after startup
- **Points**: 5
