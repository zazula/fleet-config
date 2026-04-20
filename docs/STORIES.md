# fleet-config — User Stories

This document breaks epics `E1`–`E8` into INVEST-compliant user stories derived from `docs/PRD.md`, `docs/BACKLOG.md`, and `docs/ROADMAP.md`.

## E1 — Project Scaffolding

### E1-S1 — Initialize the Python service foundation
**As a** backend engineer  
**I want to** start from a standard Python project layout with pinned dependencies and package structure  
**So that** the team can build features on a consistent, reproducible foundation  

**Acceptance Criteria:**
- `pyproject.toml` defines the runtime and development dependencies needed for the MVP
- The `src/fleet_config/` package structure exists and imports cleanly
- Linting and type-check configuration is present and executable from the repository root
- A fresh developer environment can install the project in editable mode successfully

**Points Estimate:** 3

### E1-S2 — Run a health-checked API application
**As a** backend engineer  
**I want to** boot a FastAPI application with environment-based settings and a health endpoint  
**So that** developers and automation can confirm the service is alive before deeper features are added  

**Acceptance Criteria:**
- The application exposes `GET /health` and returns HTTP `200` with service status and version
- Runtime settings load from environment variables with documented defaults
- The application starts through the supported ASGI entrypoint without manual code changes
- Application logs are emitted in structured JSON format

**Points Estimate:** 3

### E1-S3 — Initialize persistent storage on startup
**As a** backend engineer  
**I want to** create the async database engine, sessions, and startup initialization flow  
**So that** the service can persist state reliably in local and containerized environments  

**Acceptance Criteria:**
- The service creates required tables on first startup in SQLite development mode
- Database sessions are available through FastAPI dependency injection
- SQLite startup enables WAL mode for safer concurrent access in the MVP
- The database connection URL is configurable via environment variable

**Points Estimate:** 5

### E1-S4 — Enforce local developer quality checks
**As a** maintainer  
**I want to** run standard lint, type-check, format, and test commands locally  
**So that** contributors can catch quality issues before opening a pull request  

**Acceptance Criteria:**
- Pre-commit configuration includes the agreed repository checks
- A documented command surface exists for linting, formatting, type-checking, and tests
- Running the local quality commands completes successfully on a clean checkout
- The repository documentation explains how contributors use these commands

**Points Estimate:** 2

### E1-S5 — Provide an async test harness
**As a** QA engineer  
**I want to** run isolated API tests against an in-memory database and reusable fixtures  
**So that** new stories can add automated coverage quickly and safely  

**Acceptance Criteria:**
- Test fixtures provide an application instance, HTTP client, and isolated database session
- The test database is recreated or isolated between test runs
- A smoke test verifies the health endpoint end to end
- The async test runner works from the repository root with the documented test command

**Points Estimate:** 3

## E2 — Core Config CRUD

### E2-S1 — Define the configuration data model
**As a** backend engineer  
**I want to** store current config values and version records with the right constraints  
**So that** config entries remain unique, queryable, and ready for auditing  

**Acceptance Criteria:**
- The schema stores current config values and historical versions as separate related records
- Namespace and key combinations are unique within current config storage
- The schema includes indexes needed for namespace-based listing
- Foreign-key relationships preserve referential integrity between current values and versions

**Points Estimate:** 3

### E2-S2 — Persist configuration through a repository layer
**As a** backend engineer  
**I want to** create and query config keys through an async repository abstraction  
**So that** API handlers and services can reuse consistent persistence logic  

**Acceptance Criteria:**
- The repository supports get, set, delete, and namespace listing operations
- Writing a key creates the record when absent and updates it when present
- Namespace listing supports prefix filtering and cursor-based pagination
- Missing keys return a clear not-found result to callers

**Points Estimate:** 5

### E2-S3 — Validate config payloads and business rules
**As a** fleet operator  
**I want to** submit only supported config values and namespace/key shapes  
**So that** invalid data is rejected before it can affect runtime consumers  

**Acceptance Criteria:**
- The API accepts only supported JSON-compatible value types
- Namespace and key inputs are validated against the agreed naming rules
- Oversized config payloads are rejected with an appropriate client error
- Validation failures return actionable error details without persisting data

