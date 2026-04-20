# fleet-config Python SDK — Design Document

> **Version:** 1.0.0-draft  
> **Status:** Design specification; implementation follows this document as the source of truth.  
> **Audience:** Engineers implementing the Python client library.

---

## 1. Overview

`fleet-config` is a Python package that wraps the fleet-config REST API with an ergonomic, Pythonic interface. It handles authentication, connection management, retry logic, SSE (Server-Sent Events) consumption, and typed response models so callers work with native Python objects instead of raw JSON dictionaries.

The package ships with a `py.typed` marker and ships type stubs, making it fully compatible with type-checkers (mypy, pyright, pytype).

---

## 2. Installation

```bash
pip install fleet-config
```

### Dependencies

The package has **zero required external dependencies** beyond the Python standard library. All transport is implemented with `urllib.request` and `sseclient` (bundled as a vendored copy or declared as a dependency).

Optional dev/test extras (not installed by default):

```bash
# For development
pip install fleet-config[dev]   # installs pytest, pytest-asyncio, mypy, ruff

# For type-checking your own code that uses fleet_config
pip install fleet-config[types]  # installs typeshed stubs /ypy type stubs if published
```

---

## 3. Quick Start

```python
from fleet_config import Client

# ─── Initialise ────────────────────────────────────────────────────────────────
client = Client(
    base_url="http://localhost:8080",
    api_key="fc_live_abc123xyz",
    timeout=30.0,
    max_retries=3,
)

# ─── Config ────────────────────────────────────────────────────────────────────
# Set a key
client.config.set("agents", "default_model", "gpt-5.2")

# Read it back
val = client.config.get("agents", "default_model")
print(val.value)          # "gpt-5.2"
print(val.version)        # 12

# List all keys in a namespace
for cfg in client.config.list("agents"):
    print(cfg.key, cfg.value, cfg.type)

# Full change history for one key
for version in client.config.history("agents", "default_model"):
    print(f"v{version.version} by {version.actor}: {version.value} @ {version.created_at}")

# Delete a key
client.config.delete("agents", "deprecated_key")

# ─── Feature Flags ─────────────────────────────────────────────────────────────
# Create a flag
flag = client.flags.create(
    "new-search",
    rollout_percentage=25,
    enabled=True,
    description="Gradual rollout of the new search backend.",
    rules=[{"attribute": "region", "operator": "eq", "value": "us-east"}],
)

# Evaluate a flag for a specific user/agent
result = client.flags.check(
    "new-search",
    user_id="agent-7",
    attributes={"tier": "premium", "region": "us-east"},
)
print(result.flag, result.enabled, result.reason)
# → new-search True rule_match

# Inspect a flag
print(client.flags.get("new-search"))

# Delete a flag
client.flags.delete("new-search")

# List all flags
for f in client.flags.list():
    print(f.name, f.enabled, f.rollout_percentage)

# ─── Watch (SSE) ───────────────────────────────────────────────────────────────
# Subscribe to config-change events on the "agents" namespace
for event in client.watch("agents"):
    print(f"Key changed : {event.namespace}.{event.key}")
    print(f"New version : {event.version}")
    print(f"At          : {event.timestamp}")
    # client is auto-reconnecting on transient SSE disconnects.
```

---

## 4. Class Reference

### 4.1 `Client`

```python
class Client:
    """
    Top-level entry point for the fleet-config SDK.

    Parameters
    ----------
    base_url : str
        Base URL of the fleet-config API server, **without** a trailing slash.
        Example: ``"http://localhost:8080"``.
    api_key : str
        Bearer token used for authentication. Obtain from the fleet-config
        dashboard. Must begin with ``"fc_live_"`` for production endpoints or
        ``"fc_test_"`` for sandbox endpoints.
    timeout : float, default 30.0
        Per-request socket timeout in seconds. A ``TimeoutError`` is raised if
        no byte is received within this window on a given attempt.
    max_retries : int, default 3
        Maximum number of automatic retry attempts for retriable errors (see
        §6 Retry Behaviour). Applied on a per-request basis; the total number
        of attempts is ``max_retries + 1``.
    retry_backoff : float, default 0.5
        Base for the exponential-backoff multiplier. The delay between attempt
        ``n`` and ``n+1`` is ``retry_backoff * (2 ** attempt_n)`` seconds,
        plus uniform jitter of ±25 %.
    """

    config: ConfigNamespace
    flags: FlagsNamespace

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
    ) -> None: ...

    def close(self) -> None:
        """Close the underlying HTTP connection pool and cancel any in-flight requests."""
        ...

    def __enter__(self) -> "Client": ...
    def __exit__(self, *args: object) -> None: ...
```

