# fleet-config API Reference

**Base URL:** `https://fleet.example.com/api/v1`

**Content-Type:** `application/json` for all requests and responses unless otherwise noted.

**Authentication:** All endpoints except `/health` require a Bearer token. Tokens are prefixed with `fc_live_` followed by 64 hexadecimal characters.

**Version:** This document describes API version 1.

---

## Table of Contents

1. [Common Conventions](#1-common-conventions)
2. [Config CRUD](#2-config-crud)
   - [PUT /config/{namespace}/{key}](#put-confignamespacekey)
   - [GET /config/{namespace}/{key}](#get-confignamespacekey)
   - [DELETE /config/{namespace}/{key}](#delete-confignamespacekey)
   - [GET /config/{namespace}](#get-confignamespace)
   - [GET /config/{namespace}/{key}/history](#get-confignamespacekeyhistory)
3. [Feature Flags](#3-feature-flags)
   - [PUT /flags/{name}](#put-flagsname)
   - [GET /flags/{name}](#get-flagsname)
   - [DELETE /flags/{name}](#delete-flagsname)
   - [GET /flags](#get-flags)
4. [Watch](#4-watch)
   - [GET /watch/{namespace}](#get-watchnamespace)
5. [API Key Management](#5-api-key-management)
   - [POST /keys](#post-keys)
   - [GET /keys](#get-keys)
   - [DELETE /keys/{id}](#delete-keysid)
6. [System](#6-system)
   - [GET /health](#get-health)
   - [GET /audit](#get-audit)

---

## 1. Common Conventions

### Authentication

All endpoints except `/health` require a Bearer token in the `Authorization` header.

```
Authorization: Bearer fc_live_<64 hex characters>
```

Example:
```bash
curl -H "Authorization: Bearer fc_live_a3f5b8c1..." https://fleet.example.com/api/v1/config/prod/database/host
```

Tokens are created via `POST /keys` and carry one or more scopes. Attempting to call an endpoint without a valid token yields `401 Unauthorized`. Attempting to call an endpoint with insufficient scope yields `403 Forbidden`.

### Common Error Shape

All error responses follow a consistent envelope:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description",
    "details": {}
  }
}
```

The `details` field is optional and may contain field-level validation errors or other structured context.

### Error Code Catalog

| Code | HTTP Status | Description |
|---|---|---|
| `CONFIG_NOT_FOUND` | 404 | Config key does not exist in the given namespace. |
| `FLAG_NOT_FOUND` | 404 | Feature flag does not exist. |
| `KEY_NOT_FOUND` | 404 | API key does not exist (or has already been revoked). |
| `UNAUTHORIZED` | 401 | Missing, malformed, or invalid Bearer token. |
| `FORBIDDEN` | 403 | Token exists but lacks the required scope for this endpoint. |
| `INVALID_SCOPE` | 400 | One or more requested scopes are not valid scope names. |
| `VALIDATION_ERROR` | 422 | Request body failed validation (missing fields, wrong types, invalid values). |
| `NAMESPACE_NOT_EMPTY` | 409 | Attempted to delete a namespace that still contains keys. |
| `INTERNAL_ERROR` | 500 | Unexpected server-side error. Safe to retry with back-off. |

### Pagination

List endpoints that return collections support cursor-based pagination via two query parameters:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `cursor` | string (optional) | — | Opaque pagination cursor returned in a previous response's `next_cursor` field. Pass `null` or omit to start at the beginning. |
| `limit` | integer | `50` | Maximum number of items to return. Must be between `1` and `500`. |

A paginated response looks like:

```json
{
  "data": [ ... ],
  "next_cursor": "eyJpZCI6IjEyMyJ9"
}
```

- If `next_cursor` is `null` or absent, the last page has been returned.
- To fetch the next page, repeat the request with the same `limit` and pass `cursor` with the value from `next_cursor`.

### Audit Context

Write operations (`PUT` and `DELETE`) record the following in the audit log: the actor (`sub` claim from the JWT), the action (`config.set`, `config.delete`, `flag.set`, `flag.delete`, `key.revoke`), the resource type and identifier, and a timestamp.

---

## 2. Config CRUD

### PUT /config/{namespace}/{key}

**Description:** Create a new config entry or replace an existing one atomically. If the key already exists its value and type are overwritten and the version counter is incremented.

**Auth scope required:** `config:write`

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `namespace` | string | Dot-separated logical grouping (e.g. `prod.database`). Max 128 chars. Must match `^[a-z0-9_\-\.]+$`. |
| `key` | string | Config key name. Max 256 chars. Must match `^[a-z0-9_\-]+$`. |

**Request body:**

```json
{
  "value": <any JSON-serializable value>,
  "type": "string | int | float | bool | json"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `value` | any | **Yes** | The config value. Must be JSON-serializable. |
| `type` | string | **Yes** | Declares the canonical type. Affects how the value is serialized on read. Use `json` for objects and arrays. |

**Request body examples:**

```
value: "localhost"
type: "string"
```

```json
{
  "value": "localhost",
  "type": "string"
}
```

```
value: 5432
type: "int"
```

```json
{
  "value": 5432,
  "type": "int"
}
```

```
value: {"pool_size": 10, "ssl": true}
type: "json"
```

```json
{
  "value": {
    "pool_size": 10,
    "ssl": true
  },
  "type": "json"
}
```

**Response `200 OK`:**

```json
{
  "namespace": "prod.database",
  "key": "host",
  "value": "localhost",
  "type": "string",
  "version": 3,
  "updated_at": "2024-11-01T14:22:33.456Z"
}
```

**Error responses:**

| Status | Error Code | Condition |
|---|---|---|
| `400` | `INVALID_SCOPE` | Authorization token lacks `config:write`. |
| `400` | `UNAUTHORIZED` | Missing or invalid Bearer token. |
| `422` | `VALIDATION_ERROR` | `namespace` or `key` fails the regex, or `type` is not one of the five allowed values. |

**Curl example:**

```bash
curl -X PUT https://fleet.example.com/api/v1/config/prod.database/host \
  -H "Authorization: Bearer fc_live_a3f5b8c1..." \
  -H "Content-Type: application/json" \
  -d '{"value": "db.example.com", "type": "string"}'
```

**Notes:**
- `namespace` is created implicitly on first key insertion; there is no separate create-Namespace call.
- Version starts at `1` on a new key and increments by `1` on every subsequent `PUT` to the same key.
- `updated_at` is an ISO 8601 timestamp in UTC.

---

### GET /config/{namespace}/{key}

**Description:** Retrieve the current value, type, version, and last-updated timestamp for a single config key.

**Auth scope required:** `config:read`

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `namespace` | string | Config namespace. |
| `key` | string | Config key name. |

**Request body:** None.

**Response `200 OK`:**

```json
{
  "namespace": "prod.database",
  "key": "host",
  "value": "db.example.com",
  "type": "string",
  "version": 3,
  "updated_at": "2024-11-01T14:22:33.456Z"
}
```

**Error responses:**

| Status | Error Code | Condition |
|---|---|---|
| `400` | `UNAUTHORIZED` | Missing or invalid Bearer token. |
| `403` | `FORBIDDEN` | Token lacks `config:read`. |
| `404` | `CONFIG_NOT_FOUND` | The `{namespace}/{key}` pair does not exist. |

**Curl example:**

```bash
curl https://fleet.example.com/api/v1/config/prod.database/host \
  -H "Authorization: Bearer fc_live_a3f5b8c1..."
```

**Notes:**
- The returned `value` is always the serialized JSON. Clients must interpret based on `type`.
- The response includes the full config object; no envelope wrapping is applied.

---

### DELETE /config/{namespace}/{key}

**Description:** Permanently delete a config key and its entire version history.

**Auth scope required:** `config:write`

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `namespace` | string | Config namespace. |
| `key` | string | Config key name. |

**Request body:** None.

**Response `204 No Content`**

No body is returned.

**Error responses:**

| Status | Error Code | Condition |
|---|---|---|
| `400` | `UNAUTHORIZED` | Missing or invalid Bearer token. |
| `403` | `FORBIDDEN` | Token lacks `config:write`. |
| `404` | `CONFIG_NOT_FOUND` | The key does not exist. |

**Curl example:**

```bash
curl -X DELETE https://fleet.example.com/api/v1/config/prod.database/host \
  -H "Authorization: Bearer fc_live_a3f5b8c1..."
```

**Notes:**
- This operation is idempotent: if the key does not exist the server returns `404`, not `204`.
- Version history is deleted along with the key and cannot be recovered.

---

### GET /config/{namespace}

**Description:** List all config keys within a namespace. Returns items in ascending key-name order. Supports prefix filtering and cursor-based pagination.

**Auth scope required:** `config:read`

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `namespace` | string | Config namespace. |

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `prefix` | string (optional) | — | Return only keys whose names start with this prefix. Match is case-sensitive. |
| `cursor` | string (optional) | — | Pagination cursor from a previous response. |
| `limit` | integer | `50` | Max items per page (`1`–`500`). |

**Request body:** None.

**Response `200 OK`:**

```json
{
  "data": [
    {
      "namespace": "prod.database",
      "key": "host",
      "value": "db.example.com",
      "type": "string",
      "version": 3,
      "updated_at": "2024-11-01T14:22:33.456Z"
    },
    {
      "namespace": "prod.database",
      "key": "port",
      "value": 5432,
      "type": "int",
      "version": 1,
      "updated_at": "2024-10-15T08:00:00.000Z"
    }
  ],
  "next_cursor": "eyJpZCI6InBvcnQifQ=="
}
```

**Error responses:**

| Status | Error Code | Condition |
|---|---|---|
| `400` | `UNAUTHORIZED` | Missing or invalid Bearer token. |
| `403` | `FORBIDDEN` | Token lacks `config:read`. |
| `422` | `VALIDATION_ERROR` | `limit` is out of range or `namespace` is invalid. |

**Curl examples:**

List all keys (no filter):
```bash
curl "https://fleet.example.com/api/v1/config/prod.database" \
  -H "Authorization: Bearer fc_live_a3f5b8c1..."
```

Filter by prefix:
```bash
curl "https://fleet.example.com/api/v1/config/prod.database?prefix=cache" \
  -H "Authorization: Bearer fc_live_a3f5b8c1..."
```

Paginate (second page):
```bash
curl "https://fleet.example.com/api/v1/config/prod.database?limit=25&cursor=eyJpZCI6InBvcnQifQ==" \
  -H "Authorization: Bearer fc_live_a3f5b8c1..."
```

**Notes:**
- If `next_cursor` is `null` the response is the last page.
- Combining `prefix` with pagination is supported; supply the same `prefix` on all page requests to ensure consistent cursor decoding.
- Empty namespace returns `{"data": [], "next_cursor": null}` (HTTP 200), not a 404.

---

### GET /config/{namespace}/{key}/history

**Description:** Return the version history for a config key. Each entry records the value, type, and timestamp at the time that version was written. Versions are returned in descending version-number order (newest first).

**Auth scope required:** `config:read`

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `namespace` | string | Config namespace. |
| `key` | string | Config key name. |

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `cursor` | string (optional) | — | Pagination cursor. |
| `limit` | integer | `50` | Max entries per page (`1`–`500`). |

**Request body:** None.

**Response `200 OK`:**

```json
{
  "versions": [
    {
      "version": 3,
      "value": "db.example.com",
      "type": "string",
      "updated_at": "2024-11-01T14:22:33.456Z"
    },
    {
      "version": 2,
      "value": "staging.db.example.com",
      "type": "string",
      "updated_at": "2024-10-20T11:00:00.000Z"
    },
    {
      "version": 1,
      "value": "localhost",
      "type": "string",
      "updated_at": "2024-10-01T09:00:00.000Z"
    }
  ],
  "next_cursor": null
}
```

**Error responses:**

| Status | Error Code | Condition |
|---|---|---|
| `400` | `UNAUTHORIZED` | Missing or invalid Bearer token. |
| `403` | `FORBIDDEN` | Token lacks `config:read`. |
| `404` | `CONFIG_NOT_FOUND` | The key does not exist. |

**Curl example:**

```bash
curl "https://fleet.example.com/api/v1/config/prod.database/host/history?limit=10" \
  -H "Authorization: Bearer fc_live_a3f5b8c1..."
```

**Notes:**
- History is immutable; old values cannot be restored through the API. This is by design.
- The `type` stored in each historical entry reflects the type declared at write time; it does not change if the key's current type is different.
- If `next_cursor` is `null`, all historical versions have been returned.

---

## 3. Feature Flags

### PUT /flags/{name}

**Description:** Create a new feature flag or update an existing one. The flag controls whether a feature is active for a given user based on the configured rules. If the flag already exists, the request replaces its entire definition (upsert semantics).

**Auth scope required:** `flags:write`

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `name` | string | Unique flag identifier. Max 128 chars. Must match `^[a-z0-9_\-]+$`. |

**Request body:**

```json
{
  "description": "Enable the new billing UI for beta users.",
  "enabled": true,
  "rollout_percentage": 50,
  "rules": [
    {
      "field": "user_id",
      "operator": "in",
      "values": ["alice", "bob"]
    },
    {
      "field": "tier",
      "operator": "eq",
      "value": "premium"
    }
  ]
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `description` | string | No | `""` | Human-readable description of the flag's purpose. |
| `enabled` | boolean | **Yes** | — | Master kill-switch. If `false`, evaluation always returns `{"enabled": false, "reason": "disabled"}` regardless of rules. |
| `rollout_percentage` | integer | No | `0` | Global rollout as an integer percentage `0–100`. Requests that match no rule evaluate deterministically against this percentage using a hash of `{name}:{user_id}`. |
| `rules` | array | No | `[]` | Ordered list of override rules evaluated top-to-bottom. First matching rule wins. |
| `rules[].field` | string | If `rules` present | — | Attribute name to evaluate against. Common values: `user_id`, `tier`, `country`, `plan`. |
| `rules[].operator` | string | If `rules` present | — | Comparison operator. Allowed values: `in`, `not_in`, `eq`, `neq`, `contains`, `starts_with`. |
| `rules[].value` | any | Conditional | — | Used with operators `eq`, `neq`, `contains`, `starts_with`. The value to compare against the attribute. |
| `rules[].values` | array | Conditional | — | Used only with `in` and `not_in`. Must be a non-empty JSON array. |

**Request body examples:**

Flag with a kill-switch but no rollout:
```json
{
  "description": "Kill-switch for the experimental payment flow.",
  "enabled": false,
  "rollout_percentage": 0,
  "rules": []
}
```

Flag with a 50% global rollout and no per-user rules:
```json
{
  "description": "Gradual rollout of the new checkout flow.",
  "enabled": true,
  "rollout_percentage": 50,
  "rules": []
}
```

Flag with rules (user in allow-list and a plan check):
```json
{
  "description": "Beta feature for premium and pro users.",
  "enabled": true,
  "rollout_percentage": 0,
  "rules": [
    {
      "field": "user_id",
      "operator": "in",
      "values": ["alice", "bob", "charlie"]
    },
    {
      "field": "plan",
      "operator": "eq",
      "value": "pro"
    }
  ]
}
```

**Response `200 OK`:**

```json
{
  "name": "new_checkout_flow",
  "description": "Gradual rollout of the new checkout flow.",
  "enabled": true,
  "rollout_percentage": 50,
  "rules": [],
  "created_at": "2024-11-01T10:00:00.000Z",
  "updated_at": "2024-11-01T14:22:33.456Z"
}
```

**Error responses:**

| Status | Error Code | Condition |
|---|---|---|
| `400` | `UNAUTHORIZED` | Missing or invalid Bearer token. |
| `403` | `FORBIDDEN` | Token lacks `flags:write`. |
| `422` | `VALIDATION_ERROR` | `name` fails the regex; `rollout_percentage` is outside `0–100`; an unknown `operator` is supplied; or a rule is missing required fields. |

**Curl example:**

```bash
curl -X PUT https://fleet.example.com/api/v1/flags/new_checkout_flow \
  -H "Authorization: Bearer fc_live_a3f5b8c1..." \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Gradual rollout of the new checkout flow.",
    "enabled": true,
    "rollout_percentage": 50,
    "rules": []
  }'
```

**Notes:**
- Flag names are globally unique. Creating a flag with a duplicate name replaces the existing definition entirely.
- `rollout_percentage` and `rules` are independent; both can be configured simultaneously. The rollout applies only to requests that do not match any rule.
- The server does not validate that `field` names correspond to any known user attribute schema. Clients must supply whatever attributes are needed at evaluation time.

---

### GET /flags/{name}

**Description:** Evaluate a feature flag for a given user and return the resulting decision (`enabled` boolean and `reason` string). This endpoint is intended for real-time gate decisions in application code and is not used to retrieve flag definitions.

**Auth scope required:** `flags:read`

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `name` | string | Feature flag name. |

**Query parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `user_id` | string | **Yes** | The target user identifier used for rule matching and the rollout hash. Must be non-empty. |
| `attributes` | string (JSON object) | No | A JSON-encoded object of additional user attributes for rule evaluation, e.g. `{"tier":"premium","country":"US"}`. URL-encode the JSON string before passing. |

**Request body:** None.

**Response `200 OK`:**

```json
{
  "flag": "new_checkout_flow",
  "enabled": true,
  "reason": "rollout"
}
```

**Possible `reason` values:**

| Reason | Meaning |
|---|---|
| `disabled` | The flag's `enabled` field is `false`. |
| `rule_match` | A user-level rule matched; see the flag definition for which rule applied. |
| `rollout` | No rule matched; the decision was made by the rollout percentage. |
| `not_found` | **Returned only if the flag does not exist** — not an error HTTP status. |

**Error responses:**

| Status | Error Code | Condition |
|---|---|---|
| `400` | `UNAUTHORIZED` | Missing or invalid Bearer token. |
| `403` | `FORBIDDEN` | Token lacks `flags:read`. |
| `422` | `VALIDATION_ERROR` | `user_id` is missing or empty; or `attributes` is present but is not valid JSON. |

**Curl examples:**

Minimal request (only `user_id`):
```bash
curl "https://fleet.example.com/api/v1/flags/new_checkout_flow?user_id=bob" \
  -H "Authorization: Bearer fc_live_a3f5b8c1..."
```

With additional attributes:
```bash
curl "https://fleet.example.com/api/v1/flags/new_checkout_flow?user_id=bob&attributes=%7B%22tier%22%3A%22premium%22%7D" \
  -H "Authorization: Bearer fc_live_a3f5b8c1..."
```

**Notes:**
- This is an evaluation endpoint, not a retrieval endpoint. It always returns a decision, even if the flag does not exist (`reason: "not_found"`).
- The `user_id` is hashed with the flag name to produce a deterministic rollout result for a given user across any server instance.
- `attributes` is accepted as a URL-encoded JSON string (because JSON itself contains characters that conflict with URL query syntax). The `Content-Type` header is still `application/json` for this endpoint because the query string carries the data.
- For users without a defined `user_id` (e.g. anonymous sessions), supply a stable anonymous identifier as `user_id` (for example a session UUID) to maintain consistent rollout behavior.

---

### DELETE /flags/{name}

**Description:** Permanently delete a feature flag. This cannot be undone.

**Auth scope required:** `flags:write`

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `name` | string | Feature flag name. |

**Request body:** None.

**Response `204 No Content`**

No body is returned.

**Error responses:**

| Status | Error Code | Condition |
|---|---|---|
| `400` | `UNAUTHORIZED` | Missing or invalid Bearer token. |
| `403` | `FORBIDDEN` | Token lacks `flags:write`. |
| `404` | `FLAG_NOT_FOUND` | The flag does not exist. |

**Curl example:**

```bash
curl -X DELETE https://fleet.example.com/api/v1/flags/new_checkout_flow \
  -H "Authorization: Bearer fc_live_a3f5b8c1..."
```

**Notes:**
- Deleting a flag does not affect audit log records; the deletion event is itself audited.
- After deletion, `GET /flags/{name}` returns `reason: "not_found"` instead of `FLAG_NOT_FOUND` because the evaluation endpoint operates differently from the CRUD endpoints.

---

### GET /flags

**Description:** List all feature flags with their full definitions. This endpoint does not perform evaluation; it returns the stored configuration for each flag. Results are sorted alphabetically by `name`.

**Auth scope required:** `flags:read`

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `cursor` | string (optional) | — | Pagination cursor. |
| `limit` | integer | `50` | Max flags per page (`1`–`500`). |

**Request body:** None.

**Response `200 OK`:**

```json
{
  "data": [
    {
      "name": "dark_mode",
      "description": "Enable dark mode UI.",
      "enabled": true,
      "rollout_percentage": 100,
      "rules": [],
      "created_at": "2024-09-01T00:00:00.000Z",
      "updated_at": "2024-09-01T00:00:00.000Z"
    },
    {
      "name": "new_checkout_flow",
      "description": "Gradual rollout of the new checkout flow.",
      "enabled": true,
      "rollout_percentage": 50,
      "rules": [],
      "created_at": "2024-11-01T10:00:00.000Z",
      "updated_at": "2024-11-01T14:22:33.456Z"
    }
  ],
  "next_cursor": null
}
```

**Error responses:**

| Status | Error Code | Condition |
|---|---|---|
| `400` | `UNAUTHORIZED` | Missing or invalid Bearer token. |
| `403` | `FORBIDDEN` | Token lacks `flags:read`. |
| `422` | `VALIDATION_ERROR` | `limit` is out of range. |

**Curl example:**

```bash
curl "https://fleet.example.com/api/v1/flags?limit=25" \
  -H "Authorization: Bearer fc_live_a3f5b8c1..."
```

**Notes:**
- This is a definition listing endpoint; evaluation results are obtained from `GET /flags/{name}`.
- The `rules` array is returned in its stored order, which is the evaluation priority order (top-to-bottom).

---

## 4. Watch

### GET /watch/{namespace}

**Description:** Establish a Server-Sent Events (SSE) stream for a namespace. The server pushes events whenever a config key in that namespace is created, updated, or deleted. This enables real-time cache invalidation and event-driven architectures.

**Auth scope required:** `config:read`

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `namespace` | string | Config namespace to watch. |

**Request headers:**

| Header | Required | Value |
|---|---|---|
| `Accept` | **Yes** | `text/event-stream` |

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| `Last-Event-ID` | No | The event ID of the last event received by the client. The server will replay any missed events from its buffer. If omitted, the stream starts fresh from the current state. |

**Event format:**

Each pushed event follows the SSE standard:

```
id: <event_id>
event: <event_type>
data: <json_payload>

```

**Event types:**

| `event` field | Triggered when | Typical `data` payload |
|---|---|---|
| `config.changed` | A config key was created or updated. | `{"namespace": "...", "key": "...", "version": N}` |
| `config.deleted` | A config key was deleted. | `{"namespace": "...", "key": "...", "version": null}` |

**Example raw SSE stream:**

```
id: 42
event: config.changed
data: {"namespace": "prod.database", "key": "host", "version": 4}

id: 43
event: config.deleted
data: {"namespace": "prod.database", "key": "port", "version": null}

```

**Response `200 OK`** (with `Content-Type: text/event-stream`):

Byte stream of SSE frames. The connection is long-lived. The server sends a periodic `: keepalive\n\n` comment every 30 seconds to prevent proxy timeouts. The client must handle connection drops and reconnect using the `Last-Event-ID` header to resume from the last seen event.

**Error responses:**

| Status | Error Code | Condition |
|---|---|---|
| `400` | `UNAUTHORIZED` | Missing or invalid Bearer token. |
| `403` | `FORBIDDEN` | Token lacks `config:read`. |
| `400` | `VALIDATION_ERROR` | `Accept` header is not `text/event-stream`. |

**Curl example:**

```bash
curl -N "https://fleet.example.com/api/v1/watch/prod.database" \
  -H "Authorization: Bearer fc_live_a3f5b8c1..." \
  -H "Accept: text/event-stream"
```

**Notes:**
- SSE is a one-way push channel. The server never reads data from the client over this connection.
- Clients should terminate the stream gracefully on application shutdown. The server cleans up the connection when the client disconnects.
- The server buffers the last 1,000 events per namespace. If a client disconnects for longer than the buffer window, some events may be permanently lost and will not be replayed on reconnect.
- `Last-Event-ID` is the numeric `id` field from the most recently processed SSE event. On reconnect, pass it as a query parameter (e.g. `/watch/prod.database?Last-Event-ID=42`) or as an HTTP header (`Last-Event-ID: 42`). Both forms are supported.
- SSE events are identified by a monotonically increasing integer `id`. Deleted-key events have `version: null` in their data payload.

---

## 5. API Key Management

API keys grant programmatic access to fleet-config. They are created and revoked by administrators. All endpoints in this section require the `admin` scope.

### POST /keys

**Description:** Generate a new API key with the specified name and scopes. The `key` field is returned only once, at creation time. Store it securely — it cannot be retrieved again.

**Auth scope required:** `admin`

**Request body:**

```json
{
  "name": "ci-deploy-key",
  "scopes": ["config:read", "config:write", "flags:read"]
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | **Yes** | — | Human-readable label for the key (e.g. "CI deploy bot"). Must be unique. Max 128 chars. |
| `scopes` | array of strings | **Yes** | — | Ordered list of scopes to grant. Duplicates are ignored. Valid scopes: `config:read`, `config:write`, `flags:read`, `flags:write`, `admin`. |

**Request body example:**

```json
{
  "name": "ci-deploy-key",
  "scopes": ["config:read", "config:write", "flags:read"]
}
```

**Response `201 Created`:**

```json
{
  "id": "key_01j8x9b3c4d5e6f7g8h9i0j",
  "name": "ci-deploy-key",
  "key": "fc_live_a3f5b8c1d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0",
  "scopes": ["config:read", "config:write", "flags:read"],
  "created_at": "2024-11-01T12:00:00.000Z"
}
```

The `key` field is a `bcrypt`-prefixed string prefixed with `fc_live_`. Use the full string as the Bearer token.

**Error responses:**

| Status | Error Code | Condition |
|---|---|---|
| `400` | `UNAUTHORIZED` | Missing or invalid Bearer token. |
| `403` | `FORBIDDEN` | Token lacks `admin`. |
| `409` | `VALIDATION_ERROR` | A key with the same `name` already exists. |
| `422` | `VALIDATION_ERROR` | One or more elements in `scopes` are not valid scope identifiers. |
| `422` | `VALIDATION_ERROR` | `scopes` is an empty array. |

**Curl example:**

```bash
curl -X POST https://fleet.example.com/api/v1/keys \
  -H "Authorization: Bearer fc_live_a3f5b8c1..." \
  -H "Content-Type: application/json" \
  -d '{"name": "ci-deploy-key", "scopes": ["config:read", "config:write", "flags:read"]}'
```

**Notes:**
- The returned `key` is shown only once. If it is lost, revoke the key (`DELETE /keys/{id}`) and create a new one.
- Key names are deduplicated; attempting to create two keys with the same name returns `409 VALIDATION_ERROR`.
- There is no endpoint to update an existing key's name or scopes. To change scopes, revoke the key and create a new one.

---

### GET /keys

**Description:** List all API keys with their metadata. The secret key value is not included; it is masked as `"****"` in the response. Results are sorted by `created_at` descending (newest first).

**Auth scope required:** `admin`

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `cursor` | string (optional) | — | Pagination cursor. |
| `limit` | integer | `50` | Max keys per page (`1`–`500`). |

**Request body:** None.

**Response `200 OK`:**

```json
{
  "data": [
    {
      "id": "key_01j8x9b3c4d5e6f7g8h9i0j",
      "name": "ci-deploy-key",
      "key": "****",
      "scopes": ["config:read", "config:write", "flags:read"],
      "created_at": "2024-11-01T12:00:00.000Z"
    },
    {
      "id": "key_01j7a2b3c4d5e6f7g8h9i0k",
      "name": "read-only-dashboard",
      "key": "****",
      "scopes": ["config:read", "flags:read"],
      "created_at": "2024-10-15T09:30:00.000Z"
    }
  ],
  "next_cursor": null
}
```

**Error responses:**

| Status | Error Code | Condition |
|---|---|---|
| `400` | `UNAUTHORIZED` | Missing or invalid Bearer token. |
| `403` | `FORBIDDEN` | Token lacks `admin`. |

**Curl example:**

```bash
curl "https://fleet.example.com/api/v1/keys?limit=25" \
  -H "Authorization: Bearer fc_live_a3f5b8c1..."
```

**Notes:**
- `key` is always `"****"` in list responses; the raw value is never returned after creation.
- Revoked keys are not returned in this list; use the audit log to review revoked key history.

---

### DELETE /keys/{id}

**Description:** Revoke an API key, immediately invalidating any request using it. Revocation is permanent and takes effect within seconds.

**Auth scope required:** `admin`

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `id` | string | The key ID returned at creation time (the `id` field, not the key string itself). |

**Request body:** None.

**Response `204 No Content`**

No body is returned.

**Error responses:**

| Status | Error Code | Condition |
|---|---|---|
| `400` | `UNAUTHORIZED` | Missing or invalid Bearer token. |
| `403` | `FORBIDDEN` | Token lacks `admin`. |
| `404` | `KEY_NOT_FOUND` | The key ID does not exist (or was already revoked). |

**Curl example:**

```bash
curl -X DELETE https://fleet.example.com/api/v1/keys/key_01j8x9b3c4d5e6f7g8h9i0j \
  -H "Authorization: Bearer fc_live_a3f5b8c1..."
```

**Notes:**
- Revoking a key that is currently in use will cause `UNAUTHORIZED` errors for any in-flight or subsequent requests using that key.
- Revoked key IDs are not recycled; each revocation generates a new ID.
- The audit log records the revocation event with the actor identity from the revoking token.

---

## 6. System

### GET /health

**Description:** Returns the service health status and version. This endpoint requires no authentication and is suitable for load-balancer health checks, uptime monitors, and Kubernetes readiness probes.

**Request body:** None.

**Query parameters:** None.

**Response `200 OK`:**

```json
{
  "status": "healthy",
  "version": "1.4.2"
}
```

**Possible `status` values:**

| Status | Meaning |
|---|---|
| `healthy` | All systems nominal. |
| `degraded` | The service is responding but one or more dependencies (e.g. the backing store) are experiencing elevated latency. Clients may continue to operate normally with caution. |
| `unhealthy` | The service cannot fulfill requests. Returns HTTP 503 instead of 200. |

**Curl example:**

```bash
curl https://fleet.example.com/api/v1/health
```

**Notes:**
- No `Authorization` header is required or accepted.
- The `version` field reflects the running server binary version (not the API version).
- `degraded` and `unhealthy` statuses are outside the normal 200 envelope and include a human-readable `message` field: `{"status": "degraded", "version": "1.4.2", "message": "Database replication lag elevated."}`

---

### GET /audit

**Description:** Query the immutable audit log. Entries are returned in reverse-chronological order (newest first) and support filtering by actor, action, resource type, and time range. This endpoint is intended for administrative investigation and compliance purposes.

**Auth scope required:** `admin`

**Query parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `actor` | string (optional) | No | — | Filter entries by the actor's subject claim (`sub`) from the token used at the time of the action. |
| `action` | string (optional) | No | — | Filter by action name. Allowed values: `config.set`, `config.delete`, `flag.set`, `flag.delete`, `key.revoke`. |
| `resource_type` | string (optional) | No | — | Filter by the type of resource affected. Allowed values: `config`, `flag`, `key`. |
| `from` | string (ISO 8601) (optional) | No | — | Inclusive lower bound on event timestamp. Example: `2024-10-01T00:00:00Z`. |
| `to` | string (ISO 8601) (optional) | No | — | Inclusive upper bound on event timestamp. Example: `2024-11-01T23:59:59Z`. |
| `cursor` | string (optional) | No | — | Pagination cursor. |
| `limit` | integer | No | `50` | Max entries per page (`1`–`500`). |

**Request body:** None.

**Response `200 OK`:**

```json
{
  "data": [
    {
      "id": "audit_01jb2c3d4e5f6g7h8i9j0k",
      "actor": "svc-deployer",
      "action": "config.set",
      "resource_type": "config",
      "resource_id": "prod.database/host",
      "timestamp": "2024-11-01T14:22:33.456Z",
      "metadata": {
        "version": 3,
        "type": "string"
      }
    },
    {
      "id": "audit_01jb1a2b3c4d5e6f7g8h9i0j",
      "actor": "alice",
      "action": "flag.set",
      "resource_type": "flag",
      "resource_id": "new_checkout_flow",
      "timestamp": "2024-11-01T10:00:00.000Z",
      "metadata": {
        "rollout_percentage": 50
      }
    }
  ],
  "next_cursor": null
}
```

**Error responses:**

| Status | Error Code | Condition |
|---|---|---|
| `400` | `UNAUTHORIZED` | Missing or invalid Bearer token. |
| `403` | `FORBIDDEN` | Token lacks `admin`. |
| `422` | `VALIDATION_ERROR` | `from` or `to` is not a valid ISO 8601 timestamp, or `limit` is out of range. |

**Curl examples:**

All entries (no filters):
```bash
curl "https://fleet.example.com/api/v1/audit?limit=100" \
  -H "Authorization: Bearer fc_live_a3f5b8c1..."
```

Filter by actor within a time window:
```bash
curl "https://fleet.example.com/api/v1/audit?actor=alice&from=2024-10-01T00:00:00Z&to=2024-10-31T23:59:59Z" \
  -H "Authorization: Bearer fc_live_a3f5b8c1..."
```

Filter by action and resource type:
```bash
curl "https://fleet.example.com/api/v1/audit?action=config.delete&resource_type=config" \
  -H "Authorization: Bearer fc_live_a3f5b8c1..."
```

Paginate:
```bash
curl "https://fleet.example.com/api/v1/audit?limit=20&cursor=eyJpZCI6ImF1ZGl0XzAx..." \
  -H "Authorization: Bearer fc_live_a3f5b8c1..."
```

**Notes:**
- Audit log entries are immutable and are retained for a configurable retention window (default: 90 days). Entries older than the retention window are not returned and cannot be queried.
- All filters are applied as logical AND. Omitting a filter means "match all values for that field".
- The `resource_id` field is a composite string in the form `{namespace}/{key}` for config entries and the plain `{name}` for flag and key entries.
- The `metadata` sub-object contains additional context specific to each action type (for example `version` for config writes, `rollout_percentage` for flag writes, and the revoked key `id` for key revocations).
- If `from` and `to` are both omitted, the default time range is the last 7 days.

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2024-11-01 | Initial release. All 15 endpoints documented. |
