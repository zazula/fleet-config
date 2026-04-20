#!/usr/bin/env bash
# bootstrap-swarm.sh — Complete the fleet-config swarm setup
# Run this script from lambda (outside the Codex sandbox) where network access is available.
# Usage: bash /home/zazula/fleet-config/bootstrap-swarm.sh

set -euo pipefail

REPO_DIR="/home/zazula/fleet-config"
AGENT_SERVICE="http://localhost:18007"
REPO_URL="https://github.com/zazula/fleet-config"

echo "=== fleet-config Swarm Bootstrap ==="
echo ""

# ──────────────────────────────────────────────
# Phase 3A: Create GitHub repo + push
# ──────────────────────────────────────────────
echo "--- Phase 3A: Creating GitHub repo ---"
cd "$REPO_DIR"

if ! gh repo view zazula/fleet-config &>/dev/null; then
  gh repo create zazula/fleet-config --public --source=. --remote=origin --push \
    --description "Centralized config + feature-flag service for the agent fleet"
  echo "Repo created and pushed."
else
  echo "Repo already exists. Pushing any unpushed commits..."
  git push origin main 2>/dev/null || true
fi

# ──────────────────────────────────────────────
# Phase 3B: Create labels
# ──────────────────────────────────────────────
echo ""
echo "--- Phase 3B: Creating labels ---"
for label in epic task mvp stretch "role:pm" "role:planner" "role:architect" "role:designer" "role:engineer" "role:qa" "role:devops" "role:reviewer" "role:tech-writer"; do
  gh label create "$label" --repo zazula/fleet-config --force 2>/dev/null && echo "  label: $label" || true
done

# ──────────────────────────────────────────────
# Phase 3C: Create issues
# ──────────────────────────────────────────────
echo ""
echo "--- Phase 3C: Creating epic + task issues ---"

declare -A EPIC_NUMBERS
declare -A TASK_NUMBERS

create_epic() {
  local num=$1 title=$2 body=$3
  local issue_url
  issue_url=$(gh issue create --repo zazula/fleet-config \
    --title "$title" \
    --body "$body" \
    --label "epic" \
    --label "mvp")
  local issue_num=$(echo "$issue_url" | grep -oE '[0-9]+$')
  EPIC_NUMBERS[$num]=$issue_num
  echo "  Epic $num → #$issue_num"
}

create_task() {
  local key=$1 title=$2 body=$3 parent_key=$4 labels=$5
  local parent_num=${EPIC_NUMBERS[$parent_key]}
  local full_body="${body}

Parent: #${parent_num}"
  local issue_url
  issue_url=$(gh issue create --repo zazula/fleet-config \
    --title "$title" \
    --body "$full_body" \
    --label "task" \
    --label "mvp" \
    ${labels:+--label "$labels"})
  local issue_num=$(echo "$issue_url" | grep -oE '[0-9]+$')
  TASK_NUMBERS[$key]=$issue_num
  echo "    Task $key → #$issue_num (parent: #$parent_num)"
}

# E1: Project Scaffolding
create_epic "E1" "Epic E1: Project Scaffolding" \
  "Establish the repo structure, tooling, and base application so every subsequent epic has a clean foundation to build on.

## Tasks
- [ ] T1.1: Initialize project structure
- [ ] T1.2: Base FastAPI application
- [ ] T1.3: Database setup
- [ ] T1.4: Pre-commit hooks + lint config
- [ ] T1.5: Initial test harness

## Acceptance Criteria
- [ ] All deps install, lint passes, health endpoint works, Dockerfile builds"

create_task "T1.1" "T1.1: Initialize project structure" \
  "Create pyproject.toml with all dependencies (fastapi, uvicorn, sqlalchemy[asyncio], aiosqlite, pydantic, pydantic-settings, httpx, ruff, mypy, pytest, pytest-asyncio). Set up src/fleet_config/ package layout. Configure ruff and mypy." "E1" "role:engineer"

create_task "T1.2" "T1.2: Base FastAPI application" \
  "Implement app factory in main.py with create_app(). Add GET /health endpoint. Configure settings via pydantic-settings. Set up structured JSON logging with structlog." "E1" "role:engineer"

create_task "T1.3" "T1.3: Database setup" \
  "Create async SQLAlchemy engine factory, async session maker, declarative base. Implement init_db() that creates tables on startup. Enable WAL mode for SQLite." "E1" "role:engineer"

