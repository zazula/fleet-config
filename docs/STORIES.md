# fleet-config — User Stories

This document breaks epics `E1` through `E8` into INVEST-compliant user stories derived from `docs/PRD.md`, `docs/BACKLOG.md`, and `docs/ROADMAP.md`.

## E1 — Project Scaffolding

### E1-US-01 — Bootstrap the service workspace
**As a** platform engineer  
**I want to** initialize the repository with a standard backend project layout and dependency manifests  
**So that** the team can develop features in a consistent, maintainable codebase  

**Acceptance Criteria**
- The repository contains a documented application layout for API, domain, persistence, and tests.
- Dependency manifests install the service and developer tooling in a reproducible way.
- A new contributor can follow the setup steps and start the project locally without creating files manually.

**Points Estimate:** 3

### E1-US-02 — Run a baseline FastAPI application
**As a** platform engineer  
**I want to** start a baseline FastAPI app with health and readiness endpoints  
**So that** developers and automation can verify the service is running before feature work begins  

**Acceptance Criteria**
- The application starts with a documented local command.
- Health and readiness endpoints return successful responses when the app is operational.
- Startup failures produce actionable logs for local debugging.

**Points Estimate:** 2

### E1-US-03 — Initialize local persistence
**As a** platform engineer  
**I want to** provision SQLite initialization and migrations for local environments  
**So that** feature teams can build against a stable persistent store from day one  

**Acceptance Criteria**
- The application creates or connects to the configured SQLite database on startup.
- Schema migrations can be applied consistently in local and CI environments.
- Database configuration is documented for developers and automation.

**Points Estimate:** 3

### E1-US-04 — Enforce code quality checks
**As a** maintainer  
**I want to** configure linting, formatting, and pre-commit hooks  
**So that** changes are validated consistently before review  

**Acceptance Criteria**
- The repository includes documented linting and formatting commands.
- Pre-commit hooks run the agreed checks before a commit is created.
- CI can execute the same quality checks non-interactively.

**Points Estimate:** 2

### E1-US-05 — Establish the initial test harness
**As a** QA engineer  
**I want to** add a working unit and integration test harness  
**So that** new epics can ship with automated verification from the start  

**Acceptance Criteria**
- The repository includes a test runner command for local and CI execution.
- The test harness supports API-level integration tests against the application.
- Example baseline tests pass in CI and document expected testing patterns.

**Points Estimate:** 3

## E2 — Core Config CRUD

### E2-US-01 — Create a config value
**As a** fleet operator  
**I want to** create a config value for a namespace and key  
**So that** runtime consumers can retrieve centrally managed configuration  

**Acceptance Criteria**
- Creating a new namespace/key persists the submitted value and metadata.
- The API returns the stored value, version, and timestamps after creation.
- Attempts to create invalid payloads return validation errors without partial writes.

**Points Estimate:** 3

### E2-US-02 — Read a config value
**As a** fleet operator or agent process  
**I want to** read the latest value for a namespace and key  
**So that** scripts and services can use current configuration safely  

**Acceptance Criteria**
- The read endpoint returns the latest value, version, and update metadata for an existing key.
- Requests for missing keys return a descriptive not-found response.
- Authorized readers can access values while unauthorized callers are denied.

**Points Estimate:** 2

### E2-US-03 — Update an existing config value
**As a** fleet operator  
**I want to** update an existing config value  
**So that** I can change runtime behavior without editing application code  

**Acceptance Criteria**
- Updating a key persists the new value without changing its namespace or key identity.
- The API returns a higher version than the previous stored value.
- Invalid updates leave the previously stored value unchanged.

**Points Estimate:** 3

### E2-US-04 — Delete a config key
**As a** fleet operator  
**I want to** delete a config key that is no longer used  
**So that** obsolete configuration does not remain discoverable or misleading  

**Acceptance Criteria**
- Deleting an existing key removes it from current-value reads and namespace listings.
- Repeating the delete on a missing key returns a consistent not-found response.
- The delete action preserves enough metadata for downstream audit and versioning features.

**Points Estimate:** 3

### E2-US-05 — List namespace keys with pagination
**As a** fleet operator  
**I want to** list keys in a namespace with pagination metadata  
**So that** I can inspect large namespaces efficiently  

**Acceptance Criteria**
- The list endpoint returns keys with current values and metadata for the requested namespace.
- The endpoint supports a stable pagination mechanism with configurable page size.
- Empty namespaces return an empty collection rather than an error.

