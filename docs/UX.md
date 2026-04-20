# UX and API Design Guide

This guide defines the user experience contract shared by the fleet-config HTTP API and Python SDK. It builds on `docs/API.md` and `docs/SDK.md` and focuses on consistency, ergonomics, and remediation-oriented error handling.

The intended audience is maintainers designing new endpoints, SDK contributors extending client surfaces, and reviewers checking whether proposed interfaces feel predictable to both humans and machines.

---

## Design Principles

1. **Errors are actionable.** Every failure should give machines a stable code and give humans a next step.
2. **Names are boring on purpose.** API fields and SDK methods should prefer consistency over cleverness.
3. **Happy paths are concise.** Common tasks should require minimal boilerplate and read naturally in Python.
4. **Structured data stays structured.** Typed responses and validation metadata should survive transport and SDK translation.
5. **One concept, one spelling.** The API, models, exceptions, and documentation should use the same nouns for the same resource.

---

## 1. API Error-Response Shape and Taxonomy

### Canonical Error Envelope

All non-2xx API responses should use the same JSON envelope already described in `docs/API.md`:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description",
    "details": {}
  }
}
```

### Field Contract

| Field | Type | Required | Purpose | UX guidance |
|---|---|---|---|---|
| `error.code` | string | Yes | Stable machine-readable identifier | Use upper snake case; never localize; safe for branching logic. |
| `error.message` | string | Yes | Human-readable summary of the failure | Write in plain English; explain what failed, not stack traces. |
| `error.details` | object | No | Structured context for debugging and remediation | Keep keys stable and resource-specific; avoid free-form blobs when structure is known. |

### Taxonomy Rules

Error codes should be organized by **failure domain**, not by endpoint name alone. Prefer a taxonomy that answers two questions quickly:

- **What kind of problem is this?** Authentication, authorization, validation, missing resource, conflict, throttling, or server fault.
- **Which object is affected?** Config key, namespace, flag, API key, or request payload.

Recommended categories:

| Category | Typical HTTP status | Code style | Example |
|---|---|---|---|
| Authentication | 401 | Global/shared | `UNAUTHORIZED` |
| Authorization | 403 | Global/shared | `FORBIDDEN` |
| Validation | 400 or 422 | Global/shared or field-family | `VALIDATION_ERROR` |
| Missing resource | 404 | Resource-specific | `CONFIG_NOT_FOUND` |
| Conflict/state | 409 | Resource-specific | `NAMESPACE_NOT_EMPTY` |
| Rate limiting | 429 | Global/shared | `RATE_LIMITED` |
| Server/internal | 500+ | Global/shared | `INTERNAL_ERROR` |

### Message Writing Guidelines

Human-readable messages should be optimized for operators reading logs and CLI output.

Use these rules:

- State the object first when possible: `Config key 'agents.model' was not found in namespace 'prod'.`
- Avoid blameful phrasing like `you provided invalid input`.
- Avoid implementation details like table names, SQL errors, or internal exception class names.
- Keep the first sentence standalone; CLI tools can print only `message` and still be helpful.
- If remediation is obvious, mention it briefly: `Requested scope 'flags:write' is required.`

Examples:

| Good | Avoid |
|---|---|
| `Feature flag 'new-search' does not exist.` | `Flag lookup failed.` |
| `Bearer token is missing or invalid.` | `Authentication error.` |
| `Field 'limit' must be between 1 and 500.` | `Payload validation failed.` |

### `details` Shape Guidelines

The `details` object should provide machine-usable context without duplicating the message. Suggested patterns:

#### Resource errors

```json
{
  "error": {
    "code": "CONFIG_NOT_FOUND",
    "message": "Config key 'database.host' does not exist in namespace 'prod'.",
    "details": {
      "namespace": "prod",
      "key": "database.host"
    }
  }
}
```

#### Validation errors

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "details": {
      "fields": {
        "limit": ["Must be between 1 and 500"],
        "type": ["Must be one of: string, int, float, bool, json"]
      }
    }
  }
}
```

