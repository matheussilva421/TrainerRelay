"""Fail-closed boundary for the Trainer Relay Cooperative Control v1 protocol.

This module deliberately contains no socket implementation.  A trainer must
provide a validated endpoint descriptor before a caller is given a transport
client, and all state returned by a client is decoded and freshness-checked
before it can be considered authoritative.
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .cheat_config import SHA256_PATTERN, validate_label
from .config import validate_launch_identity
from .hotkeys import normalize_hotkey


PROTOCOL_NAME = "TrainerRelay Cooperative Control v1"
SCHEMA_VERSION = 1
MAX_ENDPOINT_ADDRESS_LENGTH = 256
MAX_CAPABILITY_TOKEN_LENGTH = 512
MAX_CHEATS = 64
MAX_OPERATIONS = 3
MAX_REVISION = 2**63 - 1
MAX_FRESHNESS_SECONDS = 300.0
_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_OPERATIONS = frozenset({"enable", "disable", "toggle"})
_STATES = frozenset({"unknown", "enabled", "disabled"})


class CooperativeProtocolError(ValueError):
    """A bounded reason why a cooperative message cannot be trusted."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _error(code: str) -> None:
    raise CooperativeProtocolError(code)


def _require_mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        _error(code)
    return value


def _require_exact_keys(value: Mapping[str, Any], required: set[str], optional: set[str] = set()) -> None:
    if set(value) - required - optional != set() or not required.issubset(value):
        _error("cooperative_schema_invalid")


