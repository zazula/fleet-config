from __future__ import annotations

from typing import Any

import httpx

from fleet_config.errors import ConfigNotFound, FlagNotFound, ServiceError
from fleet_config.models import ConfigKey
from fleet_config.watch import WatchStream


class FleetConfigClient:
    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def get_config(self, key: str, namespace: str = "default") -> ConfigKey:
        response = self._client.get(f"/api/v1/configs/{namespace}/{key}")
        if response.status_code == 404:
            raise ConfigNotFound(f"Config not found: {namespace}/{key}")
        self._raise_for_status(response)
        return self._parse_config(response.json())

    def set_config(self, key: str, value: str, namespace: str = "default") -> ConfigKey:
        create_response = self._client.post(
            "/api/v1/configs",
            json={"namespace": namespace, "key": key, "value": value},
        )
        if create_response.status_code in {200, 201}:
            return self._parse_config(create_response.json())
        if create_response.status_code != 409:
            self._raise_for_status(create_response)

        update_response = self._client.put(
            f"/api/v1/configs/{namespace}/{key}",
            json={"value": value},
        )
        self._raise_for_status(update_response)
        return self._parse_config(update_response.json())

    def delete_config(self, key: str, namespace: str = "default") -> None:
        response = self._client.delete(f"/api/v1/configs/{namespace}/{key}")
        if response.status_code == 404:
            raise ConfigNotFound(f"Config not found: {namespace}/{key}")
        self._raise_for_status(response)

    def list_configs(self, namespace: str | None = None) -> list[ConfigKey]:
        params = {"namespace": namespace} if namespace is not None else None
        response = self._client.get("/api/v1/configs", params=params)
        self._raise_for_status(response)
        payload = response.json()
        return [self._parse_config(item) for item in payload]

    def evaluate_flag(self, flag_key: str, user_id: str) -> bool:
        response = self._client.post(
            f"/api/v1/flags/{flag_key}/evaluate",
            json={"agent_id": user_id, "context": {}},
        )
        if response.status_code == 404:
            raise FlagNotFound(f"Flag not found: {flag_key}")
        self._raise_for_status(response)
        payload = response.json()
        return bool(payload["enabled"])

    def watch(self, namespace: str | None = None) -> WatchStream:
        path = "/api/v1/watch" if namespace is None else f"/api/v1/watch/{namespace}"
        return WatchStream(self._client, path)

    def close(self) -> None:
        self._client.close()

    def _parse_config(self, payload: dict[str, Any]) -> ConfigKey:
        return ConfigKey(
            namespace=payload["namespace"],
            key=payload["key"],
            value=payload["value"],
            version=payload["version"],
        )

    def _raise_for_status(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ServiceError(str(exc)) from exc