create_task "T1.4" "T1.4: Pre-commit hooks + lint config" \
  "Add .pre-commit-config.yaml with ruff, mypy. Create Makefile with lint/format/test/typecheck targets." "E1" "role:devops"

create_task "T1.5" "T1.5: Initial test harness" \
  "Set up pytest-asyncio. Create conftest.py with fixtures for in-memory SQLite test database, test client. Write smoke test for GET /health." "E1" "role:qa"

# E2: Core Config CRUD
create_epic "E2" "Epic E2: Core Config CRUD" \
  "Implement the core configuration storage and API — the foundational value proposition.

## Tasks
- [ ] T2.1: Config SQLAlchemy models
- [ ] T2.2: Config repository
- [ ] T2.3: Config service
- [ ] T2.4: Config router
- [ ] T2.5: Config CRUD integration tests"

create_task "T2.1" "T2.1: Config SQLAlchemy models" \
  "Create config_values and config_versions tables per docs/ARCHITECTURE.md. Unique constraint on (namespace, key)." "E2" "role:engineer"

create_task "T2.2" "T2.2: Config repository" \
  "Implement async data access layer with get/set/delete/list_by_namespace methods. set creates version row on every write." "E2" "role:engineer"

create_task "T2.3" "T2.3: Config service" \
  "Business logic: validate value types, create versions, update current_version_id, publish change events to watch bus." "E2" "role:engineer"

create_task "T2.4" "T2.4: Config router" \
  "FastAPI router: PUT/GET/DELETE /config/{namespace}/{key}, GET /config/{namespace}. Proper status codes and auth scope enforcement." "E2" "role:engineer"

create_task "T2.5" "T2.5: Config CRUD integration tests" \
  "Full test suite: CRUD happy paths, 404s, pagination, concurrent writes. Coverage >90%." "E2" "role:qa"

# E3: Auth & API Keys
create_epic "E3" "Epic E3: Auth & API Keys" \
  "Secure the API with bearer-token authentication backed by API keys stored in the database.

## Tasks
- [ ] T3.1: API key model
- [ ] T3.2: Key management service
- [ ] T3.3: Auth middleware
- [ ] T3.4: Key management router
- [ ] T3.5: Auth integration tests"

create_task "T3.1" "T3.1: API key model" \
  "Create api_keys table with key_hash, key_prefix, scopes_json, revoked_at." "E3" "role:engineer"

create_task "T3.2" "T3.2: Key management service" \
  "Create/generate/validate/revoke API keys. Keys formatted as fc_live_<hex>. SHA-256 hash storage. Constant-time comparison." "E3" "role:engineer"

create_task "T3.3" "T3.3: Auth middleware" \
  "FastAPI dependency: extract Bearer token, validate against DB, inject actor + scopes into request state. 401/403 handling." "E3" "role:engineer"

create_task "T3.4" "T3.4: Key management router" \
  "POST/GET/DELETE /keys endpoints. Admin-only scope enforcement." "E3" "role:engineer"

create_task "T3.5" "T3.5: Auth integration tests" \
  "Test full auth lifecycle: create key, auth request, scope enforcement, revoke, invalid token." "E3" "role:qa"

# E4: Versioning & Audit Log
create_epic "E4" "Epic E4: Versioning & Audit Log" \
  "Provide full change history and an audit trail for compliance and debugging.

## Tasks
- [ ] T4.1: Audit log model
- [ ] T4.2: Version history service
- [ ] T4.3: History endpoint
- [ ] T4.4: Audit log endpoint
- [ ] T4.5: Versioning + audit tests"

create_task "T4.1" "T4.1: Audit log model" \
  "Create audit_log table with actor, action, resource_type, resource_id, detail_json." "E4" "role:engineer"

create_task "T4.2" "T4.2: Version history service" \
  "Auto-create version row on every config write. Query history with cursor pagination." "E4" "role:engineer"

create_task "T4.3" "T4.3: History endpoint" \
  "GET /config/{namespace}/{key}/history with cursor pagination. Requires config:read scope." "E4" "role:engineer"

create_task "T4.4" "T4.4: Audit log endpoint" \
  "GET /audit with filters (actor, action, resource_type, date range). Admin-only." "E4" "role:engineer"

create_task "T4.5" "T4.5: Versioning + audit tests" \
  "Verify version increments, history ordering, audit log completeness." "E4" "role:qa"

