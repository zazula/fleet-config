from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ConfigKey:
    namespace: str
    key: str
    value: Any
    version: int


@dataclass(slots=True)
class FeatureFlag:
    name: str
    enabled: bool
    rollout_pct: float | None = None
    rules: dict[str, Any] | None = None


@dataclass(slots=True)
class ConfigChangeEvent:
    type: str
    namespace: str
    key: str
    version: int
    timestamp: datetime