**Points Estimate:** 3

### E2-S4 — Manage config values through HTTP endpoints
**As a** fleet operator  
**I want to** create, read, list, and delete config keys over the API  
**So that** I can centralize fleet configuration without editing source code or scattered files  

**Acceptance Criteria:**
- The API exposes endpoints for create/update, read, list, and delete operations on namespaced config keys
- Read responses include the current value and metadata needed by clients
- Namespace listing returns paginated results and does not fail for an empty namespace
- Missing resources and malformed requests return the documented HTTP status codes

**Points Estimate:** 5

### E2-S5 — Verify CRUD behavior end to end
**As a** QA engineer  
**I want to** cover the config API with automated tests for success and failure cases  
**So that** the MVP gate can rely on repeatable evidence of correct behavior  

**Acceptance Criteria:**
- Automated tests cover create, read, list, update, and delete flows
- Tests verify validation errors, missing-key handling, and pagination behavior
- Tests confirm persisted writes are visible in subsequent reads
- The CRUD suite runs as part of the standard automated test command

**Points Estimate:** 3

## E3 — Auth & API Keys

### E3-S1 — Store API keys securely with scopes and lifecycle metadata
**As a** security-conscious maintainer  
**I want to** persist API keys as hashed credentials with scope and expiry information  
**So that** the system can authorize clients without storing raw secrets  

**Acceptance Criteria:**
- The data model stores only hashed API key material plus identifying metadata
- Stored records include scopes, optional namespace restrictions, status, and expiry details
- Key lookup can identify a candidate credential without exposing the full secret
- The schema supports revocation and rotation workflows without destructive history loss

**Points Estimate:** 5

### E3-S2 — Issue and rotate scoped API keys
**As a** fleet operator  
**I want to** create and rotate API keys for people and automation  
**So that** access can be granted and renewed without redeploying services  

**Acceptance Criteria:**
- The service can issue a new API key and return the plaintext secret exactly once
- Issued keys are associated with explicit scopes and optional namespace restrictions
- Rotation replaces the active credential while preserving an audit-friendly record of the previous key
- Expired or revoked keys are no longer accepted for authenticated operations

**Points Estimate:** 5

### E3-S3 — Protect endpoints with authentication and authorization middleware
**As a** platform owner  
**I want to** enforce API key authentication and scope checks on protected endpoints  
**So that** readers and writers only perform actions they are allowed to perform  

**Acceptance Criteria:**
- Protected endpoints reject missing, invalid, expired, or revoked API keys
- Scope checks distinguish read, write, flags, and admin capabilities according to the route
- Namespace restrictions are enforced for keys that are not globally scoped
- The health endpoint remains accessible without authentication

**Points Estimate:** 5

### E3-S4 — Manage credentials through admin API endpoints
**As a** fleet operator  
**I want to** create, list, rotate, and revoke API keys through the API  
**So that** I can administer access for users, agents, and CI/CD pipelines centrally  

**Acceptance Criteria:**
- Admin endpoints exist for key issuance, listing, rotation, and revocation
- List responses expose safe identifying metadata rather than raw secrets
- Administrative actions require the appropriate privileged scope
- API responses clearly distinguish active, expired, and revoked credentials

**Points Estimate:** 3

### E3-S5 — Validate the auth lifecycle with tests
**As a** QA engineer  
**I want to** automate coverage for authentication, authorization, and key lifecycle scenarios  
**So that** access-control regressions are caught before release  

**Acceptance Criteria:**
- Tests cover issuance, successful authentication, rotation, revocation, and expiry handling
- Tests verify scope enforcement for protected routes
- Tests confirm namespace-restricted keys cannot access disallowed resources
- Tests confirm unauthenticated access is still allowed only for the health endpoint

**Points Estimate:** 3

## E4 — Versioning & Audit Log

### E4-S1 — Record immutable audit events for configuration activity
**As a** compliance-minded operator  
**I want to** persist structured audit events for sensitive actions  
**So that** I can trace who changed what and when across the fleet  