# E5: Feature Flags
create_epic "E5" "Epic E5: Feature Flags" \
  "Implement the feature-flag engine with rollout percentage and rule-based evaluation.

## Tasks
- [ ] T5.1: Feature flag model
- [ ] T5.2: Flag repository + service
- [ ] T5.3: Flag evaluation engine
- [ ] T5.4: Flag router
- [ ] T5.5: Flag evaluation tests
- [ ] T5.6: Flag concurrency tests"

create_task "T5.1" "T5.1: Feature flag model" \
  "Create feature_flags table with name, enabled, rollout_percentage (0-100), rules_json." "E5" "role:engineer"

create_task "T5.2" "T5.2: Flag repository + service" \
  "CRUD for flag definitions. Validate rules_json structure on write." "E5" "role:engineer"

create_task "T5.3" "T5.3: Flag evaluation engine" \
  "Deterministic hash bucketing (sha256(user_id+flag_name) mod 100). Allowlist, rollout, attribute rules. Priority: disabled < allowlist < rollout < attribute." "E5" "role:engineer"

create_task "T5.4" "T5.4: Flag router" \
  "PUT/GET/DELETE /flags/{name}, GET /flags list. Evaluation via GET /flags/{name}?user_id=..." "E5" "role:engineer"

create_task "T5.5" "T5.5: Flag evaluation tests" \
  "Edge cases: 0%/100% rollout, boundary values, allowlist priority, attribute rules, determinism." "E5" "role:qa"

create_task "T5.6" "T5.6: Flag concurrency tests" \
  "Concurrent updates, read-after-write consistency, delete during evaluation." "E5" "role:qa"

# E6: Watch / SSE
create_epic "E6" "Epic E6: Watch / SSE" \
  "Provide real-time streaming API so clients can react to config changes instantly.

## Tasks
- [ ] T6.1: Event bus
- [ ] T6.2: SSE endpoint
- [ ] T6.3: Reconnect support
- [ ] T6.4: Watch integration tests"

create_task "T6.1" "T6.1: Event bus" \
  "In-process asyncio pub/sub for config change events. asyncio.Queue per subscriber. Queue max 100, drop oldest." "E6" "role:engineer"

create_task "T6.2" "T6.2: SSE endpoint" \
  "GET /watch/{namespace} returning text/event-stream. 30s heartbeat. Clean disconnect handling." "E6" "role:engineer"

create_task "T6.3" "T6.3: Reconnect support" \
  "Last-Event-ID header processing. Replay missed events from version history. config.resync for large gaps." "E6" "role:engineer"

create_task "T6.4" "T6.4: Watch integration tests" \
  "Event delivery, multiple subscribers, heartbeat, disconnect/reconnect, namespace isolation." "E6" "role:qa"

# E7: Python Client SDK
create_epic "E7" "Epic E7: Python Client SDK" \
  "Ship an idiomatic, type-safe Python client.

## Tasks
- [ ] T7.1: SDK package structure
- [ ] T7.2: Config client methods
- [ ] T7.3: Flag client methods
- [ ] T7.4: Watch client
- [ ] T7.5: Error handling + retries
- [ ] T7.6: SDK tests"

create_task "T7.1" "T7.1: SDK package structure" \
  "fleet_config client package. Client class, py.typed, __all__ exports." "E7" "role:engineer"

create_task "T7.2" "T7.2: Config client methods" \
  "get/set/delete/list/history methods with typed Pydantic response models." "E7" "role:engineer"

create_task "T7.3" "T7.3: Flag client methods" \
  "create/check/get/delete/list with FlagEvaluation response including reason." "E7" "role:engineer"

create_task "T7.4" "T7.4: Watch client" \
  "SSE iterator with auto-reconnect. for event in client.watch(ns): ..." "E7" "role:engineer"

create_task "T7.5" "T7.5: Error handling + retries" \
  "Custom exception hierarchy. Exponential backoff with jitter on 429/5xx." "E7" "role:engineer"

create_task "T7.6" "T7.6: SDK tests" \
  "Mock-based unit tests + integration tests against live service." "E7" "role:qa"

# E8: Deploy & Observability
create_epic "E8" "Epic E8: Deploy & Observability" \
  "Make the service one-command deployable and production-ready with CI.