**Context manager:** `Client` implements `__enter__` / `__exit__` so it may be used with the `with` statement, which guarantees `close()` is called on exit.

```python
with Client(base_url="http://localhost:8080", api_key="fc_live_...") as client:
    # work with client
    pass
# pool is closed automatically
```

---

### 4.2 `ConfigNamespace`

Returned as `client.config`. Exposes config-versioned key/value storage.

#### `ConfigNamespace.get`

```python
def get(self, namespace: str, key: str) -> ConfigValue:
    """
    Retrieve a single config value.

    Parameters
    ----------
    namespace : str
        Logical grouping for the key, e.g. ``"agents"``, ``"deployment"``.
    key : str
        Dot-separated key path within the namespace, e.g. ``"model"`` or
        ``"limits.requests_per_minute"``.

    Returns
    -------
    ConfigValue
        The stored value together with its current version, type, and
        ``updated_at`` timestamp.

    Raises
    ------
    NotFoundError
        Raised when ``(namespace, key)`` has no entry.
    AuthenticationError / PermissionDeniedError / ServerError
        Propagated from transport layer.
    """
```

#### `ConfigNamespace.set`

```python
def set(
    self,
    namespace: str,
    key: str,
    value: object,
    *,
    type: str | None = None,
) -> ConfigValue:
    """
    Create or overwrite a config value.

    Parameters
    ----------
    namespace : str
        Logical grouping for the key.
    key : str
        Dot-separated key path.
    value : object
        The value to store. The API accepts JSON-serialisable Python objects.
        Compound dict/list structures are serialised to JSON.
    type : str | None
        Optional type hint for the stored value. Accepted tokens are
        ``"string"``, ``"number"``, ``"boolean"``, ``"json"``. If omitted
        the server infers the type from the JSON payload.

    Returns
    -------
    ConfigValue
        The newly written (or updated) config value with its new version number.

    Raises
    ------
    ValidationError
        Raised when ``type`` is specified but the value does not match the
        declared type.
    AuthenticationError / PermissionDeniedError / ServerError
        Propagated from transport layer.
    """
```

#### `ConfigNamespace.delete`

```python
def delete(self, namespace: str, key: str) -> None:
    """
    Delete a config key permanently.

    Parameters
    ----------
    namespace : str
    key : str

    Raises
    ------
    NotFoundError
        Raised when the ``(namespace, key)`` pair does not exist.
    AuthenticationError / PermissionDeniedError / ServerError
        Propagated from transport layer.
    """
```

#### `ConfigNamespace.list`

```python
def list(
    self,
    namespace: str,
    *,
    prefix: str | None = None,
    limit: int = 50,
) -> list[ConfigValue]:
    """
    List all keys in a namespace, optionally filtered by key prefix.

    Parameters
    ----------
    namespace : str
    prefix : str | None
        When set, only keys whose string representation **starts with** this
        prefix are returned. Prefix matching is performed on the full dot-path
        key, not just its final component. Example: ``prefix="limits."`` will
        return all keys under the ``limits`` sub-namespace.
    limit : int, default 50
        Upper bound on the number of results returned in a single API call.
        The SDK pages automatically until all matches are retrieved; callers
        receive a single flat list.

    Returns
    -------
    list[ConfigValue]
        Zero or more config values.
    """
```

#### `ConfigNamespace.history`

```python
def history(
    self,
    namespace: str,
    key: str,
    *,
    limit: int = 50,
) -> list[ConfigVersion]:
    """
    Return the version history of a single config key, newest-first.

    Parameters
    ----------
    namespace : str
    key : str
    limit : int, default 50
        Maximum number of historical snapshots to retrieve.

    Returns
    -------
    list[ConfigVersion]
        List of historical snapshots, newest first. Each entry carries the
        value at that point in time, the actor who made the change (usually a
        user ID or service name), and the UTC ``created_at`` timestamp.
    """
```

---

### 4.3 `FlagsNamespace`

Returned as `client.flags`. Exposes feature-flag CRUD and evaluation.

#### `FlagsNamespace.create`

