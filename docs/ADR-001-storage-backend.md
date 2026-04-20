# ADR-001: Storage Backend

## Status: Accepted

## Context

`fleet-config` is designed as a centralized configuration and feature-flag service for small-to-medium deployments that prioritize operational simplicity. The architecture document describes a single stateless container backed initially by SQLite, with an explicit path to PostgreSQL later. The service must support versioned configuration values, immutable history, feature flag evaluation, scoped API key storage, audit records, and watch-style change propagation.

These requirements favor a storage backend that can provide strong consistency for writes, simple transactional semantics, and straightforward querying across related entities. The data model in the architecture document is clearly relational: configuration values point to current versions, historical versions are append-only, API keys are indexed and revocable, and audit events need structured filtering and pagination. While the product exposes key-value and flag semantics externally, it still requires joins, uniqueness guarantees, transactional writes, and durable audit trails internally.

Alternative approaches such as a pure KV store would simplify a narrow subset of point lookups, but would complicate version history, audit access, scoped key management, and cross-entity consistency. A document database would also be workable, but would add operational complexity without materially improving the primary access patterns described in the docs.

## Decision

Adopt a relational SQL backend as the system of record, using SQLite for the initial deployment model and PostgreSQL as the planned scale-up path.

SQLite is chosen as the default backend because it matches the product goal of zero-infrastructure adoption, supports transactional semantics, works well in a single-container deployment, and is sufficient for the expected early-stage workload. PostgreSQL is the forward path when higher write concurrency, managed durability, backup workflows, or multi-instance deployment become necessary.

The service will therefore treat the database as a relational persistence layer rather than implementing a separate dedicated KV store. Configuration and flag APIs may present key-value semantics externally, but the underlying data model remains normalized and transaction-oriented.

## Consequences

- The product stays easy to adopt because a single container plus SQLite is enough for initial production use.
- The storage model cleanly supports version history, auditing, scoped credential records, and paginated list queries.
- The service preserves a credible migration path to PostgreSQL without redesigning the API or domain model.
- Operational limits are explicit: SQLite constrains high-concurrency writes and multi-node deployment, so horizontal scale is deferred until PostgreSQL adoption.
- The architecture avoids the complexity of running both a relational database and a separate KV store.
- Some backend-specific behavior will still need care during migration, especially around concurrency, locking, and SQL dialect differences.
