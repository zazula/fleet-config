# ADR 0003: Flag Rollout Hashing

## Status

Proposed

## Context

The feature-flag engine supports percentage rollouts and must evaluate flags deterministically so that a given actor receives a stable result across repeated requests. The architecture emphasizes predictable evaluation behavior for small-to-medium deployments, and the API design implies that clients depend on consistent outcomes for controlled rollouts.

To support percentage-based rollout, the system needs a repeatable way to map an evaluation key, actor identifier, or similar subject value into a bucket space. That mapping should be implementation-independent, stable across processes, and easy to reproduce in documentation and SDKs.

## Decision

Use a SHA-256 based hash to derive deterministic rollout buckets for percentage flag evaluation.

The rollout algorithm will hash a stable input composed of the flag identity and subject identity, then map the resulting digest into the bucket range used for percentage comparisons. This ensures that the same subject is assigned consistently for the same flag, independent of runtime instance or process state.

SHA-256 is chosen because it is widely available, deterministic, and easy to implement consistently across languages without introducing custom hashing logic.

## Consequences

- Rollout decisions remain stable for a given subject and flag, which avoids user flapping and preserves confidence in staged delivery.
- The algorithm is straightforward to reproduce across backend services and SDKs, improving interoperability.
- The hashing approach does not require shared mutable state, which fits the stateless application design.
- Changing the rollout input shape or hashing algorithm in the future would redistribute bucket assignments for some or all subjects.
- Consistency is prioritized over bucket preservation across algorithm changes; any future change must be treated as a deliberate migration event.
- SHA-256 is computationally heavier than simpler non-cryptographic hashes, but the cost is acceptable for the expected request profile and the benefit of standardization.
