# ADR 0001: Storage Abstraction

## Status

Proposed

## Context

The current architecture targets a single-container deployment backed by SQLite to keep initial operations simple. The architecture document also calls out the need to remain swappable to Postgres as the system outgrows a single-node SQLite setup. The service includes multiple persistence-backed concerns—configuration storage, feature flags, API tokens, and audit records—which should not force application-layer rewrites when the database backend changes.

At the API layer, the service exposes versioned config CRUD, feature-flag evaluation and management, token administration, and audit-oriented write behavior. Those behaviors require transactional updates, predictable async I/O under FastAPI, and a clean separation between HTTP concerns, business rules, and persistence details.

## Decision

Use SQLAlchemy's async support as the primary database abstraction and implement data access through a repository pattern.

Specifically:

- Use SQLAlchemy async engines and sessions for both SQLite today and Postgres later.
- Keep ORM models and migrations aligned with a relational schema that works across both backends.
- Introduce repository interfaces for the main aggregate areas such as config entries, feature flags, API tokens, and audit events.
- Keep service-layer code dependent on repository contracts rather than database-specific queries.
- Centralize transaction boundaries in the service layer so multi-step writes remain explicit and portable across backends.

## Consequences

- The application gains a clear migration path from SQLite to Postgres without rewriting routers or core business logic.
- Async database access aligns with the FastAPI execution model and avoids introducing separate sync persistence pathways.
- Repository boundaries improve testability by allowing service logic to be exercised with fakes or targeted integration fixtures.
- Query behavior becomes more deliberate, which is helpful for config versioning, audit logging, and token lifecycle operations.
- The design adds some upfront abstraction and boilerplate compared with directly querying through ORM sessions in route handlers.
- Some SQLAlchemy and backend differences still need active management, especially around SQLite/Postgres type behavior, concurrency semantics, and SQL feature parity.
