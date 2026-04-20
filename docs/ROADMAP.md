# Fleet Config — Project Roadmap

## 1. Overview

This roadmap sequences delivery of the fleet-config service into phased milestones with explicit acceptance gates. Each phase builds on the prior, with parallel epics where dependencies allow. Stretch phases are gated behind MVP success.

---

## 2. Phase 1: MVP (Weeks 1–2)

**Goal:** Ship a working service that replaces scattered config files and ad-hoc env vars.

| Epic | Description |
|------|-------------|
| E1 — Scaffolding | Project layout, FastAPI app skeleton, SQLite init, Docker + docker-compose boilerplate, CI pipeline scaffold |
| E2 — Core Config CRUD | Create / Read / Update / Delete config keys and namespaces; schema validation; list pagination |
| E3 — Auth & API Keys | API key issuance and rotation; key scoping (namespace + read/write); middleware guard |
| E4 — Versioning & Audit Log | Every write produces a new version; audit log table tracks who/when/what; rollback to revision |

**Gate — MVP Release Criteria**
- All CRUD endpoints return correct HTTP status codes and payload shapes
- Auth middleware rejects requests with missing or expired keys
- At least 80 % unit-test coverage on core modules
- `docker build` completes with zero warnings
- `docker-compose up` starts the service and health-check endpoint responds 200

---

## 3. Phase 2: Feature Flags + Watch (Week 3)

**Goal:** Add gradual rollout capability and real-time push so clients stay in sync.

| Epic | Description |
|------|-------------|
| E5 — Feature Flags | Flag CRUD, boolean and variant evaluation, targeting rules (percentage rollouts, user segments) |
| E6 — Watch / SSE | Server-Sent Events endpoint; service pushes change events to subscribed clients; reconnect handshake |

**Gate — Feature Flag Release Criteria**
- Flag evaluation returns correct value for all targeting-rule combinations
- Percentage rollout is deterministic (uses consistent hash of flag key + user ID)
- SSE client reconnects within 2 s and receives missed events via replay window
- Integration tests cover flag CRUD, evaluation, and SSE subscribe/unsub flows

---

## 4. Phase 3: SDK + Deployment (Week 4)

**Goal:** Make fleet-config consumable by product services and trivially deployable.

| Epic | Description |
|------|-------------|
| E7 — Python Client SDK | Typed Python package (`fleetconfig`); `Client` context-manager; flag evaluation helpers; published to PyPI |
| E8 — Deploy & Observability | Production `docker-compose.yml` with health checks, restart policies; structured JSON logging; basic Grafana dashboard JSON |

**Gate — SDK Release Criteria**
- SDK package passes `flake8`, `mypy --strict`, and `pytest` in CI
- SDK is published to PyPI (public or internal index) with a versioned release tag
- `docker-compose up` brings up the full stack in one command
- CI pipeline is green on the `main` branch

---

## 5. Phase 4: Hardening (Week 5)

**Goal:** Move from MVP to production-grade reliability and operability.

| Epic | Description |
|------|-------------|
| E9 — Postgres Backend | Swap SQLite for Postgres; add connection pooling; preserve all migration scripts |
| E10 — Prometheus Metrics | Expose `/metrics` in Prometheus format; track request latency, flag eval latency, SSE watcher count |
| E11 — Rate Limiting | Token-bucket rate limiter per API key; configurable via config file |
| E12 — Admin Web UI Skeleton | Read-only admin dashboard (list namespaces, view flags, view audit log); read-only until auth is refined |

**Gate — Hardening Release Criteria**
- Load test: 500 concurrent SSE watchers + 200 RPS API traffic for ≥ 5 min with p99 latency < 200 ms
- Security review: no plaintext API key storage, no SQL injection, SSE origin-check enabled
- All configuration documented in `docs/config-reference.md`
- `docs/CHANGELOG.md` updated with versioned entries

---

## 6. Dependency Graph

```
E1 ─┬─► E2 ─┬─► E4
    │        └───────────────────────► E6
    │        │
    │        └──► E5 ──────► E7 ──► (all prior epics)
    │
    └─► E3 ─┘
         │
         └───────────────► E5

E8 depends on E1 only
```

**Readable form**

| This epic | Is blocked by |
|-----------|---------------|
| E2 | E1 |
| E3 | E1 |
| E4 | E2 |
| E5 | E2 and E3 |
| E6 | E2 |
| E7 | E2, E5, E6 |
| E8 | E1 |
| E9–E12 | E7 (SDK must be stable before hardening begins) |

**Parallel tracks after E1**
- Track A: E2 → E4 → E6 (storage, versioning, push)
- Track B: E3 → E5 (auth, then flags)
- Track C: E7 (SDK; waits for E2, E5, E6 to be stable)

---

## 7. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| SQLite write concurrency under SSE load | DB write stalls → SSE latency spikes | Enable WAL mode; serialize writes behind a single `asyncio.Lock` for MVP |
| SSE connection scaling | Too many open connections exhausts file descriptors / memory | Hard cap of 100 concurrent watchers for MVP; return HTTP 503 + `Retry-After` header above cap |
| API key security | Key exfiltration from logs or storage | Store only bcrypt hash; never log raw keys; identification uses a 6-char prefix (key shows prefix + last 4 chars) |
| Config value size | Large payloads cause memory pressure | Reject values > 64 KB at write time with HTTP 413 |
| Percentage rollout hash collision | Many users land in wrong segment | Use HMAC-SHA256 of `flag_key + user_id` as hash input; document non-exact distribution for populations < 1 000 |
| Postgres migration from SQLite | Data loss or downtime | Run `pgloader` in a shadow migration step before cut-over; maintain SQLite as read-only fallback for 2 weeks |
| SDK backward-compatibility | Breaking API changes break callers | Pin SDK major version to service major version; publish changelog with migration guide |
