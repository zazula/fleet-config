# ADR 0003: Flag Rollout Hashing

## Status

Proposed

## Context

The feature-flag engine supports percentage rollouts and must produce deterministic decisions for the same flag and subject attributes over time. A rollout strategy that is not deterministic would cause users or devices to move in and out of a treatment group unpredictably, making feature evaluation unreliable and creating a poor consumer experience.

The architecture calls for percentage-based rollouts, which requires converting stable input data into a bucket value. The implementation needs to be simple, portable across languages, and consistent across deployments so that SDKs and server evaluation logic can agree on who falls into a rollout cohort.

## Decision

Use SHA-256 to hash the rollout key material and map the resulting digest into percentage buckets for deterministic rollout evaluation.

This means:

- rollout evaluation derives a stable input string from the relevant flag identifier and subject key;
- the system computes a SHA-256 digest of that input;
- part of the digest is converted into a numeric bucket within a fixed range;
- rollout percentages are evaluated by comparing the bucket to the configured threshold;
- all implementations must use the same canonical input construction and bucket-mapping rules.

SHA-256 is chosen because it is widely available, deterministic, easy to implement across platforms, and resistant to accidental bias from weaker ad hoc hashing choices. The goal is consistency and portability, not cryptographic secrecy of rollout decisions.

## Consequences

Positive consequences:

- produces stable rollout assignments for the same subject and flag inputs;
- is easy to reproduce across server and SDK implementations in different languages;
- avoids dependence on runtime-specific hash functions that may vary by platform or process;
- keeps rollout behavior deterministic and explainable.

Negative consequences and trade-offs:

- changing the hash algorithm, bucket derivation method, or canonical input format later will redistribute cohorts;
- even small changes to salting or identifier composition can shift users between enabled and disabled states;
- cryptographic hashing is somewhat more expensive than simpler non-cryptographic hashes, though still acceptable for this use case.

Consistency versus redistribution consequences:

- the main benefit is long-term consistency: the same inputs map to the same buckets across requests and deployments;
- the main cost is redistribution sensitivity: any future change to the hashing contract will reshuffle assignments for some or all subjects;
- if redistribution is ever required intentionally, it should be treated as a controlled behavior change and documented as such;
- preserving a canonical hashing contract becomes part of API and SDK compatibility.