#### Authorization errors

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "This token does not have permission to delete API keys.",
    "details": {
      "required_scope": "keys:write"
    }
  }
}
```

### Status-Code Guidance

For fleet-config specifically, use these conventions consistently:

- **400** for syntactically valid requests with unsupported query parameters or invalid enum-like values when the failure is not field-by-field model validation.
- **401** for missing, malformed, expired, or otherwise invalid credentials.
- **403** for authenticated callers lacking the necessary scope.
- **404** when a named resource is absent.
- **409** when the resource exists but its current state blocks the operation.
- **422** for structured request-body validation failures.
- **429** for quota or rate-limit enforcement.
- **500–504** for transient or unexpected server-side failures.

### Compatibility Rules

To keep errors safe for automation:

- Never repurpose an existing `error.code` to mean something different.
- Preserve old codes when refining messages.
- Add new keys to `details` additively.
- Treat `message` as operator-facing text that may evolve; treat `code` and stable `details` keys as the programmatic contract.

---

## 2. CLI Ergonomics for the Python SDK

The SDK is Python-first, but its design should also support CLI-style workflows: brief commands, obvious verbs, readable defaults, and output that degrades cleanly into terminal usage.

### Method Naming

Follow the noun + verb structure already established in `docs/SDK.md`:

- Namespace accessors are nouns: `client.config`, `client.flags`.
- Operations are short verbs: `get`, `set`, `delete`, `list`, `history`, `check`, `create`, `revoke`.
- Streaming or long-lived operations use event-oriented verbs: `watch`.

Recommended naming rules:

| Pattern | Use | Example |
|---|---|---|
| `get` | Fetch one resource by identity | `client.flags.get(name)` |
| `list` | Enumerate many resources | `client.flags.list(limit=100)` |
| `set` | Create-or-replace idempotent writes | `client.config.set(namespace, key, value)` |
| `create` | Non-idempotent creation | `client.keys.create(scopes=[...])` |
| `delete` or `revoke` | Destructive operations | `client.keys.revoke(key_id)` |
| `check` | Server-side evaluation or decisioning | `client.flags.check(name, user_id=...)` |
| `watch` | Streaming subscriptions | `client.watch(namespace)` |

Avoid introducing synonyms for the same action, such as mixing `remove`, `destroy`, and `delete` across namespaces.

### Parameter Conventions

Python callers expect identity parameters first and optional behavior controls second.

Recommended ordering:

1. Required positional identifiers
2. Required payload value, if any
3. Keyword-only optional controls

Examples:

```python
client.config.get(namespace, key)
client.config.set(namespace, key, value, *, type=None)
client.flags.check(name, *, user_id, attributes=None)
client.flags.list(*, cursor=None, limit=50)
```

Specific conventions:

- Prefer `snake_case` for all SDK parameters and model fields.
- Keep API terminology where it is already clear and domain-specific: `namespace`, `rollout_percentage`, `updated_at`.
- Use keyword-only parameters for optional behavior and less obvious required inputs such as evaluation context.
- Reserve booleans for true toggles; avoid ambiguous flags like `full=False` when explicit methods or enums would be clearer.
- Use `None` to mean omission, not an empty string or sentinel literal.

### CLI-Friendly Signatures

Even if the SDK is not itself a CLI, good SDK signatures map cleanly to terminal wrappers.

Prefer:

```python
client.flags.check("new-search", user_id="user-123", attributes={"tier": "pro"})
```

Over:

```python
client.flags.check("new-search", "user-123", {"tier": "pro"}, False, None)
```

This makes wrappers easier to generate, shell examples easier to read, and errors easier to attribute to a named argument.

### Context Manager Patterns

`Client` already supports `with Client(...) as client:`. This should be the default documented pattern for any code that performs more than one request or maintains pooled connections.

Preferred guidance:

- Use a context manager in scripts, jobs, and tests.
- Keep `close()` available for long-lived objects managed outside `with`.
- Ensure streamed resources are also closed promptly on loop exit or exception.
- If an async client is added later, mirror the same shape with `async with`.

Example:

```python
from fleet_config import Client

with Client(base_url=base_url, api_key=api_key) as client:
    current = client.config.get("agents", "default_model")
    print(current.value)
```

For watch streams, the ergonomics should remain iterator-based while documenting lifetime clearly:

```python
with Client(base_url=base_url, api_key=api_key) as client:
    for event in client.watch("agents"):
        print(event.key, event.version)
