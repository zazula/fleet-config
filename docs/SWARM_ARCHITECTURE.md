# Swarm Architecture for `fleet-config`

## Overview

The E7 proof of concept demonstrates a thread-per-role swarm coordinated through `fleet-config`.
Instead of agents exchanging direct point-to-point state, the swarm uses shared config keys and
feature flags as the control plane.

## Thread-per-role model

Each role owns a narrow concern and reacts to shared state:

- **Coordinator** decides what work should happen next
- **Workers** subscribe to namespace changes and pull their assignments from config
- **Review / QA / Deploy roles** can use the same pattern for readiness gates and rollout controls

This model keeps agent responsibilities simple:

- writes are explicit and auditable
- reads are idempotent
- watchers react to change instead of polling blindly in business logic

## `fleet-config` as coordination backbone

`fleet-config` gives the swarm three primitives:

- **Versioned config** for shared intent, such as task assignments or runtime parameters
- **Feature flags** for routing and behavior selection, such as toggling parallel execution
- **SSE watch streams** so agents can react quickly when shared state changes

In the demo, the coordinator:

1. creates `enable_parallel_processing`
2. evaluates the flag for a routing decision
3. writes `coordination/task` and `coordination/worker_count`

Workers subscribe to `coordination` and read the current assignment after receiving an SSE event.

## Scaling patterns

This PoC suggests a few viable scaling directions:

- **Namespace-per-swarm** to isolate independent agent groups
- **Role-specific key prefixes** such as `workers/`, `qa/`, or `deploy/`
- **Flag-driven rollout** to incrementally enable new swarm behaviors
- **Replay from current config** so reconnecting agents can restore state before resuming watches

For larger deployments, a production-grade watch implementation would likely move from polling the
database to a push-oriented event pipeline, while preserving the same API contract for agents.

## Lessons learned from the PoC

- A shared config service is a practical backbone for multi-agent coordination when the workflow is
  mostly state-driven.
- SSE is enough for lightweight orchestration and local demos because agents only need ordered,
  append-like change notifications.
- Feature flags are useful beyond user-facing product behavior; they also provide safe operational
  switches for swarm routing, concurrency, and gradual rollout.
- The clean separation between "watch for change" and "read current state" makes agents resilient
  to reconnects and duplicate events.

## Operational guidance

- Keep coordination keys coarse-grained and human-readable.
- Prefer idempotent worker actions keyed by config version.
- Treat feature flag evaluation as a policy decision and config reads as state retrieval.
- Log agent identity and config version whenever work starts or completes.

The `demos/multi_agent_demo.py` script is the reference implementation for this pattern in the
current repository.