```python
def create(
    self,
    name: str,
    *,
    description: str | None = None,
    enabled: bool = True,
    rollout_percentage: int = 100,
    rules: list[FlagRule] | None = None,
) -> FeatureFlag:
    """
    Register a new feature flag.

    Parameters
    ----------
    name : str
        Unique flag identifier. Lowercase alphanumeric with hyphens; max 64
        characters. Must be unique across the entire fleet.
    description : str | None
        Human-readable description for tooling and dashboards.
    enabled : bool, default True
        Global master switch for this flag. When ``False`` the flag is
        considered off for every evaluation unless an allowlist rule matches.
    rollout_percentage : int
        Integer 0–100. Percentage of ``user_id`` values (hashed deterministically)
        that pass the rollout gate when no rule applies and the flag is enabled.
        Defaults to 100 (fully rolled out).
    rules : list[FlagRule] | None
        Optional list of evaluation rules evaluated in order. See FlagRule data
        model below.

    Returns
    -------
    FeatureFlag
        The created flag (including server-assigned metadata).

    Raises
    ------
    ConflictError
        Raised when a flag with this ``name`` already exists.
    ValidationError
        Raised for malformed rule expressions or invalid percentage values.
    """
    # FlagRule shape (not a top-level class — defined here for doc purposes):
    # rule = {"attribute": str, "operator": str, "value": object}
    # Accepted operators: "eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in", "contains"
```

#### `FlagsNamespace.check`

```python
def check(
    self,
    name: str,
    *,
    user_id: str,
    attributes: dict[str, object] | None = None,
) -> FlagEvaluation:
    """
    Evaluate a feature flag for a given user/agent context.

    Parameters
    ----------
    name : str
        Flag to evaluate.
    user_id : str
        Stable identifier for the end-user or agent making the request. Used as
        the deterministic salt for the rollout-percentage hash so the same
        ``user_id`` always receives the same result.
    attributes : dict[str, object] | None
        Optional map of contextual attributes used in rule matching, e.g.
        ``{"region": "us-east", "tier": "premium"}``.

    Returns
    -------
    FlagEvaluation
        Result object containing the flag name, enabled boolean, and a
        machine-readable ``reason`` string describing why the flag evaluated
        to that state.

    Evaluation priority (evaluated in order, first match wins):
    1. **disabled** — The flag exists but its ``enabled`` field is ``False``.
    2. **allowlist** — A rule with operator ``eq`` matched an ``user_id`` or an
       attribute in ``attributes``.
    3. **rollout** — The deterministic hash of ``(name, user_id)`` fell within
       ``[0, rollout_percentage)``.
    4. **rule_match** — A non-allowlist rule matched an attribute expression.
    5. **default** — No rules matched and rollout gate was not passed; flag is
       off.

    Raises
    ------
    NotFoundError
        Raised when no flag with this ``name`` is registered.
    AuthenticationError / PermissionDeniedError / ServerError
        Propagated from transport layer.
    """
```

#### `FlagsNamespace.get`

```python
def get(self, name: str) -> FeatureFlag:
    """
    Retrieve the full flag definition by name.

    Parameters
    ----------
    name : str

    Returns
    -------
    FeatureFlag

    Raises
    ------
    NotFoundError
        Raised when the flag does not exist.
    """
```

#### `FlagsNamespace.delete`

```python
def delete(self, name: str) -> None:
    """
    Delete a feature flag permanently.

    Parameters
    ----------
    name : str

    Raises
    ------
    NotFoundError
        Raised when the flag does not exist.
    """
```

#### `FlagsNamespace.list`

```python
def list(self) -> list[FeatureFlag]:
    """
    List every registered feature flag.

    Returns
    -------
    list[FeatureFlag]
        All flags in the fleet, newest-first.
    """
```

---

### 4.4 `Client.watch`

