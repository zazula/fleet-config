# ADR 0001: Storage Abstraction

## Status

Proposed

## Context

The current architecture targets operational simplicity by shipping as a single container backed by SQLite, while explicitly keeping the door open to migrate to PostgreSQL later as scale and operational needs grow. The architecture also separates the FastAPI router layer from the service layer and repository layer, which suggests a need for a persistence approach that does not leak database-specific behavior into request handling or business logic.

The API surface includes audited write operations, cursor-paginated list endpoints, versioned configuration records, scoped authentication, and real-time watch behavior. Those features require clear transactional boundaries and durable data access patterns that can work against SQLite now and PostgreSQL later without forcing a major rewrite.

## Decision

Use SQLAlchemy's async ORM and Core capabilities as the database access foundation, and organize persistence behind a repository pattern.

Repositories will define the application-facing interface for loading and mutating configuration entries, feature flags, API tokens, audit records, and supporting watch-related persistence concerns. The service layer will depend on repository interfaces rather than raw SQL or framework-bound session handling. SQLAlchemy async sessions will provide transaction management and database connectivity for both SQLite in the initial deployment model and PostgreSQL in a future deployment.

This decision keeps the storage model relational, preserves portability across supported SQL backends, and aligns with the existing layered architecture described in the design documents.

## Consequences

- The application gains a clean boundary between business logic and persistence, making a later move from SQLite to PostgreSQL substantially easier.
- Async database access fits the FastAPI-based async request model and avoids introducing a mismatched synchronous persistence layer.
- Repository interfaces improve testability by allowing service-layer tests to use fakes or stubs without requiring a real database for every case.
- SQLAlchemy provides migrations, dialect handling, and query composition capabilities that reduce the amount of handwritten database glue code.
- The codebase takes on additional abstraction and setup cost compared with direct SQL or a lighter-weight SQLite-only approach.
- Some queries may need deliberate tuning to behave consistently across SQLite and PostgreSQL, especially around JSON handling, concurrency characteristics, and SQL dialect differences.