**Points Estimate:** 3

## E3 — Auth & API Keys

### E3-US-01 — Issue scoped API keys
**As a** fleet administrator  
**I want to** issue API keys with namespace and permission scopes  
**So that** clients get only the access they need  

**Acceptance Criteria**
- Key issuance supports assigning read and/or write scopes per namespace.
- The raw secret is shown only at creation time while storage keeps a non-reversible representation.
- Issued keys include metadata needed for later identification and governance.

**Points Estimate:** 5

### E3-US-02 — Rotate an API key
**As a** fleet administrator  
**I want to** rotate an API key without changing client intent  
**So that** I can recover from exposure or follow routine security policies  

**Acceptance Criteria**
- Rotation generates a replacement secret while preserving the configured scopes.
- The previous secret stops working after rotation completes.
- Rotation activity is traceable through key metadata and audit-friendly records.

**Points Estimate:** 3

### E3-US-03 — Revoke an API key
**As a** fleet administrator  
**I want to** revoke an API key  
**So that** compromised or obsolete clients lose access immediately  

**Acceptance Criteria**
- Revoked keys are rejected on all protected endpoints.
- Revocation is idempotent and returns a consistent outcome on repeated requests.
- Revoked keys remain visible in management views with a non-active status.

**Points Estimate:** 3

### E3-US-04 — Enforce API-key authentication on protected endpoints
**As a** security-conscious maintainer  
**I want to** require API-key authentication and authorization on protected routes  
**So that** only approved clients can read or write config  

**Acceptance Criteria**
- Protected endpoints reject missing or invalid credentials.
- Authorization decisions enforce namespace and permission scopes.
- Authentication failures return consistent status codes and error messages.

**Points Estimate:** 5

### E3-US-05 — Manage keys through an API
**As a** fleet administrator  
**I want to** create, list, rotate, and revoke keys through dedicated endpoints  
**So that** key lifecycle management is scriptable  

**Acceptance Criteria**
- The key management API exposes create, list, rotate, and revoke operations.
- List responses show safe metadata only and never return full secrets.
- API documentation describes the request and response shapes for each lifecycle action.

**Points Estimate:** 3

## E4 — Versioning & Audit Log

### E4-US-01 — Record a version on every config write
**As a** fleet operator  
**I want to** create a new version whenever a config value changes  
**So that** I have a reliable history of modifications  

**Acceptance Criteria**
- Each successful config write creates a new monotonically increasing version.
- Version records include the stored value snapshot and write metadata.
- Failed writes do not create version records.

**Points Estimate:** 3

### E4-US-02 — View key version history
**As a** fleet operator  
**I want to** retrieve the complete version history of a key  
**So that** I can understand how its value changed over time  

**Acceptance Criteria**
- The history endpoint returns all recorded versions for an existing key in chronological order.
- Each version entry includes version number, value snapshot, timestamp, and actor metadata.
- Requests for keys with no history return a descriptive not-found response.

**Points Estimate:** 2

### E4-US-03 — Review the audit trail for config activity
**As a** fleet operator  
**I want to** inspect audit entries for config and key-management actions  
**So that** I can trace who changed what and when  

**Acceptance Criteria**
- The audit log captures create, update, delete, rollback, and key-management events.
- Audit entries are immutable once recorded.
- Operators can filter or page through audit results without missing chronological order.

**Points Estimate:** 5

### E4-US-04 — Roll back a config key to a previous version
**As a** fleet operator  
**I want to** roll back a key to a selected earlier version  
**So that** I can recover quickly from a bad change  

**Acceptance Criteria**
- Rollback accepts a target historical version and restores that value as a new current version.
- The rollback action records its own audit event and resulting version number.
- Rolling back to the current version behaves as a safe no-op.

**Points Estimate:** 3

### E4-US-05 — Preserve audit and version integrity
**As a** compliance-minded maintainer  
**I want to** prevent mutation of historical audit and version records  
**So that** operational investigations can trust the stored history  

**Acceptance Criteria**
- Application workflows append new version and audit records rather than overwriting historical rows.
- Tests cover that rollback and delete flows preserve prior history.
- Operational documentation states the immutability expectations for version and audit data.

**Points Estimate:** 2

## E5 — Feature Flags

### E5-US-01 — Create and manage feature flags
**As a** fleet operator  
**I want to** create, update, and archive feature flags  
**So that** I can control feature rollout without code deployments  