```python
def watch(self, namespace: str) -> Iterator[WatchEvent]:
    """
    Subscribe to a real-time stream of config-change events for a namespace
    using Server-Sent Events (SSE).

    Parameters
    ----------
    namespace : str
        Namespace to watch. All config changes within this namespace are
        forwarded as ``WatchEvent`` objects.

    Yields
    ------
    WatchEvent
        Each event contains the event type (``"put"`` for create/update,
        ``"delete"`` for removal), the affected ``(namespace, key)`` pair,
        the new ``version`` number, and a UTC ``timestamp``.

    Reconnection Policy
    -------------------
    The iterator auto-reconnects on transient disconnections (network blip,
        server restart). The back-off follows the same exponential-backoff
        schedule as the HTTP client. After ``max_retries`` consecutive failures
        the iterator raises a ``ServerError``.

    Note
    ----
    This is a **consuming iterator**: you must fully exhaust it (or wrap it in
    ``itertools.islice``) before calling any other SDK method on the same
    ``Client`` instance. SSE and HTTP share a single underlying session.
    """

    import time
    import sseclient  # vendored / bundled

    attempt = 0
    while True:
        try:
            resp = self._session.get(
                f"{self.base_url}/api/v1/watch/{namespace}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "text/event-stream",
                    "Cache-Control": "no-cache",
                },
                stream=True,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            client_ = sseclient.SSEClient(resp)
            for sse_event in client_:
                if sse_event.data == "":
                    continue
                yield WatchEvent.from_sse(sse_event)
        except Exception as exc:
            if not _is_retriable_sse(exc):
                raise
            attempt += 1
            if attempt > self.max_retries:
                raise ServerError(f"Watch stream exhausted retries after {attempt} attempts") from exc
            time.sleep(self._backoff(attempt))
```

---

## 5. Data Models

All response objects are **Pydantic v2 models** (or equivalent with a compatibility shim for Pydantic v1). They accept both `dict` and keyword arguments as input. Serialisation uses `model_dump_json()`.

```python
from fleet_config.models import (
    ConfigValue,
    ConfigVersion,
    FeatureFlag,
    FlagEvaluation,
    FlagRule,
    WatchEvent,
)
```

### `ConfigValue`

```python
class ConfigValue(BaseModel):
    """
    Represents a single stored config key/value pair at its current version.
    """

    namespace: str
    """
    Logical grouping, e.g. ``"agents"``.
    """

    key: str
    """
    Dot-separated key path, e.g. ``"default_model"``.
    """

    value: object
    """
    The deserialised value. Type matches the ``type`` field.
    """

    type: Literal["string", "number", "boolean", "json"]
    """
    Declared semantic type of the value. Controls how the value is
    deserialised on read.
    """

    version: int
    """
    Monotonically increasing integer version. Incremented on every successful
    ``set`` call. Useful for optimistic concurrency control.
    """

    updated_at: datetime
    """
    UTC timestamp of the most recent ``set`` call.
    """
```

### `ConfigVersion`

```python
class ConfigVersion(BaseModel):
    """
    An immutable snapshot of a config key at a specific point in time.
    """

    version: int
    """
    Version number this snapshot records.
    """

    value: object
    """
    The value at the point this snapshot was taken.
    """

    actor: str | None
    """
    Identity of the principal that triggered the change. Usually a user ID,
    service account name, or ``"system"``. May be ``None`` for historical
    records created before actor tracking was introduced.
    """

    created_at: datetime
    """
    UTC timestamp when this version was written.
    """
```

### `FeatureFlag`

```python
class FeatureFlag(BaseModel):
    """
    Complete definition of a feature flag.
    """

    name: str
    """
    Unique identifier; must match ``^[a-z0-9][-a-z0-9]{0,63}$``.
    """

    description: str | None
    """
    Free-text description.
    """

    enabled: bool
    """
    Master switch. When ``False`` the flag evaluates to ``enabled=False``
    for all subjects unless they match an explicit allowlist rule.
    """

    rollout_percentage: int
    """
    Integer 0–100. Deterministic rollout percentage evaluated against
    ``user_id`` when no rule matches.
    """

    rules: list[FlagRule] | None
    """
    Ordered list of conditional rules. Evaluated in index order; the first
    match wins. May be ``None`` (empty list) when no rules are defined.
    """
```

### `FlagRule`

```python
class FlagRule(BaseModel):
    """
    A single conditional rule within a FeatureFlag.

    Rule evaluation is performed server-side at ``check`` time. The SDK
    sends ``user_id`` and ``attributes`` and receives a ``reason`` in the
    ``FlagEvaluation`` response; raw rule evaluation does not happen on the
    client.
    """

    attribute: str
    """
    Dot-separated attribute path to inspect in the evaluation context, e.g.
    ``"tier"`` or ``"location.country_code"``.
    """

    operator: Literal[
        "eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in", "contains"
    ]
    """
    Comparison operator.

    - ``eq``       — equality (value must be a string, number, or bool)
    - ``neq``      — not equal
    - ``gt``/``gte``/``lt``/``lte`` — numeric comparison
    - ``in``       — attribute value appears in the list provided as ``value``
    - ``not_in``   — attribute value does not appear in the list
    - ``contains`` — attribute (must be a string) contains the provided substring
    """

    value: object
    """
    The comparison target. Must be compatible with the declared ``operator``.
    For ``in`` / ``not_in`` this must be a JSON array.
    """
```

