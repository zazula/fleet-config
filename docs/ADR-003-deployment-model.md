# ADR-003: Deployment Model

## Status: Accepted

## Context

The architecture document describes `fleet-config` as shipping in a single stateless container, with FastAPI handling API traffic, SSE watchers, authentication, service logic, and persistence integration. The intended audience values operational simplicity over immediate horizontal scale, and the initial topology centers on one service instance backed by SQLite, with PostgreSQL available later when growth requires it.

This means the deployment model must optimize for low ceremony, portability, and predictable operations. The system also includes long-lived watch connections over SSE, which benefit from straightforward networking and stable request routing. A service mesh would add observability and traffic-policy capabilities, but it would also introduce substantial operational surface area that is not justified by the current scale target or the single-service topology described in the docs.

Likewise, aggressive horizontal scaling is not the primary design center while SQLite remains the default backend. Multi-instance deployment becomes materially more attractive only after moving to PostgreSQL and establishing the operational need for scale-out, redundancy, or separate edge routing.

## Decision

Adopt a container-first deployment model built around a single service container, without requiring a service mesh, and scale vertically first before introducing multi-instance horizontal scaling.

The service will be packaged and deployed as a standard container image. Initial production deployment assumes one application instance with mounted persistent storage for SQLite, fronted by ordinary HTTP ingress or load balancing as needed. A service mesh is not part of the baseline architecture.

When usage outgrows the single-node model, the next step is to migrate the database backend to PostgreSQL and then add horizontal application replicas behind shared ingress. Mesh adoption remains optional and should be driven by proven operational needs such as cross-service traffic policy, mutual TLS standardization, or advanced observability across a larger platform.

## Consequences

- Teams get a simple deployment story that matches the product goal of fast adoption with minimal infrastructure.
- Containerization keeps packaging portable across local development, VMs, and Kubernetes-style environments.
- Avoiding a mandatory service mesh reduces baseline complexity, cost, and operator burden.
- SSE behavior stays simpler in the initial topology because there are fewer moving parts in connection routing.
- The default model favors vertical scaling and single-instance reliability over immediate horizontal elasticity.
- True multi-instance scale and high availability require the PostgreSQL migration and more deliberate operational design around shared state, ingress behavior, and watcher distribution.