**Acceptance Criteria:**
- The audit log stores actor, action, resource identity, event details, and timestamp
- The schema supports filtering by actor, action, and resource identity efficiently
- Audit detail fields can store structured metadata for different event types
- Audit entries are append-only and cannot be silently rewritten by normal workflows

**Points Estimate:** 3

### E4-S2 — Create a new version record on every config mutation
**As a** fleet operator  
**I want to** keep an immutable version history whenever a config value changes  
**So that** I can inspect prior states and recover safely from bad writes  

**Acceptance Criteria:**
- Every config write creates a new sequential version for the affected key
- Delete and rollback-related mutations also emit audit events with relevant context
- Version history can be requested in reverse chronological order with pagination
- Version numbering is per key and remains consistent across repeated writes

**Points Estimate:** 5

### E4-S3 — Browse config history through the API
**As a** fleet operator  
**I want to** request the version history of a config key  
**So that** I can investigate incidents and understand how a value evolved over time  

**Acceptance Criteria:**
- A history endpoint returns version records with value snapshot, actor, and timestamp metadata
- Results are ordered newest first and support cursor-based pagination
- Requests for keys with no history return a documented not-found response
- Access to history requires the appropriate read permission

**Points Estimate:** 3

### E4-S4 — Query the audit trail through the API
**As a** fleet operator  
**I want to** filter audit events by actor, action, resource, and time range  
**So that** I can answer operational and compliance questions without querying the database directly  

**Acceptance Criteria:**
- The audit API supports filtering by actor, action, resource type, resource identity, and time window
- Responses enforce sensible default and maximum page sizes
- Combined filters work together predictably in a single request
- Access to the audit log requires an admin-capable scope

**Points Estimate:** 3

### E4-S5 — Roll back a key to a previous version safely
**As a** fleet operator  
**I want to** restore a prior version of a config key as a new current version  
**So that** I can recover from bad changes without manually reconstructing old values  

**Acceptance Criteria:**
- A rollback request targets a previous version and writes that value as a new current version
- Rollback operations are captured in the audit trail with the source version referenced
- Rolling back to the current version completes successfully without creating duplicate history
- The response includes the resulting current version information after rollback

**Points Estimate:** 5

## E5 — Feature Flags

### E5-S1 — Store feature flag definitions with rollout metadata
**As a** product operator  
**I want to** persist feature flags with enablement state, rollout percentage, and targeting rules  
**So that** I can control gradual releases without shipping code changes  

**Acceptance Criteria:**
- The feature flag schema stores unique flag names, rollout percentage, and rule definitions
- Rollout percentages are constrained to valid values between `0` and `100`
- Rule definitions are stored in a structured format suitable for evaluation
- Flag records include timestamps needed for audit and operational use

**Points Estimate:** 3

### E5-S2 — Manage flag definitions through a validated service layer
**As a** product operator  
**I want to** create, update, list, and delete flags with rule validation  
**So that** invalid targeting definitions are rejected before they affect users  

**Acceptance Criteria:**
- The service supports CRUD operations for feature flags by name
- Invalid rule structures are rejected with validation feedback
- Invalid rollout percentages are rejected before persistence
- Upsert behavior updates an existing flag or creates it when absent

**Points Estimate:** 5

### E5-S3 — Evaluate flags deterministically for a user context
**As a** runtime agent process  
**I want to** evaluate a flag for a user and attributes deterministically  
**So that** every service can make the same rollout decision for the same input  

**Acceptance Criteria:**
- Disabled flags evaluate to disabled regardless of rollout or targeting rules
- Allowlist-style targeting can enable a user even when rollout percentage is `0`
- Percentage rollouts produce deterministic results for the same flag name and user ID
- Attribute-based rules are evaluated according to the documented priority order

**Points Estimate:** 5

### E5-S4 — Access flag management and evaluation over HTTP
**As a** fleet operator or agent process  
**I want to** manage flag definitions and request evaluations through the API  
**So that** CI pipelines and runtime clients can use feature flags programmatically  

**Acceptance Criteria:**
- The API exposes endpoints to create/update, list, delete, and evaluate feature flags
- Evaluation requests require a user identifier and return both the decision and reason
- Read and write permissions are enforced separately for flag routes
- Listing returns flag definitions rather than evaluation responses

