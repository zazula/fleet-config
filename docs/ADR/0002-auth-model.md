# ADR 0002: Auth Model

## Status

Proposed

## Context

The architecture and API documents describe authenticated access for all configuration and flag operations, with authorization enforced through scopes such as `config:read`, `config:write`, `flags:read`, `flags:write`, and token-management capabilities. The current product goal is to keep authentication simple for service-to-service usage while still supporting least-privilege access and auditability.

A naive API key model is easy to ship, but plain key storage creates unnecessary risk if the database is exposed, and coarse authorization limits future operability as more endpoints and automation workflows are added. The API already assumes Bearer-style authorization headers and audit attribution tied to an authenticated subject.

## Decision

Adopt bearer tokens as the authentication mechanism, store only hashed token material at rest, and authorize requests through explicit scopes.

Specifically:

- Issue opaque bearer tokens for clients to present in the `Authorization: Bearer ...` header.
- Persist only a one-way hash of the token secret, never the full recoverable token value.
- Associate each token with a subject identifier and a bounded set of scopes.
- Enforce scope checks in auth middleware and/or service boundaries before executing protected operations.
- Use the authenticated subject and granted scopes to support audit-log attribution and revocation workflows.

## Consequences

- The system remains simple for machine clients because it uses a familiar bearer-token flow rather than a more complex delegated auth system.
- Storing hashed tokens reduces blast radius if the token table is leaked, because tokens cannot be read back directly from persistence.
- Scope-based authorization supports least privilege and maps cleanly to the API surface already defined in the docs.
- Audit entries can identify which subject performed a write or revocation action.
- Token issuance must surface the plaintext token exactly once, which requires careful operational handling by clients.
- Revocation and lookup flows must be built around hash-based matching and metadata, not plaintext token recovery.
- Opaque bearer tokens still require strong transport security and secure client-side storage because possession remains sufficient for access.