### `FlagEvaluation`

```python
class FlagEvaluation(BaseModel):
    """
    The result of evaluating a feature flag for a specific context.
    """

    flag: str
    """
    Name of the flag that was evaluated.
    """

    enabled: bool
    """
    Whether the flag resolves to ``True`` or ``False`` for the given context.
    """

    reason: Literal["disabled", "allowlist", "rollout", "rule_match", "default"]
    """
    Machine-readable explanation of the evaluation result.

    - ``disabled``  — flag exists but ``enabled=False`` globally.
    - ``allowlist`` — a rule with operator ``eq`` matched the ``user_id`` or an
                       attribute and forced the flag on.
    - ``rollout``   — the ``user_id`` hash fell within ``rollout_percentage``.
    - ``rule_match`` — a non-allowlist rule matched; see ``FlagEvaluation`` extra
                       field ``rule_index`` for which rule.
    - ``default``   — no rule matched and rollout gate was not passed;
                       flag is off.
    """
```

### `WatchEvent`

```python
class WatchEvent(BaseModel):
    """
    A real-time config-change event received via SSE.
    """

    event: Literal["put", "delete"]
    """
    Event kind.

    - ``put``    — a config key was created or updated.
    - ``delete`` — a config key was deleted.
    """

    namespace: str
    """
    Namespace in which the change occurred.
    """

    key: str
    """
    Full dot-separated key path that changed.
    """

    version: int
    """
    New version number of the affected key (absent for ``delete`` events).
    """

    timestamp: datetime
    """
    UTC timestamp when the change was committed.
    """

    @classmethod
    def from_sse(cls, sse_event: sseclient.Event) -> "WatchEvent":
        """
        Parse a ``sseclient.Event`` into a ``WatchEvent``.

        Expected SSE fields:

        - ``event`` — ``"put"`` or ``"delete"``
        - ``data``   — JSON object with at least ``namespace``, ``key``,
                       ``version`` (int), ``timestamp`` (ISO-8601 string)
        """
        import json
        data = json.loads(sse_event.data)
        return cls(
            event=sse_event.event or "put",
            namespace=data["namespace"],
            key=data["key"],
            version=data["version"],
            timestamp=datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00")),
        )
```

---

## 6. Error Handling

### Exception Hierarchy

```
FleetConfigError (Exception)
├── AuthenticationError     — HTTP 401
├── PermissionDeniedError   — HTTP 403
├── NotFoundError           — HTTP 404
├── ConflictError           — HTTP 409
├── ValidationError         — HTTP 422   (malformed request body)
├── RateLimitError           — HTTP 429   (retryable)
└── ServerError             — HTTP 5xx   (retryable)

ConnectionError (FleetConfigError)
    — network-level failures: DNS lookup failed, connection refused,
      socket timeout, TLS handshake failure
```

### Exception Shape

All SDK exceptions carry four fields that are always present (defaulting to
`None` when the underlying HTTP response does not supply them):

```python
class FleetConfigError(Exception):
    """
    Abstract base for all fleet-config exceptions.

    Attributes
    ----------
    status_code : int | None
        HTTP status code of the failing response. ``None`` for network
        failures.
    error_code : str | None
        Machine-readable error token returned by the API, e.g. ``"FLAG_NOT_FOUND"``.
        ``None`` when the server did not return a structured error body.
    message : str
        Human-readable description. Always non-``None``.
    details : dict[str, object] | None
        Optional additional context from the API, such as a list of
        validation failures keyed by field path.
    """

    status_code: int | None
    error_code: str | None
    message: str
    details: dict[str, object] | None

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None: ...
```

**Subclass mapping:**

| HTTP status | Exception class                |
|-------------|-------------------------------|
| 401         | `AuthenticationError`         |
| 403         | `PermissionDeniedError`       |
| 404         | `NotFoundError`               |
| 409         | `ConflictError`               |
| 422         | `ValidationError`              |
| 429         | `RateLimitError` (retryable)  |
| 500–504     | `ServerError` (retryable)     |
| Network     | `ConnectionError`             |