**Points Estimate:** 3

### E5-S5 — Prove flag behavior under edge cases and concurrency
**As a** QA engineer  
**I want to** automate flag evaluation and update scenarios  
**So that** rollout logic remains trustworthy under real operating conditions  

**Acceptance Criteria:**
- Tests cover disabled flags, `0%` rollout, `100%` rollout, allowlists, and attribute rules
- Tests verify deterministic outcomes for repeated evaluations with the same inputs
- Concurrent updates do not corrupt stored flag state
- Read-after-write and delete-during-evaluation scenarios fail gracefully without crashes

**Points Estimate:** 5

## E6 — Watch / SSE

### E6-S1 — Publish config change events to namespace subscribers
**As a** runtime agent process  
**I want to** subscribe to config change events for a namespace  
**So that** I can react to updates without polling the API continuously  

**Acceptance Criteria:**
- The watch manager routes events only to subscribers of the affected namespace
- Multiple subscribers to the same namespace each receive published events
- Subscriber queues handle overflow without blocking writers indefinitely
- Unsubscribed or disconnected consumers are cleaned up from in-memory tracking

**Points Estimate:** 5

### E6-S2 — Stream config events over Server-Sent Events
**As a** runtime agent process  
**I want to** receive namespace updates through an SSE endpoint  
**So that** long-running services can stay in sync with centralized configuration in near real time  

**Acceptance Criteria:**
- The watch endpoint returns a compliant `text/event-stream` response for authorized readers
- Config change events are emitted as they occur for the subscribed namespace
- Heartbeat comments are sent on a regular interval to keep idle connections alive
- Client disconnects are detected and cleaned up cleanly by the server

**Points Estimate:** 5

### E6-S3 — Resume missed events after reconnect
**As a** runtime agent process  
**I want to** reconnect with a last-seen event identifier and replay missed changes  
**So that** transient disconnects do not force a full config reload every time  

**Acceptance Criteria:**
- The watch endpoint accepts `Last-Event-ID` and interprets it consistently
- Reconnects replay missed events from persisted history when they are still available
- The service emits a resync signal when the replay window cannot satisfy the gap
- Replay behavior works after process restart without relying on stale in-memory state

**Points Estimate:** 5

### E6-S4 — Validate watch behavior end to end
**As a** QA engineer  
**I want to** run integration tests for subscribe, heartbeat, isolation, and reconnect flows  
**So that** the real-time delivery path is safe to depend on in production  

**Acceptance Criteria:**
- Tests verify an update is delivered to a live subscriber after a config write
- Tests verify namespace isolation across independent subscribers
- Tests verify a heartbeat arrives within the documented interval budget
- Tests verify disconnect-and-reconnect flows replay or resync as expected

**Points Estimate:** 3

## E7 — Python Client SDK

### E7-S1 — Publish a typed Python SDK surface
**As a** Python service developer  
**I want to** install a typed `fleetconfig` client package with a clear public API  
**So that** product services can adopt fleet-config without hand-writing HTTP calls  

**Acceptance Criteria:**
- The SDK package exposes a documented `Client` entry point and typed models for core responses
- The package structure cleanly separates client-side code from server implementation details
- Type checking passes under strict settings for the published SDK surface
- Packaging metadata supports building and distributing the SDK as a versioned artifact

**Points Estimate:** 3

### E7-S2 — Read and write config through the SDK client
**As a** Python service developer  
**I want to** call simple client methods for config CRUD operations  
**So that** my code can consume centralized configuration with minimal boilerplate  

**Acceptance Criteria:**
- The client supports context-managed lifecycle for opening and closing HTTP resources
- Methods exist for get, set, delete, and list config operations with typed return values
- Authentication headers are handled automatically by the client
- Client method signatures align with the supported server API behavior

**Points Estimate:** 5

### E7-S3 — Evaluate flags and read definitions through the SDK
**As a** Python service developer  
**I want to** manage and evaluate feature flags through SDK helpers  
**So that** application code can use rollout decisions without duplicating protocol logic  

