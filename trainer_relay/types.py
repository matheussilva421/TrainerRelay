"""Closed wire-state vocabularies shared by discovery and the watcher."""

from enum import Enum


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