## Tasks
- [ ] T8.1: Dockerfile
- [ ] T8.2: docker-compose
- [ ] T8.3: GitHub Actions CI
- [ ] T8.4: Structured logging
- [ ] T8.5: Smoke test suite"

create_task "T8.1" "T8.1: Dockerfile" \
  "Multi-stage build, non-root user, EXPOSE 8080, healthcheck. Image <150MB." "E8" "role:devops"

create_task "T8.2" "T8.2: docker-compose" \
  "Service definition with volume mount for SQLite, env config, healthcheck." "E8" "role:devops"

create_task "T8.3" "T8.3: GitHub Actions CI" \
  "Workflow on PR: lint (ruff), typecheck (mypy), test (pytest), build (docker)." "E8" "role:devops"

create_task "T8.4" "T8.4: Structured logging" \
  "structlog JSON output. Request-ID middleware. LOG_LEVEL env var." "E8" "role:devops"

create_task "T8.5" "T8.5: Smoke test suite" \
  "E2E: start compose, full workflow, assert results. Clean teardown." "E8" "role:qa"

echo ""
echo "--- Issues created ---"
echo "Epics:"
for key in E1 E2 E3 E4 E5 E6 E7 E8; do
  echo "  $key: #${EPIC_NUMBERS[$key]}"
done
echo ""
echo "Tasks:"
for key in "${!TASK_NUMBERS[@]}"; do
  echo "  $key: #${TASK_NUMBERS[$key]}"
done

# ──────────────────────────────────────────────
# Phase 4: Create agent-service workspace
# ──────────────────────────────────────────────
echo ""
echo "--- Phase 4: Creating agent-service workspace ---"

# First fetch agent-roles to get ref strings
ROLES_JSON=$(curl -s "${AGENT_SERVICE}/api/v1/agent-roles")
echo "Agent roles fetched."

# Extract role refs
ROLE_SUPERVISOR_REF=$(echo "$ROLES_JSON" | python3 -c "import sys,json; data=json.load(sys.stdin); [print(r['ref']) for r in data if r.get('name','')=='Multi-Agent Supervisor']" | head -1)
ROLE_PORTFOLIO_REF=$(echo "$ROLES_JSON" | python3 -c "import sys,json; data=json.load(sys.stdin); [print(r['ref']) for r in data if r.get('name','')=='Portfolio Manager']" | head -1)
ROLE_CTO_REF=$(echo "$ROLES_JSON" | python3 -c "import sys,json; data=json.load(sys.stdin); [print(r['ref']) for r in data if r.get('name','')=='CTO/Systems Architect']" | head -1)
ROLE_UX_REF=$(echo "$ROLES_JSON" | python3 -c "import sys,json; data=json.load(sys.stdin); [print(r['ref']) for r in data if r.get('name','')=='UX Architect/Interaction Designer']" | head -1)
ROLE_FACTORY_REF=$(echo "$ROLES_JSON" | python3 -c "import sys,json; data=json.load(sys.stdin); [print(r['ref']) for r in data if r.get('name','')=='Software Factory']" | head -1)
ROLE_DEVOPS_REF=$(echo "$ROLES_JSON" | python3 -c "import sys,json; data=json.load(sys.stdin); [print(r['ref']) for r in data if r.get('name','')=='DevOps/SRE/Platform Engineer']" | head -1)
ROLE_QA_REF=$(echo "$ROLES_JSON" | python3 -c "import sys,json; data=json.load(sys.stdin); [print(r['ref']) for r in data if r.get('name','')=='QA Engineer/Test Architect']" | head -1)
ROLE_REVIEWER_REF=$(echo "$ROLES_JSON" | python3 -c "import sys,json; data=json.load(sys.stdin); [print(r['ref']) for r in data if r.get('name','')=='Adversarial Reviewer']" | head -1)

echo "Role refs:"
echo "  Supervisor: $ROLE_SUPERVISOR_REF"
echo "  Portfolio:  $ROLE_PORTFOLIO_REF"
echo "  CTO:        $ROLE_CTO_REF"
echo "  UX:         $ROLE_UX_REF"
echo "  Factory:    $ROLE_FACTORY_REF"
echo "  DevOps:     $ROLE_DEVOPS_REF"
echo "  QA:         $ROLE_QA_REF"
echo "  Reviewer:   $ROLE_REVIEWER_REF"