### Error Body Shape

The API is expected to return errors as JSON:

```json
{
  "error": {
    "code": "FLAG_NOT_FOUND",
    "message": "Feature flag 'never-created' does not exist.",
    "details": { "flag": "never-created" }
  }
}
```

When a structured error body is present `error_code` maps to `error.code`,
`message` maps to `error.message`, and `details` maps to `error.details`.
When the response is not a JSON error body the SDK constructs a generic
`FleetConfigError` with the raw response text (or a standard library
`Exception` message) as the `message`.

---

## 7. Retry Behaviour

### Retriable Conditions

The SDK **automatically retries** the following conditions:

| Condition | Reason |
|-----------|--------|
| HTTP 429 | Rate-limited. Exponential back-off clears the limit. |
| HTTP 500–504 | Transient server errors. |
| `ConnectionError` (network-level) | DNS failure, refused connection, TLS timeout. |

### Non-Retriable Conditions

| Condition | Reason |
|-----------|--------|
| HTTP 401 / 403 | Authentication / permission issue — credentials are wrong or session expired. Retrying does not help. |
| HTTP 404 | Resource absent — retrying will not create the resource. |
| HTTP 409 | Conflict — the conflicting state will not clear by retrying. |
| HTTP 422 | Validation error — the request body is malformed; re-sending achieves nothing. |

### Back-off Schedule

For attempt `n` (starting at 0), the delay before attempt `n+1` is:

```
delay_n = retry_backoff * (2 ** n) + uniform(-0.25 * retry_backoff, +0.25 * retry_backoff)
```

Defaults: `retry_backoff = 0.5` → delays of approximately 0.5 s, 1.0 s, 2.0 s.

### Implementing the Retry Loop

```python
def _request_with_retry(
    self,
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float,
) -> HTTPResponse:
    last_exc: Exception | None = None
    for attempt in range(self.max_retries + 1):
        try:
            req = _build_request(method, path, body, headers, timeout, self._pool)
            resp = self._pool.urlopen(req.method, req.get_full_url(), ...)
            if resp.status < 400:
                return resp
            if not _is_retriable_status(resp.status):
                self._raise_for_status(resp)
            last_exc = self._http_error(resp)
        except Exception as exc:
            if not _is_retriable_exc(exc):
                raise
            last_exc = exc
        if attempt < self.max_retries:
            sleep(self._backoff(attempt))
    assert last_exc is not None
    raise last_exc
```

---

## 8. Type Hints

The package ships with:

```text
fleet-config/
├── fleet_config/
│   ├── __init__.py          # re-exports public API
│   ├── client.py            # Client class
│   ├── config_namespace.py  # ConfigNamespace
│   ├── flags_namespace.py   # FlagsNamespace
│   ├── models.py            # All Pydantic data models
│   ├── errors.py            # Exception hierarchy
│   └── py.typed             # marker file — "this package ships type info"
```

### Public API Surface (re-exports from `__init__.py`)

```python
# fleet_config/__init__.py
from fleet_config.client          import Client
from fleet_config.config_namespace import ConfigNamespace
from fleet_config.flags_namespace  import FlagsNamespace
from fleet_config.models          import (
    ConfigValue,
    ConfigVersion,
    FeatureFlag,
    FlagEvaluation,
    FlagRule,
    WatchEvent,
)
from fleet_config.errors import (
    FleetConfigError,
    AuthenticationError,
    PermissionDeniedError,
    NotFoundError,
    ConflictError,
    ValidationError,
    RateLimitError,
    ServerError,
    ConnectionError,
)

__all__ = [
    "Client",
    "ConfigNamespace",
    "FlagsNamespace",
    "ConfigValue",
    "ConfigVersion",
    "FeatureFlag",
    "FlagEvaluation",
    "FlagRule",
    "WatchEvent",
    "FleetConfigError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "ConflictError",
    "ValidationError",
    "RateLimitError",
    "ServerError",
    "ConnectionError",
]

__version__: str = "1.0.0"
```

The `py.typed` marker file exists at the root of the installed package to signal to mypy/pyright that type annotations are available and complete.

---

## 9. Usage Patterns

### 9.1 Context Manager

Always prefer the context-manager form to ensure the HTTP connection pool is closed cleanly, even if an exception propagates:

```python
from fleet_config import Client

with Client(
    base_url="https://fleet-config.internal.example.com",
    api_key="fc_live_...",
    timeout=15.0,
) as client:
    client.config.set("agents", "temperature", 0.7, type="number")
```