```

### Output and Exception Ergonomics

For CLI-style use, exceptions should be easy to collapse into one line:

```python
try:
    client.flags.delete("old-flag")
except FleetConfigError as exc:
    print(f"{exc.error_code or 'ERROR'}: {exc.message}")
```

That pattern works only if:

- `error_code` is stable and concise
- `message` is already operator-friendly
- `details` is supplemental, not required for comprehension

---

## 3. Idiomatic Python Usage Patterns

### Use Type Hints Pervasively

The SDK should continue treating type hints as part of the public UX, not as internal decoration.

Guidelines:

- Annotate all public methods, return values, and exception fields.
- Prefer precise unions and literals where the domain is closed.
- Use `Mapping[str, object]` or `dict[str, object]` for JSON-like attribute bags, depending on mutability needs.
- Keep timestamps as `datetime`, not strings, in SDK models.

Example:

```python
from collections.abc import Iterator
from typing import Literal


def watch(namespace: str) -> Iterator[WatchEvent]:
    ...


def set(
    namespace: str,
    key: str,
    value: object,
    *,
    type: Literal["string", "int", "float", "bool", "json"] | None = None,
) -> ConfigValue:
    ...
```

### Lean Into Pydantic Models

`docs/SDK.md` specifies Pydantic models for response objects. That is the right UX choice because it gives callers:

- editor autocomplete
- runtime validation
- simple JSON serialization
- predictable nested structures

Recommended model practices:

- Model API resources as `BaseModel` subclasses.
- Parse server responses immediately at the SDK boundary.
- Expose typed nested models instead of raw dictionaries when the schema is known.
- Keep `model_dump()` / `model_dump_json()` examples in docs so users know how to bridge to storage and logs.

Example:

```python
from fleet_config.models import ConfigValue

config: ConfigValue = client.config.get("agents", "default_model")
print(config.model_dump())
print(config.model_dump_json(indent=2))
```

### Prefer `with` Examples in Documentation

Documentation should bias toward examples that clean up after themselves.

Preferred pattern:

```python
from fleet_config import Client

with Client(base_url=base_url, api_key=api_key) as client:
    feature = client.flags.get("new-search")
    print(feature.enabled)
```

Acceptable shortcut for REPL examples:

```python
client = Client(base_url=base_url, api_key=api_key)
try:
    print(client.flags.list(limit=10))
finally:
    client.close()
```

### Show Common Task Patterns

#### Read-modify-write config

```python
from fleet_config import Client
from fleet_config.errors import NotFoundError

with Client(base_url=base_url, api_key=api_key) as client:
    try:
        current = client.config.get("agents", "temperature")
        value = float(current.value)
    except NotFoundError:
        value = 0.7

    updated = client.config.set("agents", "temperature", value + 0.1, type="float")
    print(updated.version, updated.value)
```

#### Feature-flag evaluation

```python
from fleet_config import Client
from fleet_config.models import FlagEvaluation

with Client(base_url=base_url, api_key=api_key) as client:
    result: FlagEvaluation = client.flags.check(
        "new-search",
        user_id="user-42",
        attributes={"tier": "premium", "region": "us-east"},
    )
    if result.enabled:
        print(f"enabled via {result.reason}")
```

#### Pagination loop

```python
from fleet_config import Client

with Client(base_url=base_url, api_key=api_key) as client:
    cursor: str | None = None
    while True:
        page = client.flags.list(cursor=cursor, limit=100)
        for flag in page.data:
            print(flag.name)
        if not page.next_cursor:
            break
        cursor = page.next_cursor
```

#### Structured validation handling

```python
from fleet_config import Client
from fleet_config.errors import ValidationError

with Client(base_url=base_url, api_key=api_key) as client:
    try:
        client.config.set("agents", "max_tokens", "a lot", type="int")
    except ValidationError as exc:
        print(exc.message)
        print(exc.details or {})