**Acceptance Criteria**
- The API supports creating, updating, reading, listing, and archiving flags.
- Flag definitions include the data needed for boolean or variant evaluation.
- Archived flags are clearly distinguished from active flags in list and read responses.

**Points Estimate:** 5

### E5-US-02 — Evaluate boolean flags for a runtime context
**As a** runtime client  
**I want to** evaluate a boolean flag for a specific user context  
**So that** the application can decide whether a feature is enabled  

**Acceptance Criteria**
- Evaluation accepts a flag key and a context payload such as user ID or cohort.
- The response returns the resolved boolean value and enough metadata to explain the decision path.
- Requests for unknown flags return a descriptive not-found response.

**Points Estimate:** 3

### E5-US-03 — Evaluate multivariate flags
**As a** product service  
**I want to** resolve a variant from a multivariate flag  
**So that** experiments and targeted experiences can select the correct treatment  

**Acceptance Criteria**
- Variant flags can define multiple weighted or rule-driven outcomes.
- Evaluation returns a deterministic variant for the same flag and context inputs.
- Invalid flag definitions are rejected before they become active.

**Points Estimate:** 5

### E5-US-04 — Target flags by percentage rollout
**As a** deployment pipeline  
**I want to** enable a flag for a percentage of users  
**So that** I can perform gradual rollouts safely  

**Acceptance Criteria**
- Percentage rollout uses a deterministic algorithm based on stable identifiers.
- Repeated evaluations for the same flag and user context return the same result.
- Rollout settings can be adjusted without redefining the flag structure.

**Points Estimate:** 5

### E5-US-05 — Target flags by segment rules
**As a** fleet operator  
**I want to** define segment-based targeting rules  
**So that** flags can be enabled for specific cohorts or environments  

**Acceptance Criteria**
- Flag rules support matching on documented context attributes.
- Rule precedence is deterministic when multiple rules could apply.
- Evaluation metadata identifies which rule or default path produced the result.

**Points Estimate:** 5

### E5-US-06 — Validate flag behavior under concurrency
**As a** maintainer  
**I want to** verify flag updates and evaluations remain correct under concurrent load  
**So that** rollout decisions stay reliable during active changes  

**Acceptance Criteria**
- Concurrent reads and writes do not produce inconsistent or partial flag definitions.
- Automated tests cover concurrent evaluation and update scenarios.
- Documented limits or safeguards exist for supported concurrency behavior in the MVP.

**Points Estimate:** 3

## E6 — Watch / SSE

### E6-US-01 — Subscribe to config change events
**As a** runtime client  
**I want to** subscribe to config and flag change events over SSE  
**So that** my process can react to updates without polling  

**Acceptance Criteria**
- The service exposes an SSE endpoint for authorized subscribers.
- Subscribers receive change events for supported config and flag mutations.
- The event payload includes enough metadata for the client to identify what changed.

**Points Estimate:** 5

### E6-US-02 — Reconnect and resume missed events
**As a** runtime client  
**I want to** reconnect to the SSE stream and replay missed events  
**So that** short disconnects do not cause configuration drift  

**Acceptance Criteria**
- The SSE endpoint supports a resume mechanism using the last processed event identifier.
- Clients that reconnect within the replay window receive missed events in order.
- If replay is no longer possible, the service returns a clear recovery path for resynchronization.

**Points Estimate:** 5

### E6-US-03 — Filter watched events by scope
**As a** runtime client  
**I want to** subscribe only to relevant namespaces or event types  
**So that** my process handles only changes it cares about  

**Acceptance Criteria**
- Subscription requests can limit delivery by documented scope controls.
- Authorization rules prevent clients from subscribing beyond their granted access.
- Filtered subscriptions reduce irrelevant events without breaking event ordering.

**Points Estimate:** 3

### E6-US-04 — Operate SSE safely under load
**As a** maintainer  
**I want to** enforce connection-management limits and observability for SSE watchers  
**So that** the service remains stable under concurrent subscriptions  

**Acceptance Criteria**
- The service enforces documented watcher limits and returns a retry hint when limits are exceeded.
- Connection lifecycle events are logged or measured for operational visibility.
- Automated integration tests cover subscribe, disconnect, and reconnect behavior.

**Points Estimate:** 3

## E7 — Python Client SDK

### E7-US-01 — Install and configure the Python SDK
**As a** Python service developer  
**I want to** install a typed `fleetconfig` package and configure a client  
**So that** my application can consume fleet-config with minimal setup  

