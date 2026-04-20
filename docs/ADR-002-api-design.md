# ADR-002: API Design

## Status: Accepted

## Context

The API reference defines a versioned HTTP interface rooted at `/api/v1`, using JSON payloads, Bearer authentication, standard HTTP verbs, cursor-based pagination, and Server-Sent Events for change watching. The expected clients include SDKs, curl-based operators, automation systems, and services that need simple integration with minimal infrastructure assumptions.

The product domain is configuration management and feature flag delivery, where interoperability, debuggability, and ease of adoption matter as much as raw transport efficiency. The documented endpoints are resource-oriented and map naturally to HTTP semantics: configuration values, flags, keys, audit events, and health checks. The watch model is also already defined in terms of SSE, which fits naturally into an HTTP-first API.

gRPC was a plausible alternative, especially for strongly typed internal service-to-service integrations. However, it would add client tooling requirements, reduce ease of manual inspection, complicate browser and shell access, and be a poor fit for the documented operational model centered on curl, SDKs, and plain HTTP integrations. The existing documentation already establishes versioning and error behavior in REST-style terms.

## Decision

Adopt a REST-style HTTP API as the primary interface, with explicit path-based versioning using `/api/v1`.

The service will use resource-oriented endpoints, JSON request and response bodies, standard HTTP methods, and HTTP status codes as the core interaction model. Long-lived change notifications will use Server-Sent Events over HTTP rather than introducing a separate RPC transport.

Versioning will be handled in the URL path so that major breaking changes can be introduced in a future `/api/v2` without ambiguity. Minor, backward-compatible changes such as additive fields, new scopes, or additional optional endpoints can be delivered within the same major version.

## Consequences

- The API remains easy to consume from SDKs, command-line tools, proxies, and common platform tooling.
- Operators can inspect and debug traffic with standard HTTP tooling without specialized gRPC support.
- The documented resources, verbs, pagination model, and SSE watch behavior stay consistent within a single protocol family.
- Path-based versioning makes breaking changes explicit and reduces ambiguity for client upgrades.
- REST over JSON is less compact and less strongly typed than gRPC, so some efficiency and schema-rigidity benefits are intentionally traded away.
- If future internal-only high-throughput use cases emerge, a secondary gRPC interface could still be added later without replacing the public HTTP contract.