Calling `client.close()` explicitly is only necessary in long-running processes that manage the lifecycle manually.

### 9.2 Environment Variable Configuration

The SDK reads two environment variables as a convenience layer (it does **not**
require them — all configuration can be passed explicitly as constructor
arguments):

| Environment variable          | Constructor parameter | Purpose |
|-------------------------------|-----------------------|---------|
| `FLEET_CONFIG_URL`            | `base_url`            | API server base URL |
| `FLEET_CONFIG_API_KEY`        | `api_key`             | Bearer token |

```python
# Minimal production setup — credentials come from the environment.
# Useful in containerised deployments (K8s secrets, AWS Secrets Manager,
# Vault, etc.).
import os
from fleet_config import Client

client = Client(
    base_url=os.environ["FLEET_CONFIG_URL"],
    api_key=os.environ["FLEET_CONFIG_API_KEY"],
)
```

The SDK does **not** use `python-dotenv` or any third-party `.env` loader by default. If you want that behaviour, combine with `pydantic-settings` or ` environs `:

```python
from environs import Env
from fleet_config import Client

env = Env()
env.read_env()  # reads .env if present

client = Client(
    base_url=env.str("FLEET_CONFIG_URL"),
    api_key=env.str("FLEET_CONFIG_API_KEY"),
    timeout=env.float("FLEET_CONFIG_TIMEOUT", 30.0),
)
```

### 9.3 Async Support Note (MVP Scope)

The **MVP ships with synchronous transport only**. All methods block on I/O and are **not** coroutine-friendly. This is intentional: the initial surface is kept small so the SDK can be validated against real server behaviour before committing to an async API.

The async roadmap (to be implemented post-MVP) looks like:

```python
# Future (post-MVP) — NOT included in v1.0.0
from fleet_config import AsyncClient

async with AsyncClient(base_url="http://localhost:8080", api_key="...") as client:
    val = await client.config.get("agents", "default_model")
    async for event in client.watch("agents"):
        print(event)
```

Converting the existing sync API to async requires replacing `urllib.request` with `aiohttp` (or `httpx.AsyncClient`) and returning `asyncio` coroutines. The Pydantic models and error hierarchy remain unchanged.

---

## 10. API Surface Summary

### `Client`

| Attribute / method | Type | Notes |
|---|---|---|
| `config` | `ConfigNamespace` | Config CRUD |
| `flags` | `FlagsNamespace` | Feature-flag CRUD + evaluation |
| `watch(ns)` | `Iterator[WatchEvent]` | SSE real-time subscription |
| `close()` | `None` | Close HTTP pool |
| `__enter__` / `__exit__` | `Client` | Context-manager support |

### `ConfigNamespace`

| Method | Returns | HTTP verb |
|---|---|---|
| `get(ns, key)` | `ConfigValue` | `GET /api/v1/config/{ns}/{key}` |
| `set(ns, key, value)` | `ConfigValue` | `PUT /api/v1/config/{ns}/{key}` |
| `delete(ns, key)` | `None` | `DELETE /api/v1/config/{ns}/{key}` |
| `list(ns)` | `list[ConfigValue]` | `GET /api/v1/config/{ns}` |
| `history(ns, key)` | `list[ConfigVersion]` | `GET /api/v1/config/{ns}/{key}/history` |

### `FlagsNamespace`

| Method | Returns | HTTP verb |
|---|---|---|
| `create(name, …)` | `FeatureFlag` | `POST /api/v1/flags` |
| `check(name, user_id, …)` | `FlagEvaluation` | `POST /api/v1/flags/{name}/check` |
| `get(name)` | `FeatureFlag` | `GET /api/v1/flags/{name}` |
| `delete(name)` | `None` | `DELETE /api/v1/flags/{name}` |
| `list()` | `list[FeatureFlag]` | `GET /api/v1/flags` |

### Data models (all in `fleet_config.models`)

`ConfigValue` · `ConfigVersion` · `FeatureFlag` · `FlagRule` · `FlagEvaluation` · `WatchEvent`

### Errors (all in `fleet_config.errors`)

`FleetConfigError` · `AuthenticationError` · `PermissionDeniedError` · `NotFoundError` · `ConflictError` · `ValidationError` · `RateLimitError` · `ServerError` · `ConnectionError`

---

*End of document.*
