"""Read-only, exact-SHA-256 FLiNG adapter catalog."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cheat_config import SHA256_PATTERN, validate_label, validate_trainer_sha256
from .config import is_launch_identity, validate_launch_identity
from .hotkeys import normalize_hotkey


CATALOG_SCHEMA_VERSION = 1
CATALOG_FILENAME = "fling_adapters_v1.json"
_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_ARCHITECTURES = {"x86", "x64"}
_MAX_CHEATS_PER_ADAPTER = 64
_MAX_HOTKEYS_PER_CHEAT = 8


class _FrozenList(list[Any]):
    """A JSON-compatible list that cannot be mutated through normal methods."""

    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("immutable_catalog_descriptor")

    __delitem__ = __setitem__ = __iadd__ = __imul__ = _immutable
    append = clear = extend = insert = pop = remove = reverse = sort = _immutable


class _FrozenHotkey(dict[str, Any]):
    def __init__(self, value: Mapping[str, Any]) -> None:
        super().__init__(
            modifiers=_FrozenList(value["modifiers"]),
            key=value["key"],
        )

    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("immutable_catalog_descriptor")

    __delitem__ = __setitem__ = __ior__ = clear = pop = popitem = setdefault = update = _immutable


def _freeze_hotkey(value: Mapping[str, Any]) -> _FrozenHotkey:
    return _FrozenHotkey(value)


def _wire_hotkey(value: Mapping[str, Any]) -> dict[str, Any]:
    return {"modifiers": list(value["modifiers"]), "key": value["key"]}


@dataclass(frozen=True)
class CheatDescriptor:
    id: str
    label: str
    hotkey: Mapping[str, Any]
    hotkeys: tuple[Mapping[str, Any], ...]

    def to_wire(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "hotkey": _wire_hotkey(self.hotkey),
        }
        if len(self.hotkeys) > 1:
            result["hotkeys"] = [_wire_hotkey(value) for value in self.hotkeys]
        return result


@dataclass(frozen=True)
class AdapterDescriptor:
    adapter_id: str
    sha256: str
    pe_architecture: str
    trainer_label: str
    supported_identities: tuple[str, ...]
    cheats: tuple[CheatDescriptor, ...]
    disable_all_hotkey: Mapping[str, Any]

    @property
    def id(self) -> str:
        return self.adapter_id

    @property
    def exact_sha256(self) -> str:
        return self.sha256

    def to_wire(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.adapter_id,
            "sha256": self.sha256,
            "peArchitecture": self.pe_architecture,
            "trainerLabel": self.trainer_label,
            "cheats": [cheat.to_wire() for cheat in self.cheats],
            "disableAllHotkey": _wire_hotkey(self.disable_all_hotkey),
        }
        if self.supported_identities:
            result["supportedIdentities"] = list(self.supported_identities)
        return result


class CheatCatalog:
    def __init__(self, adapters: tuple[AdapterDescriptor, ...]) -> None:
        self.adapters = adapters
        self._by_sha256 = {adapter.sha256: adapter for adapter in adapters}

    @classmethod
    def load(cls, path: Path) -> "CheatCatalog":
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, TypeError, UnicodeError, ValueError) as error:
            raise ValueError("invalid_cheat_catalog") from error
        try:
            adapters = _decode_catalog(document)
        except ValueError as error:
            raise ValueError("invalid_cheat_catalog") from error
        return cls(adapters)

    def resolve(self, sha256: str, identity: str) -> AdapterDescriptor | None:
        if not isinstance(sha256, str) or SHA256_PATTERN.fullmatch(sha256) is None:
            return None
        if not is_launch_identity(identity):
            return None
        adapter = self._by_sha256.get(sha256)
        if adapter is None:
            return None
        if adapter.supported_identities and identity not in adapter.supported_identities:
            return None
        return adapter


def _validate_identifier(value: Any, code: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise ValueError(code)
    return value


def _decode_cheat(value: Any) -> CheatDescriptor:
    if not isinstance(value, Mapping):
        raise ValueError("invalid_cheat_descriptor")
    keys = set(value)
    if "hotkey" in value and "hotkeys" in value:
        raise ValueError("invalid_cheat_descriptor")
    if keys not in ({"id", "label", "hotkey"}, {"id", "label", "hotkeys"}):
        raise ValueError("invalid_cheat_descriptor")
    cheat_id = _validate_identifier(value.get("id"), "invalid_cheat_id")
    label = validate_label(value.get("label"))
    if "hotkey" in value:
        normalized_hotkeys = (normalize_hotkey(value["hotkey"]),)
    else:
        raw_hotkeys = value["hotkeys"]
        if type(raw_hotkeys) is not list or not 1 <= len(raw_hotkeys) <= _MAX_HOTKEYS_PER_CHEAT:
            raise ValueError("invalid_cheat_hotkeys")
        normalized_hotkeys = tuple(normalize_hotkey(hotkey) for hotkey in raw_hotkeys)
    frozen_hotkeys = tuple(_freeze_hotkey(hotkey) for hotkey in normalized_hotkeys)
    return CheatDescriptor(
        id=cheat_id,
        label=label,
        hotkey=frozen_hotkeys[0],
        hotkeys=frozen_hotkeys,
    )


def _decode_adapter(value: Any) -> AdapterDescriptor:
    if not isinstance(value, Mapping):
        raise ValueError("invalid_adapter")
    required = {"id", "sha256", "peArchitecture", "trainerLabel", "cheats"}
    optional = {"supportedIdentities", "disableAllHotkey"}
    if set(value) - required - optional != set() or not required.issubset(value):
        raise ValueError("invalid_adapter")
    adapter_id = _validate_identifier(value["id"], "invalid_adapter_id")
    sha256 = validate_trainer_sha256(value["sha256"])
    pe_architecture = value["peArchitecture"]
    if pe_architecture not in _ARCHITECTURES:
        raise ValueError("invalid_pe_architecture")
    trainer_label = validate_label(value["trainerLabel"])

    supported_identities_value = value.get("supportedIdentities", [])
    if type(supported_identities_value) is not list:
        raise ValueError("invalid_supported_identities")
    supported_identities: list[str] = []
    for identity in supported_identities_value:
        validated_identity = validate_launch_identity(identity)
        if validated_identity in supported_identities:
            raise ValueError("duplicate_supported_identity")
        supported_identities.append(validated_identity)

    raw_cheats = value["cheats"]
    if type(raw_cheats) is not list or not 1 <= len(raw_cheats) <= _MAX_CHEATS_PER_ADAPTER:
        raise ValueError("invalid_adapter_cheats")
    cheats: list[CheatDescriptor] = []
    seen_cheat_ids: set[str] = set()
    for raw_cheat in raw_cheats:
        descriptor = _decode_cheat(raw_cheat)
        if descriptor.id in seen_cheat_ids:
            raise ValueError("duplicate_cheat_id")
        seen_cheat_ids.add(descriptor.id)
        cheats.append(descriptor)

    disable_all = normalize_hotkey(value.get("disableAllHotkey", {"modifiers": [], "key": "HOME"}))
    return AdapterDescriptor(
        adapter_id=adapter_id,
        sha256=sha256,
        pe_architecture=pe_architecture,
        trainer_label=trainer_label,
        supported_identities=tuple(supported_identities),
        cheats=tuple(cheats),
        disable_all_hotkey=_freeze_hotkey(disable_all),
    )


def _decode_catalog(value: Any) -> tuple[AdapterDescriptor, ...]:
    if not isinstance(value, Mapping) or set(value) != {"schemaVersion", "adapters"}:
        raise ValueError("invalid_catalog")
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != CATALOG_SCHEMA_VERSION:
        raise ValueError("invalid_catalog_schema")
    raw_adapters = value["adapters"]
    if type(raw_adapters) is not list or not raw_adapters:
        raise ValueError("invalid_catalog_adapters")

    adapters: list[AdapterDescriptor] = []
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    for raw_adapter in raw_adapters:
        descriptor = _decode_adapter(raw_adapter)
        if descriptor.adapter_id in seen_ids:
            raise ValueError("duplicate_adapter_id")
        if descriptor.sha256 in seen_hashes:
            raise ValueError("duplicate_adapter_sha256")
        seen_ids.add(descriptor.adapter_id)
        seen_hashes.add(descriptor.sha256)
        adapters.append(descriptor)
    return tuple(adapters)


def packaged_catalog_path() -> Path:
    source_path = Path(__file__).resolve().parent / "data" / CATALOG_FILENAME
    if source_path.is_file():
        return source_path
    return Path(__file__).resolve().parents[2] / "data" / CATALOG_FILENAME


def load_packaged_catalog() -> CheatCatalog:
    return CheatCatalog.load(packaged_catalog_path())
