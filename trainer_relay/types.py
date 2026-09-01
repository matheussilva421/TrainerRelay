"""Closed wire-state vocabularies and immutable command boundaries."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any


class _WireState(str, Enum):
    def __str__(self) -> str:
        return self.value


class DiscoveryState(_WireState):
    WAITING_FOR_GAME = "waiting_for_game"
    SESSION = "session"
    AMBIGUOUS = "ambiguous"
    INVALID_CONFIG = "invalid_config"


class RelayStatus(_WireState):
    DISABLED = "disabled"
    WAITING_FOR_GAME = "waiting_for_game"
    LAUNCHING = "launching"
    RUNNING = "running"
    RETRYING = "retrying"
    FAILED = "failed"
    AMBIGUOUS = "ambiguous"
    INVALID_CONFIG = "invalid_config"


class CommandContextError(ValueError):
    """A bounded reason why a command context could not be issued."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class CommandContext:
    """The minimal verified snapshot a one-shot command is allowed to use."""

    identity: str
    session: Any
    trainer_sha256: str
    trainer_arch: str
    environment: Mapping[str, str]
    umu_run: str
    expected_reentry_bus: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "environment", MappingProxyType(dict(self.environment)))