WS_RESPONSE=$(curl -s -X POST "${AGENT_SERVICE}/workspaces" \
  -H 'Content-Type: application/json' \
  -d "{\"name\": \"fleet-config\", \"git_repo\": \"${REPO_URL}.git\"}")
WS_ID=$(echo "$WS_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Workspace created: id=${WS_ID}"

# ──────────────────────────────────────────────
# Phase 5: Create 10 threads
# ──────────────────────────────────────────────
echo ""
echo "--- Phase 5: Creating threads ---"

create_thread() {
  local name=$1 template_id=$2
  local response
  response=$(curl -s -X POST "${AGENT_SERVICE}/threads" \
    -H 'Content-Type: application/json' \
    -d "{\"workspace_id\": ${WS_ID}, \"agent_template_id\": ${template_id}, \"name\": \"${name}\"}")
  local thread_id=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  echo "$thread_id"
}

THREAD_PM=$(create_thread "pm-orchestrator" 19)
THREAD_PLANNER=$(create_thread "planner-product" 15)
THREAD_ARCHITECT=$(create_thread "architect-cto" 11)
THREAD_DESIGNER=$(create_thread "designer-ux" 21)
THREAD_CORE_API=$(create_thread "engineer-core-api" 18)
THREAD_FLAGS=$(create_thread "engineer-flags" 18)
THREAD_SDK_WATCH=$(create_thread "engineer-sdk-watch" 18)
THREAD_QA=$(create_thread "qa-test" 18)
THREAD_DEVOPS=$(create_thread "devops-deploy" 7)
THREAD_REVIEWER=$(create_thread "reviewer-adversarial" 1)

echo "Threads created:"
echo "  pm-orchestrator:      $THREAD_PM"
echo "  planner-product:      $THREAD_PLANNER"
echo "  architect-cto:        $THREAD_ARCHITECT"
echo "  designer-ux:          $THREAD_DESIGNER"
echo "  engineer-core-api:    $THREAD_CORE_API"
echo "  engineer-flags:       $THREAD_FLAGS"
echo "  engineer-sdk-watch:   $THREAD_SDK_WATCH"
echo "  qa-test:              $THREAD_QA"
echo "  devops-deploy:        $THREAD_DEVOPS"
echo "  reviewer-adversarial: $THREAD_REVIEWER"

# ──────────────────────────────────────────────
# Phase 6: Kick off PM thread
# ──────────────────────────────────────────────
echo ""
echo "--- Phase 6: Kicking off PM thread ---"

# Build epic issue number list for the PM prompt
EPIC_LIST=""
for key in E1 E2 E3 E4 E5 E6 E7 E8; do
  EPIC_LIST="${EPIC_LIST}  ${key}: #${EPIC_NUMBERS[$key]}
"
done

PM_PROMPT="You are the Project Manager / Orchestrator for **fleet-config**, a centralized config + feature-flag service. You own this project end-to-end.

## Your Team

You have 9 team members, each running in their own thread:

| Thread | ID | Role | Owns |
|--------|----|------|------|
| planner-product | ${THREAD_PLANNER} | Portfolio Manager | PRD, story breakdown, backlog grooming |
| architect-cto | ${THREAD_ARCHITECT} | CTO/Systems Architect | Architecture decisions, data model, tech choices |
| designer-ux | ${THREAD_DESIGNER} | UX Architect/Interaction Designer | API/CLI UX, SDK ergonomics, error-message design |
| engineer-core-api | ${THREAD_CORE_API} | Software Factory | Core config CRUD + storage layer + auth middleware |
| engineer-flags | ${THREAD_FLAGS} | Software Factory | Feature-flag engine, rollout logic, rule evaluation |
| engineer-sdk-watch | ${THREAD_SDK_WATCH} | Software Factory | Python client SDK + SSE watch endpoint |
| qa-test | ${THREAD_QA} | QA Engineer/Test Architect | Test plan, pytest suite, integration + E2E tests |
| devops-deploy | ${THREAD_DEVOPS} | DevOps/SRE/Platform Engineer | Dockerfile, compose, GitHub Actions CI |
| reviewer-adversarial | ${THREAD_REVIEWER} | Adversarial Reviewer | Code review on every PR |

## GitHub Repo

${REPO_URL}

### Epic Issue Numbers
${EPIC_LIST}

## Your Standing Directives

1. **Maintain the backlog.** Keep issues up-to-date. Close tasks when PRs land. Update epic status.
2. **Assign tasks to engineer threads** by posting to \`/threads/{id}/messages\` with a clear task brief + linked issue number.
3. **Gate engineering work** on the Architect + Designer completing their opening artifacts first. Do NOT dispatch engineering tasks until the Architect's ADRs and the Designer's UX doc have been reviewed and merged.
4. **Require the Reviewer** to be CC'd on every PR via issue comment. Tag the reviewer thread on every PR that needs review.
5. **Require QA to write tests alongside engineering.** Each task should produce both implementation + tests.
6. **Report status** by writing to the \`pm-status\` log whenever asked.
7. **Use \`gh\` CLI** for all GitHub interactions (creating branches, opening PRs, commenting, closing issues).

## Execution Phases

**Phase 1 (Immediate):** Have the Architect produce final architecture decisions (ADRs). Have the Planner produce story breakdown of E1–E3. Have the Designer produce UX doc.

**Phase 2 (After Phase 1 lands):** Kick off E1 scaffolding work with engineer-core-api. Then dispatch E2 + E3 in parallel once scaffolding lands.

**Phase 3 (After E1–E3):** Dispatch E4, E5, E6 in parallel.

**Phase 4 (After E5–E6):** Dispatch E7 (SDK) and E8 (Deploy).

Go."

RUN_PM=$(curl -s -X POST "${AGENT_SERVICE}/threads/${THREAD_PM}/runs" \
  -H 'Content-Type: application/json' \
  -d "{\"provider\": \"local\", \"input\": {\"prompt\": $(echo "$PM_PROMPT" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}, \"role\": \"${ROLE_SUPERVISOR_REF}\"}")
RUN_PM_ID=$(echo "$RUN_PM" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "PM run dispatched: run #${RUN_PM_ID}"

# ──────────────────────────────────────────────
# Phase 7: Kick off Planner, Architect, Designer
# ──────────────────────────────────────────────
echo ""
echo "--- Phase 7: Kicking off Planner, Architect, Designer ---"

PLANNER_PROMPT="Read docs/PRD.md, docs/BACKLOG.md, docs/ROADMAP.md from the workspace repo. Produce docs/STORIES.md with each epic (E1–E8) broken into INVEST-compliant user stories. Each story should have: ID, title, as-a/I-want/so-that, acceptance criteria, points estimate. Open a PR titled 'docs: story breakdown' for review."

RUN_PLANNER=$(curl -s -X POST "${AGENT_SERVICE}/threads/${THREAD_PLANNER}/runs" \
  -H 'Content-Type: application/json' \
  -d "{\"provider\": \"local\", \"input\": {\"prompt\": $(echo "$PLANNER_PROMPT" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}, \"role\": \"${ROLE_PORTFOLIO_REF}\"}")
RUN_PLANNER_ID=$(echo "$RUN_PLANNER" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Planner run dispatched: run #${RUN_PLANNER_ID}"

ARCHITECT_PROMPT="Read docs/ARCHITECTURE.md and docs/API.md from the workspace repo. Produce three Architecture Decision Records:
1. docs/ADR/0001-storage-abstraction.md — Context: SQLite now, postgres later. Decision: SQLAlchemy async with repository pattern. Consequences.
2. docs/ADR/0002-auth-model.md — Context: simple API keys. Decision: bearer tokens with hashed storage, scope-based access. Consequences.
3. docs/ADR/0003-flag-rollout-hashing.md — Context: deterministic rollout. Decision: SHA-256 bucket hash. Consequences: consistency vs redistribution.

Each ADR should have: Status (Proposed), Context, Decision, Consequences.
Open a PR titled 'docs: initial ADRs' for review."

RUN_ARCHITECT=$(curl -s -X POST "${AGENT_SERVICE}/threads/${THREAD_ARCHITECT}/runs" \
  -H 'Content-Type: application/json' \
  -d "{\"provider\": \"local\", \"input\": {\"prompt\": $(echo "$ARCHITECT_PROMPT" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}, \"role\": \"${ROLE_CTO_REF}\"}")
RUN_ARCHITECT_ID=$(echo "$RUN_ARCHITECT" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Architect run dispatched: run #${RUN_ARCHITECT_ID}"

DESIGNER_PROMPT="Read docs/API.md and docs/SDK.md from the workspace repo. Produce docs/UX.md covering:
1. API error-response shape and taxonomy (machine-readable codes, human-readable messages)
2. CLI ergonomics for the Python SDK (method naming, parameter conventions, context manager patterns)
3. Idiomatic Python usage patterns (with-examples, type hints, Pydantic models)
4. Error code catalog with suggested remediation messages

Open a PR titled 'docs: UX and API design guide' for review."

RUN_DESIGNER=$(curl -s -X POST "${AGENT_SERVICE}/threads/${THREAD_DESIGNER}/runs" \
  -H 'Content-Type: application/json' \
  -d "{\"provider\": \"local\", \"input\": {\"prompt\": $(echo "$DESIGNER_PROMPT" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}, \"role\": \"${ROLE_UX_REF}\"}")
RUN_DESIGNER_ID=$(echo "$RUN_DESIGNER" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Designer run dispatched: run #${RUN_DESIGNER_ID}"

# ──────────────────────────────────────────────
# Phase 8: Final summary + state file
# ──────────────────────────────────────────────
echo ""
echo "========================================="
echo "=== fleet-config Swarm — Final Summary ==="
echo "========================================="
echo ""
echo "repo:      ${REPO_URL}"
echo "workspace: ${WS_ID}"
echo ""
echo "threads:"
echo "  pm-orchestrator:       ${THREAD_PM}  (template 19, role Multi-Agent Supervisor)"
echo "  planner-product:       ${THREAD_PLANNER}  (template 15, role Portfolio Manager)"
echo "  architect-cto:         ${THREAD_ARCHITECT}  (template 11, role CTO/Systems Architect)"
echo "  designer-ux:           ${THREAD_DESIGNER}  (template 21, role UX Architect)"
echo "  engineer-core-api:     ${THREAD_CORE_API}  (template 18, role Software Factory)"
echo "  engineer-flags:        ${THREAD_FLAGS}  (template 18, role Software Factory)"
echo "  engineer-sdk-watch:    ${THREAD_SDK_WATCH}  (template 18, role Software Factory)"
echo "  qa-test:               ${THREAD_QA}  (template 18, role QA Engineer)"
echo "  devops-deploy:         ${THREAD_DEVOPS}  (template 7, role DevOps/SRE)"
echo "  reviewer-adversarial:  ${THREAD_REVIEWER}  (template 1, role Adversarial Reviewer)"
echo ""
echo "issues:"
for key in E1 E2 E3 E4 E5 E6 E7 E8; do
  echo "  ${key}: #${EPIC_NUMBERS[$key]}"
done
echo ""
echo "opening runs:"
echo "  pm:        run #${RUN_PM_ID}    (standing manager brief)"
echo "  planner:   run #${RUN_PLANNER_ID}    (story breakdown)"
echo "  architect: run #${RUN_ARCHITECT_ID}    (ADRs)"
echo "  designer:  run #${RUN_DESIGNER_ID}    (UX doc)"
echo ""

# Persist state
mkdir -p /home/zazula/operator/state
python3 -c "
import json

state = {
    'repo': '${REPO_URL}',
    'workspace_id': ${WS_ID},
    'threads': {
        'pm-orchestrator': ${THREAD_PM},
        'planner-product': ${THREAD_PLANNER},
        'architect-cto': ${THREAD_ARCHITECT},
        'designer-ux': ${THREAD_DESIGNER},
        'engineer-core-api': ${THREAD_CORE_API},
        'engineer-flags': ${THREAD_FLAGS},
        'engineer-sdk-watch': ${THREAD_SDK_WATCH},
        'qa-test': ${THREAD_QA},
        'devops-deploy': ${THREAD_DEVOPS},
        'reviewer-adversarial': ${THREAD_REVIEWER}
    },
    'epics': {k: int(v) for k, v in {
$(for key in E1 E2 E3 E4 E5 E6 E7 E8; do echo "        '${key}': '${EPIC_NUMBERS[$key]}',"; done)
    }.items()},
    'opening_runs': {
        'pm': ${RUN_PM_ID},
        'planner': ${RUN_PLANNER_ID},
        'architect': ${RUN_ARCHITECT_ID},
        'designer': ${RUN_DESIGNER_ID}
    }
}

with open('/home/zazula/operator/state/fleet-config-swarm.json', 'w') as f:
    json.dump(state, f, indent=2)
print('State persisted to /home/zazula/operator/state/fleet-config-swarm.json')
"

echo ""
echo "=== Bootstrap complete ==="