**Acceptance Criteria**
- The SDK is packaged for installation through the documented Python distribution flow.
- Client configuration supports base URL, credentials, and sensible defaults.
- Type hints are available for public client interfaces.

**Points Estimate:** 3

### E7-US-02 — Read and write config through the SDK
**As a** Python service developer  
**I want to** call config CRUD operations from the SDK  
**So that** my application can manage config without hand-written HTTP code  

**Acceptance Criteria**
- The SDK exposes client methods for config reads, writes, deletes, and namespace listing.
- SDK methods return typed models or structured responses matching the service API.
- API errors are translated into documented SDK exceptions.

**Points Estimate:** 5

### E7-US-03 — Evaluate feature flags through the SDK
**As a** Python service developer  
**I want to** evaluate boolean and variant flags through helper methods  
**So that** application code can consume rollout decisions consistently  

**Acceptance Criteria**
- The SDK exposes helpers for boolean and variant flag evaluation.
- Evaluation helpers accept documented context objects and return typed results.
- SDK behavior stays aligned with service-side evaluation semantics.

**Points Estimate:** 3

### E7-US-04 — Consume watch events from the SDK
**As a** Python service developer  
**I want to** stream watch events through an SDK client interface  
**So that** my service can react to config updates without implementing SSE plumbing  

**Acceptance Criteria**
- The SDK provides a client interface for connecting to the watch stream.
- The watch client surfaces parsed event objects and reconnect metadata.
- Usage documentation shows how to start and stop a watch cleanly.

**Points Estimate:** 5

### E7-US-05 — Use robust retries and error handling
**As a** Python service developer  
**I want to** get consistent retry and error-handling behavior from the SDK  
**So that** transient service issues are easier to recover from safely  

**Acceptance Criteria**
- The SDK distinguishes retryable failures from permanent API errors.
- Retry behavior is configurable and documented for supported operations.
- Exceptions include enough context for callers to log and debug failures.

**Points Estimate:** 3

### E7-US-06 — Trust the SDK through automated quality gates
**As a** maintainer  
**I want to** validate the SDK with tests, linting, and strict typing  
**So that** published releases are reliable for downstream teams  

**Acceptance Criteria**
- The SDK test suite covers config, flags, watch, and error-handling workflows.
- CI runs linting, strict type checking, and tests on the SDK package.
- Release documentation explains the supported Python versions and packaging flow.

**Points Estimate:** 3

## E8 — Deploy & Observability

### E8-US-01 — Build a production-ready container image
**As a** platform engineer  
**I want to** produce a container image for fleet-config  
**So that** the service can be deployed consistently across environments  

**Acceptance Criteria**
- The repository contains a documented Docker build for the service.
- The container starts the application with production-oriented defaults.
- The image build is usable in local smoke tests and CI automation.

**Points Estimate:** 3

### E8-US-02 — Launch the stack with docker-compose
**As a** platform engineer  
**I want to** start fleet-config and its dependencies with one compose command  
**So that** local and small-scale deployments are easy to operate  

**Acceptance Criteria**
- `docker-compose` or `docker compose` starts the documented service stack successfully.
- Compose configuration includes health checks and restart behavior for managed services.
- Startup documentation identifies required environment variables and default ports.

**Points Estimate:** 3

### E8-US-03 — Run CI for build and verification
**As a** maintainer  
**I want to** run automated build and verification workflows in GitHub Actions  
**So that** changes are validated before merge  

**Acceptance Criteria**
- CI runs the documented quality checks and automated tests for the repository.
- Workflow status is visible to reviewers before merging changes.
- Failures identify the stage that needs attention.

**Points Estimate:** 3

### E8-US-04 — Emit structured operational logs
**As a** platform engineer  
**I want to** emit structured JSON logs from the service  
**So that** operational events can be searched and analyzed consistently  

**Acceptance Criteria**
- Application logs use a structured format with timestamp, level, and request context fields.
- Sensitive values such as API secrets are excluded or redacted from logs.
- Logging behavior is documented for local and deployed environments.

**Points Estimate:** 2

### E8-US-05 — Provide a baseline observability dashboard and smoke tests
**As a** platform engineer  
**I want to** ship smoke tests and a starter dashboard definition  
**So that** deployments can be validated and monitored quickly  

**Acceptance Criteria**
- The repository includes a repeatable smoke test flow for a deployed stack.
- A baseline dashboard definition covers service health and key operational signals.
- Deployment documentation explains how operators use the smoke test and dashboard together.

**Points Estimate:** 3
