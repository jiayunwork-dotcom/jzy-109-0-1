"""Registry of named bridge configurations ("bridge presets" / 电桥档).

State lives in process memory only: nothing persists across restarts, and
that is deliberate. Each preset stores its own four arm values, so two
different presets are fully independent -- changing one never affects the
arms seen under another name.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

from .balance import ARMS
from .validation import validate_arms, validate_config_name


class ConfigNotFoundError(LookupError):
    """Raised when a named preset does not exist."""


@dataclass(frozen=True)
class BridgeConfig:
    """One named four-arm configuration."""

    name: str
    r1: float
    r2: float
    r3: float
    r4: float

    def arms(self) -> dict[str, float]:
        return {arm: getattr(self, arm) for arm in ARMS}


class BridgeRegistry:
    """Thread-safe in-memory store of :class:`BridgeConfig` presets."""

    def __init__(self) -> None:
        self._configs: dict[str, BridgeConfig] = {}
        self._lock = threading.Lock()

    def register(self, name: str, arms: dict[str, float]) -> BridgeConfig:
        """Create or replace a preset. Re-registering overwrites."""
        config_name = validate_config_name(name)
        valid = validate_arms(arms)
        config = BridgeConfig(name=config_name, **valid)
        with self._lock:
            self._configs[config_name] = config
        return config

    def get(self, name: str) -> BridgeConfig:
        try:
            with self._lock:
                return self._configs[name]
        except KeyError:
            raise ConfigNotFoundError(
                f"no bridge preset named {name!r}; register it via POST /configs"
            ) from None

    def list(self) -> list[BridgeConfig]:
        with self._lock:
            return list(self._configs.values())

    def delete(self, name: str) -> None:
        config_name = validate_config_name(name)
        with self._lock:
            if config_name not in self._configs:
                raise ConfigNotFoundError(
                    f"no bridge preset named {config_name!r}"
                )
            del self._configs[config_name]

    def clear(self) -> None:
        """Drop every preset (used by tests)."""
        with self._lock:
            self._configs.clear()


# Module-level singleton used by the HTTP layer.
registry = BridgeRegistry()
