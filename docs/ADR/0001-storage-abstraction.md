# ADR 0001: Storage Abstraction

## Status

Proposed

## Context

The architecture is designed to start with SQLite for operational simplicity and a single-container deployment model, while preserving a clear path to PostgreSQL when concurrency, operational requirements, or managed-database adoption justify it. The existing architecture already calls out a repository layer between the service layer and the database, and it identifies SQLAlchemy async with `aiosqlite` as part of the initial stack.

Without an explicit storage decision, application code can drift toward SQLite-specific assumptions, direct ORM coupling in handlers or services, and ad hoc query logic that becomes expensive to migrate later. The system also needs to support asynchronous request handling, transactional write paths, audit logging, and future database portability without forcing a rewrite of business logic.

## Decision

Use SQLAlchemy's async support as the primary database access technology and isolate persistence behind a repository pattern.

This means:

- the application uses SQLAlchemy async sessions for database interaction;
- SQLite is the initial runtime backend via `aiosqlite`;
- repository interfaces encapsulate persistence operations for configs, flags, audit records, API credentials, and related domain entities;
- the service layer depends on repository abstractions rather than raw SQLAlchemy models or engine/session details;
- database-specific concerns, including query tuning and dialect differences, are contained within repository and persistence modules.

This decision intentionally favors a thin repository pattern over embedding persistence logic throughout the codebase. SQLAlchemy remains the common abstraction for both SQLite and a future PostgreSQL backend, allowing the application to change database drivers and configuration with minimal impact on API handlers and domain services.

## Consequences

Positive consequences:

- creates a deliberate migration path from SQLite to PostgreSQL without rewriting the API or service layers;
- keeps FastAPI routes and business services focused on validation, authorization, and domain logic instead of persistence details;
- supports async I/O consistently across request handling and database access;
- improves testability by allowing repositories to be mocked or swapped with test implementations;
- centralizes transaction and query behavior, which helps with auditing, version increments, and consistency rules.

Negative consequences and trade-offs:

- adds an extra abstraction layer that increases initial implementation effort;
- introduces some duplication between domain models, ORM mappings, and repository contracts if not kept disciplined;
- does not eliminate all database differences, so some PostgreSQL migration work will still be required for DDL, indexing, and concurrency semantics;
- async SQLAlchemy has more setup and lifecycle complexity than direct synchronous SQLite access.

Operational consequences:

- the codebase should avoid SQLite-only SQL features unless they are isolated and replaceable;
- schema management and migrations should be written with both the current SQLite deployment and future PostgreSQL compatibility in mind;
- repository boundaries become a stable seam for future optimizations such as read-model tuning, caching, or backend substitution.
