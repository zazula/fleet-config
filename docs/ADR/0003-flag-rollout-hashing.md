# ADR 0003: Flag Rollout Hashing

## Status

Proposed

## Context

The feature-flag engine needs deterministic percentage rollouts so a given subject receives a stable flag decision across repeated evaluations. The architecture calls out percentage rollouts alongside attribute rules and allowlists, which means the rollout mechanism must be predictable, easy to implement in the service, and portable across environments and SDKs.

Simple random sampling at request time would produce inconsistent experiences, while rollout logic tied too closely to a specific database or runtime would make cross-language evaluation harder. The system needs a bucket assignment approach based on stable inputs such as flag key and subject key.

## Decision

Use a SHA-256-based bucket hash to drive deterministic rollout assignment.

Specifically:

- Build a stable input string from the rollout context, including at minimum the flag identifier and subject identifier.
- Compute a SHA-256 digest over that input.
- Convert a defined portion of the digest into a numeric bucket.
- Map that bucket into the rollout range used by percentage-based rules.
- Standardize the input format and bucket calculation so server and SDK implementations remain consistent.

## Consequences

- Rollout decisions are deterministic for the same inputs, which gives users a consistent experience across evaluations.
- SHA-256 is widely available and portable, making equivalent implementations practical across languages and runtimes.
- The approach avoids dependence on database-specific sampling or runtime-local randomness.
- Changing the hash input format, the selected digest segment, or the bucketing algorithm will redistribute assignments for some or all subjects.
- This creates a trade-off: consistency is preserved while the algorithm remains fixed, but future algorithm changes can trigger redistribution during migrations.
- The implementation must document normalization rules carefully to avoid accidental divergence between server-side and SDK-side evaluation.