def _safe_text(value: Any, *, maximum: int, code: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= maximum:
        _error(code)
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        _error(code)
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        _error(code)
    return value


def _validate_identifier(value: Any) -> str:
    if not isinstance(value, str) or _IDENTIFIER_PATTERN.fullmatch(value) is None:
        _error("cooperative_cheat_id_invalid")
    return value


def _validate_session(value: Any) -> dict[str, int]:
    session = _require_mapping(value, "cooperative_session_invalid")
    _require_exact_keys(session, {"pid", "startTime"})
    if (
        type(session["pid"]) is not int
        or type(session["startTime"]) is not int
        or session["pid"] <= 0
        or session["startTime"] < 0
    ):
        _error("cooperative_session_invalid")
    return {"pid": session["pid"], "startTime": session["startTime"]}


def _session_wire(value: Any) -> dict[str, int]:
    if isinstance(value, Mapping):
        return _validate_session(value)
    pid = getattr(value, "pid", None)
    start_time = getattr(value, "start_time", None)
    return _validate_session({"pid": pid, "startTime": start_time})


def _validate_endpoint(value: Any) -> dict[str, str]:
    endpoint = _require_mapping(value, "cooperative_endpoint_invalid")
    _require_exact_keys(endpoint, {"transport", "address"})
    if endpoint["transport"] != "unix":
        _error("cooperative_endpoint_invalid")
    address = _safe_text(endpoint["address"], maximum=MAX_ENDPOINT_ADDRESS_LENGTH, code="cooperative_endpoint_invalid")
    if not (address.startswith("/") or address.startswith("@")):
        _error("cooperative_endpoint_invalid")
    return {"transport": "unix", "address": address}


def _validate_operations(value: Any, *, code: str) -> tuple[str, ...]:
    if type(value) is not list or not 1 <= len(value) <= MAX_OPERATIONS:
        _error(code)
    operations: list[str] = []
    for operation in value:
        if not isinstance(operation, str) or operation not in _OPERATIONS or operation in operations:
            _error(code)
        operations.append(operation)
    return tuple(operations)


@dataclass(frozen=True)
class CooperativeCheatDescriptor:
    id: str
    label: str
    operations: tuple[str, ...]
    state: str
    hotkey: Mapping[str, Any] | None = None

    def to_wire(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "operations": list(self.operations),
            "state": self.state,
        }
        if self.hotkey is not None:
            value["hotkey"] = {"modifiers": list(self.hotkey["modifiers"]), "key": self.hotkey["key"]}
        return value


def _decode_cheat(value: Any) -> CooperativeCheatDescriptor:
    cheat = _require_mapping(value, "cooperative_cheat_invalid")
    _require_exact_keys(cheat, {"id", "label", "operations", "state"}, {"hotkey"})
    cheat_id = _validate_identifier(cheat["id"])
    try:
        label = validate_label(cheat["label"])
    except ValueError:
        _error("cooperative_cheat_invalid")
    operations = _validate_operations(cheat["operations"], code="cooperative_operations_invalid")
    state = cheat["state"]
    if not isinstance(state, str) or state not in _STATES:
        _error("cooperative_state_invalid")
    hotkey = None
    if "hotkey" in cheat:
        try:
            hotkey = normalize_hotkey(cheat["hotkey"])
        except ValueError:
            _error("cooperative_hotkey_invalid")
    return CooperativeCheatDescriptor(cheat_id, label, operations, state, hotkey)


@dataclass(frozen=True)
class CooperativeDescriptor:
    identity: str
    trainer_sha256: str
    session: Mapping[str, int]
    endpoint: Mapping[str, str]
    capability_token: str
    revision: int
    operations: tuple[str, ...]
    cheats: tuple[CooperativeCheatDescriptor, ...]
    trainer_label: str | None = None

    @property
    def protocol(self) -> str:
        return PROTOCOL_NAME

    @property
    def schema_version(self) -> int:
        return SCHEMA_VERSION

    def cheat(self, cheat_id: str) -> CooperativeCheatDescriptor | None:
        return next((cheat for cheat in self.cheats if cheat.id == cheat_id), None)

    def to_wire(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "protocol": PROTOCOL_NAME,
            "schemaVersion": SCHEMA_VERSION,
            "identity": self.identity,
            "trainerSha256": self.trainer_sha256,
            "session": dict(self.session),
            "endpoint": dict(self.endpoint),
            "capabilityToken": self.capability_token,
            "revision": self.revision,
            "operations": list(self.operations),
            "cheats": [cheat.to_wire() for cheat in self.cheats],
        }
        if self.trainer_label is not None:
            value["trainerLabel"] = self.trainer_label
        return value


def decode_cooperative_descriptor(
    value: Any,
    *,
    expected_identity: str | None = None,
    expected_trainer_sha256: str | None = None,
    expected_session: Any | None = None,
    expected_capability_token: str | None = None,
    previous_revision: int | None = None,
) -> CooperativeDescriptor:
    descriptor = _require_mapping(value, "cooperative_descriptor_invalid")
    _require_exact_keys(
        descriptor,
        {
            "protocol",
            "schemaVersion",
            "identity",
            "trainerSha256",
            "session",
            "endpoint",
            "capabilityToken",
            "revision",
            "operations",
            "cheats",
        },
        {"trainerLabel"},
    )
    if descriptor["protocol"] != PROTOCOL_NAME or type(descriptor["schemaVersion"]) is not int or descriptor["schemaVersion"] != SCHEMA_VERSION:
        _error("cooperative_protocol_unsupported")
    try:
        identity = validate_launch_identity(descriptor["identity"])
    except ValueError:
        _error("cooperative_identity_mismatch")
    trainer_sha256 = descriptor["trainerSha256"]
    if not isinstance(trainer_sha256, str) or SHA256_PATTERN.fullmatch(trainer_sha256) is None:
        _error("cooperative_build_invalid")
    session = _validate_session(descriptor["session"])
    endpoint = _validate_endpoint(descriptor["endpoint"])
    capability_token = _safe_text(
        descriptor["capabilityToken"], maximum=MAX_CAPABILITY_TOKEN_LENGTH, code="cooperative_capability_invalid"
    )
    revision = descriptor["revision"]
    if (
        type(revision) is not int
        or not 0 <= revision <= MAX_REVISION
        or previous_revision is not None
        and revision < previous_revision
    ):
        _error("cooperative_revision_invalid")
    operations = _validate_operations(descriptor["operations"], code="cooperative_operations_invalid")
    raw_cheats = descriptor["cheats"]
    if type(raw_cheats) is not list or not 1 <= len(raw_cheats) <= MAX_CHEATS:
        _error("cooperative_cheats_invalid")
    cheats = tuple(_decode_cheat(raw) for raw in raw_cheats)
    seen_ids: set[str] = set()
    for cheat in cheats:
        if cheat.id in seen_ids or not set(cheat.operations).issubset(operations):
            _error("cooperative_cheat_invalid")
        seen_ids.add(cheat.id)
    trainer_label = None
    if "trainerLabel" in descriptor:
        try:
            trainer_label = validate_label(descriptor["trainerLabel"])
        except ValueError:
            _error("cooperative_trainer_label_invalid")

    if expected_identity is not None and identity != expected_identity:
        _error("cooperative_identity_mismatch")
    if expected_trainer_sha256 is not None and trainer_sha256 != expected_trainer_sha256:
        _error("cooperative_build_mismatch")
    if expected_session is not None and session != _session_wire(expected_session):
        _error("cooperative_session_mismatch")
    if expected_capability_token is not None and capability_token != expected_capability_token:
        _error("cooperative_capability_mismatch")
    return CooperativeDescriptor(identity, trainer_sha256, session, endpoint, capability_token, revision, operations, cheats, trainer_label)


@dataclass(frozen=True)
class CooperativeAck:
    identity: str
    trainer_sha256: str
    session: Mapping[str, int]
    command_id: str
    cheat_id: str
    operation: str
    accepted: bool
    state: str
    revision: int
    fresh_until: float
    fresh: bool
    reason: str | None = None
    capability_token: str = ""

    def to_wire(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "protocol": PROTOCOL_NAME,
            "schemaVersion": SCHEMA_VERSION,
            "identity": self.identity,
            "trainerSha256": self.trainer_sha256,
            "session": dict(self.session),
            "capabilityToken": self.capability_token,
            "commandId": self.command_id,
            "cheatId": self.cheat_id,
            "operation": self.operation,
            "accepted": self.accepted,
            "state": self.state,
            "revision": self.revision,
            "freshUntil": self.fresh_until,
        }
        if self.reason is not None:
            value["reason"] = self.reason
        return value


def _validate_command_id(value: Any) -> str:
    if not isinstance(value, str) or _UUID_PATTERN.fullmatch(value) is None:
        _error("cooperative_command_id_invalid")
    try:
        uuid.UUID(value)
    except (AttributeError, ValueError):
        _error("cooperative_command_id_invalid")
    return value


def _validate_number(value: Any, code: str) -> float:
    if type(value) not in {int, float}:
        _error(code)
    try:
        result = float(value)
    except (OverflowError, ValueError):
        _error(code)
    if result != result or result in {float("inf"), float("-inf")}:
        _error(code)
    return result


def decode_cooperative_ack(
    value: Any,
    *,
    descriptor: CooperativeDescriptor,
    expected_command_id: str,
    now: float | None = None,
    previous_revision: int | None = None,
) -> CooperativeAck:
    ack = _require_mapping(value, "cooperative_ack_invalid")
    _require_exact_keys(
        ack,
        {
            "protocol",
            "schemaVersion",
            "identity",
            "trainerSha256",
            "session",
            "capabilityToken",
            "commandId",
            "cheatId",
            "operation",
            "accepted",
            "state",
            "revision",
            "freshUntil",
        },
        {"reason"},
    )
    if ack["protocol"] != PROTOCOL_NAME or type(ack["schemaVersion"]) is not int or ack["schemaVersion"] != SCHEMA_VERSION:
        _error("cooperative_protocol_unsupported")
    try:
        identity = validate_launch_identity(ack["identity"])
    except ValueError:
        _error("cooperative_identity_mismatch")
    trainer_sha256 = ack["trainerSha256"]
    if not isinstance(trainer_sha256, str) or SHA256_PATTERN.fullmatch(trainer_sha256) is None:
        _error("cooperative_build_invalid")
    session = _validate_session(ack["session"])
    capability_token = _safe_text(
        ack["capabilityToken"], maximum=MAX_CAPABILITY_TOKEN_LENGTH, code="cooperative_capability_invalid"
    )
    command_id = _validate_command_id(ack["commandId"])
    expected_id = _validate_command_id(expected_command_id)
    cheat_id = _validate_identifier(ack["cheatId"])
    operation = ack["operation"]
    if not isinstance(operation, str) or operation not in descriptor.operations:
        _error("cooperative_operation_invalid")
    cheat = descriptor.cheat(cheat_id)
    if cheat is None or operation not in cheat.operations:
        _error("cooperative_cheat_invalid")
    if command_id != expected_id:
        _error("cooperative_command_id_mismatch")
    if identity != descriptor.identity or trainer_sha256 != descriptor.trainer_sha256 or session != dict(descriptor.session):
        _error("cooperative_binding_mismatch")
    if capability_token != descriptor.capability_token:
        _error("cooperative_capability_mismatch")
    accepted = ack["accepted"]
    if type(accepted) is not bool:
        _error("cooperative_ack_invalid")
    state = ack["state"]
    if not isinstance(state, str) or state not in _STATES or (accepted and state not in {"enabled", "disabled"}) or (not accepted and state != "unknown"):
        _error("cooperative_state_invalid")
    revision = ack["revision"]
    if (
        type(revision) is not int
        or not 0 <= revision <= MAX_REVISION
        or revision < descriptor.revision
        or previous_revision is not None
        and revision < previous_revision
    ):
        _error("cooperative_revision_invalid")
    fresh_until = _validate_number(ack["freshUntil"], "cooperative_freshness_invalid")
    observed_now = time.monotonic() if now is None else _validate_number(now, "cooperative_freshness_invalid")
    if fresh_until > observed_now + MAX_FRESHNESS_SECONDS:
        _error("cooperative_freshness_invalid")
    fresh = fresh_until > observed_now
    reason = None
    if "reason" in ack:
        reason = _safe_text(ack["reason"], maximum=256, code="cooperative_reason_invalid")
    return CooperativeAck(
        identity,
        trainer_sha256,
        session,
        command_id,
        cheat_id,
        operation,
        accepted,
        state if fresh else "unknown",
        revision,
        fresh_until,
        fresh,
        reason,
        capability_token,
    )


class CooperativeControlClient:
    """A transport callback gated by an already validated descriptor."""

    def __init__(self, descriptor: CooperativeDescriptor, request: Callable[[Mapping[str, Any]], Any]) -> None:
        if not isinstance(descriptor, CooperativeDescriptor) or not callable(request):
            raise ValueError("cooperative_transport_invalid")
        try:
            self.descriptor = decode_cooperative_descriptor(descriptor.to_wire())
        except Exception:
            raise ValueError("cooperative_transport_invalid") from None
        self._request = request

    def send(self, command_id: str, cheat_id: str, operation: str, *, now: float | None = None) -> CooperativeAck:
        command_id = _validate_command_id(command_id)
        cheat_id = _validate_identifier(cheat_id)
        cheat = self.descriptor.cheat(cheat_id)
        if cheat is None or operation not in self.descriptor.operations or operation not in cheat.operations:
            _error("cooperative_operation_invalid")
        payload = {
            "protocol": PROTOCOL_NAME,
            "schemaVersion": SCHEMA_VERSION,
            "identity": self.descriptor.identity,
            "trainerSha256": self.descriptor.trainer_sha256,
            "session": dict(self.descriptor.session),
            "capabilityToken": self.descriptor.capability_token,
            "commandId": command_id,
            "cheatId": cheat_id,
            "operation": operation,
        }
        raw_ack = self._request(payload)
        return decode_cooperative_ack(
            raw_ack,
            descriptor=self.descriptor,
            expected_command_id=command_id,
            now=now,
        )


class CooperativeControlBoundary:
    """Create a client only from a valid descriptor; never opens a socket."""

    def __init__(self, request: Callable[[Mapping[str, Any]], Any] | None = None) -> None:
        self._request = request

    def client_for(self, descriptor: Any) -> CooperativeControlClient | None:
        if self._request is None:
            return None
        try:
            decoded = decode_cooperative_descriptor(
                descriptor.to_wire() if isinstance(descriptor, CooperativeDescriptor) else descriptor
            )
            return CooperativeControlClient(decoded, self._request)
        except Exception:
            return None


decode_descriptor = decode_cooperative_descriptor
decode_ack = decode_cooperative_ack

__all__ = [
    "CooperativeAck",
    "CooperativeCheatDescriptor",
    "CooperativeControlBoundary",
    "CooperativeControlClient",
    "CooperativeDescriptor",
    "CooperativeProtocolError",
    "PROTOCOL_NAME",
    "SCHEMA_VERSION",
    "decode_ack",
    "decode_cooperative_ack",
    "decode_cooperative_descriptor",
    "decode_descriptor",
]
