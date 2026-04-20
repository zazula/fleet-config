# fleet-config-sdk

Python SDK for the `fleet-config` service.

## Install

```bash
pip install fleet-config-sdk
```

## Usage

```python
from fleet_config import FleetConfigClient

client = FleetConfigClient("http://localhost:8000")
config = client.get_config("retry_count", namespace="agents")
enabled = client.evaluate_flag("beta-access", user_id="user-123")

for event in client.watch(namespace="agents"):
    print(event.key, event.version)
```

## API notes

- `set_config()` creates a config with `POST /api/v1/configs` and updates with `PUT /api/v1/configs/{namespace}/{key}`.
- `list_configs()` is implemented client-side against known service capabilities and currently uses namespace/key reads only where available. It raises `ServiceError` if the server does not support listing.
- `watch()` consumes Server-Sent Events from `/api/v1/watch` or `/api/v1/watch/{namespace}`.