**Acceptance Criteria:**
- The SDK provides methods for listing, creating/updating, deleting, and evaluating flags
- Evaluation helpers accept user identifiers and optional attributes cleanly
- Typed responses expose both decision outcomes and explanatory metadata
- SDK flag helpers remain compatible with the server’s authenticated route model

**Points Estimate:** 5

### E7-S4 — Consume watch streams through the SDK
**As a** Python service developer  
**I want to** iterate over config watch events from the SDK  
**So that** my service can respond to changes using familiar Python control flow  

**Acceptance Criteria:**
- The SDK exposes a watch interface that yields typed watch events
- The watch client parses SSE frames correctly and supports clean shutdown
- Disconnects trigger automatic reconnect with the last seen event identifier
- The watch interface is usable in straightforward iterator-based application code

**Points Estimate:** 5

### E7-S5 — Handle service errors and retries consistently in the SDK
**As a** Python service developer  
**I want to** receive typed exceptions and sensible transient-failure retries  
**So that** callers can recover from network and server issues predictably  

**Acceptance Criteria:**
- HTTP failures map to a documented exception hierarchy with status and message details
- Retry behavior applies only to retryable conditions such as `429`, selected `5xx`, and connection failures
- Backoff timing increases across retry attempts and caps at the documented limit
- Non-retryable client errors surface immediately without hidden retries

**Points Estimate:** 5

### E7-S6 — Prove SDK behavior with unit and integration tests
**As a** QA engineer  
**I want to** validate SDK methods against mocked responses and a live service  
**So that** published client releases are trustworthy for downstream teams  

**Acceptance Criteria:**
- Unit tests cover all public SDK methods with mocked HTTP behavior
- Error mapping tests cover each custom exception type
- Retry tests verify the expected retry policy and backoff progression
- Integration tests validate the SDK against a running fleet-config service for representative flows

**Points Estimate:** 3

## E8 — Deploy & Observability

### E8-S1 — Build a production-ready container image
**As a** platform engineer  
**I want to** package the service as a secure, lightweight Docker image  
**So that** environments can run a consistent artifact with minimal setup  

**Acceptance Criteria:**
- The repository includes a reproducible Docker build for the service
- The final container runs as a non-root user
- The container exposes the service port and passes the configured health check
- The produced image meets the documented size target for the MVP

**Points Estimate:** 3

### E8-S2 — Start the full service stack with docker compose
**As a** fleet operator  
**I want to** launch fleet-config with one compose command  
**So that** local environments and simple deployments can stand up the service quickly  

**Acceptance Criteria:**
- A compose definition starts the service with the required environment and persistent data volume
- The compose stack reports the service as healthy after startup
- Restart behavior is configured for basic resilience in long-running environments
- Service logs remain accessible through standard compose tooling

**Points Estimate:** 3

### E8-S3 — Enforce CI checks on pull requests
**As a** maintainer  
**I want to** run lint, type-check, test, and container build jobs in CI  
**So that** changes cannot merge to `main` unless the release gates remain green  

**Acceptance Criteria:**
- A pull request workflow runs the required quality and build jobs automatically
- The workflow uses the supported Python version for the project
- Failing jobs block merge according to repository policy
- CI coverage includes both application checks and container build verification

**Points Estimate:** 3

### E8-S4 — Emit structured operational logs with request context
**As a** platform operator  
**I want to** receive structured JSON logs enriched with per-request identifiers  
**So that** I can trace requests and troubleshoot service behavior in shared environments  

**Acceptance Criteria:**
- Request logs are emitted as valid JSON entries
- Each request log includes a request identifier, method, path, status, and duration
- Log verbosity is configurable through environment settings
- Request context propagates consistently across logs produced during request handling

**Points Estimate:** 3

### E8-S5 — Validate deployment with a smoke test
**As a** release engineer  
**I want to** run an end-to-end smoke test against the compose stack  
**So that** I can verify the shipped deployment exercises the product’s critical workflows  

**Acceptance Criteria:**
- The smoke test boots the compose stack, waits for health, and tears it down reliably
- The test exercises representative auth, config, flag, and watch flows
- Failures return a non-zero exit code and leave enough output for diagnosis
- The smoke test is runnable both locally and in CI automation

**Points Estimate:** 5
