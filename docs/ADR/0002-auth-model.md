# ADR 0002: Authentication Model

## Status

Proposed

## Context

The architecture and API documentation describe a simple machine-to-machine authentication model centered on scoped credentials presented in the `Authorization` header. The system is intended for service clients, SDKs, and automation rather than end-user login flows. It also requires authorization decisions at the endpoint level, with clear distinctions between authentication failure and insufficient privileges.

The platform needs to create, validate, revoke, and audit these credentials while minimizing operational complexity. Because tokens are bearer credentials, storing them in plaintext would create unnecessary risk if the database were exposed. At the same time, the API already models permissions as scopes such as read and write capabilities across configuration, flags, and keys.

## Decision

Use bearer tokens as the authentication mechanism, store only hashed representations of those tokens at rest, and authorize requests using scope-based access control.

Issued tokens will be presented by clients in the `Authorization: Bearer <token>` header. The server will hash incoming tokens and compare the hash to stored records rather than persisting raw token secrets. Each token record will carry one or more scopes, and endpoint access will be enforced by checking for the required scope before executing the requested operation.

This preserves the simple API-key-like operational model described by the architecture while improving storage safety and making authorization rules explicit and composable.

## Consequences

- Clients get a simple, familiar machine-to-machine authentication flow with no session management or interactive login requirements.
- Storing only token hashes reduces the blast radius of a database leak because raw bearer secrets are not recoverable from normal application storage.
- Scope-based authorization maps cleanly to the documented endpoint permissions and supports least-privilege token issuance.
- Revocation, auditing, and key management remain straightforward because tokens are first-class managed resources.
- Operators must handle token issuance carefully because the raw token value is only available at creation time.
- Hashed storage adds a small amount of implementation complexity around secure generation, hashing, comparison, and rotation behavior.
- Bearer tokens remain high-value secrets in transit and at the client, so transport security and client-side secret handling remain critical.