```

### Keep Pythonic Defaults

When adding new methods or models, prefer these defaults:

- return objects, not tuples
- return `None` for successful deletes with no body
- use iterators for streams
- use exceptions for failures, not `(result, error)` pairs
- accept standard Python containers as input

These choices match the rest of the SDK and reduce surprise for Python users.

---

## 4. Error Code Catalog with Suggested Remediation Messages

The API reference already lists a baseline catalog. The table below expands that catalog into a UX contract by pairing each code with a recommended message style, SDK exception mapping, and operator remediation.

| Code | HTTP | SDK exception | Recommended message | Suggested remediation |
|---|---|---|---|---|
| `UNAUTHORIZED` | 401 | `AuthenticationError` | `Bearer token is missing or invalid.` | Verify the `Authorization` header, token prefix, token freshness, and target environment. |
| `FORBIDDEN` | 403 | `PermissionDeniedError` | `This token does not have permission to perform this action.` | Use a token with the required scope, such as `config:write` or `keys:write`. |
| `INVALID_SCOPE` | 400 | `ValidationError` or dedicated scope error | `One or more requested scopes are not valid.` | Check scope spelling against the documented allowlist before creating the key. |
| `VALIDATION_ERROR` | 422 | `ValidationError` | `Request validation failed.` | Inspect `error.details.fields` and correct the named fields before retrying. |
| `CONFIG_NOT_FOUND` | 404 | `NotFoundError` | `Config key '{key}' does not exist in namespace '{namespace}'.` | Confirm the namespace and key, or create the config entry before reading or deleting it. |
| `FLAG_NOT_FOUND` | 404 | `NotFoundError` | `Feature flag '{name}' does not exist.` | Check the flag name for typos or create the flag first. |
| `KEY_NOT_FOUND` | 404 | `NotFoundError` | `API key '{id}' does not exist or has already been revoked.` | Refresh the key list and avoid retrying revoke on an already-removed key. |
| `NAMESPACE_NOT_EMPTY` | 409 | `ConflictError` | `Namespace '{namespace}' cannot be deleted because it still contains keys.` | Delete or migrate remaining keys, then retry the namespace deletion. |
| `RATE_LIMITED` | 429 | `RateLimitError` | `Rate limit exceeded.` | Retry with exponential backoff and reduce burst size; honor `Retry-After` if present. |
| `INTERNAL_ERROR` | 500 | `ServerError` | `The server encountered an unexpected error.` | Retry with backoff; if the failure persists, capture request identifiers and escalate. |

### Additional Catalog Guidance

For future codes, preserve the same style:

- **Code** is short and stable.
- **Message** describes the immediate problem in one sentence.
- **Remediation** tells the operator what to check next.

Recommended future additions if the product surface grows:

| Candidate code | When to use | Suggested remediation |
|---|---|---|
| `RATE_LIMITED` | Explicit throttle responses from gateway or app layer | Back off and retry after the server-advertised delay. |
| `CURSOR_INVALID` | Pagination cursor cannot be parsed or has expired | Restart pagination without a cursor and avoid reusing cursors across filter changes. |
| `WATCH_STREAM_EXHAUSTED` | Streaming connection exceeded retry budget | Recreate the client or subscription and inspect network stability. |
| `CONFLICT_VERSION_MISMATCH` | Future optimistic locking support | Re-read the latest version, merge changes, and retry with the fresh version token. |

### API-to-SDK Translation Rules

To keep remediation consistent across transports, the SDK should map API errors using this algorithm:

1. Parse `error.code`, `error.message`, and `error.details` when present.
2. Choose the exception subclass from HTTP status.
3. Preserve the original `error.code` on the exception as `error_code`.
4. Surface the API `message` unchanged unless no structured body exists.
5. Leave remediation in docs and CLI layers rather than hard-coding verbose advice into exceptions.

This separation keeps API payloads concise while still allowing CLI tools and operational runbooks to present tailored next steps.

---

## Review Checklist

Use this checklist when reviewing new endpoints or SDK additions:

- Does the API return the canonical error envelope for every failure path?
- Is `error.code` stable, specific, and machine-friendly?
- Is `error.message` understandable without reading server code?
- Does `details` add structured context instead of duplicating prose?
- Do SDK methods use consistent verbs and `snake_case` parameters?
- Are optional parameters keyword-only where that improves readability?
- Do examples use `with Client(...)` by default?
- Are public return types modeled with Pydantic instead of raw dictionaries?
- Is there a documented remediation path for each new error code?

