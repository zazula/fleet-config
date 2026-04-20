# ADR 0002: Auth Model

## Status

Proposed

## Context

The service is intended to be simple to operate and easy for machine clients to consume. The current architecture and API describe scoped credentials used for authorization on every request, and the API contract already expects Bearer-token authentication with read and write permissions separated by scope.

The system does not need end-user login flows, browser sessions, or a full identity-provider integration for its initial use case. It does, however, need revocable machine credentials, least-privilege access, audit attribution, and a storage model that reduces the impact of a database leak.

Simple opaque API keys satisfy the basic machine-to-machine use case, but storing them in plaintext would create unnecessary risk, and using a single undifferentiated credential model would make it harder to enforce endpoint-level permissions cleanly as the API surface grows.

## Decision

Adopt Bearer tokens as the external authentication format, store only hashed token material at rest, and authorize requests using scope-based access control.

This means:

- clients send credentials using the `Authorization: Bearer <token>` header;
- issued tokens are treated as opaque secrets for clients rather than self-describing JWTs;
- the server stores a cryptographic hash of the token secret rather than the plaintext token;
- each token is associated with an explicit set of scopes such as `config:read`, `config:write`, `flags:read`, `flags:write`, and `watch:read`;
- request authorization checks required scopes per endpoint before executing business logic;
- revocation is handled server-side by deleting or disabling the stored hashed credential record.

This model keeps client usage simple while improving security posture over plaintext API-key storage. It also aligns with the documented API contract that uses Bearer authentication and scope-based authorization.

## Consequences

Positive consequences:

- maintains a straightforward machine-consumable auth flow with a standard HTTP Authorization header;
- reduces the blast radius of database compromise because raw credentials are not stored at rest;
- enables least-privilege access by granting tokens only the scopes required for a consumer's role;
- supports clean endpoint-level authorization and clearer audit semantics;
- keeps revocation and permission changes under server control.

Negative consequences and trade-offs:

- hashed storage means tokens cannot be shown again after issuance, so clients must capture them at creation time;
- every authenticated request requires a server-side lookup rather than purely local token verification;
- scope management introduces additional operational overhead compared with a single all-access key;
- migrating from any existing plaintext key storage would require a rotation plan because plaintext tokens cannot be derived from hashes.

Operational consequences:

- token issuance flows must present the secret once and never persist it in logs;
- hashing parameters and token length should be selected to balance brute-force resistance and lookup cost;
- authorization failures should clearly distinguish invalid credentials from insufficient scope;
- audit records should attribute actions to the token subject or service identity associated with the hashed credential.
