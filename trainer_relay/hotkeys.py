"""Finite symbolic hotkey validation and Windows virtual-key mapping."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_MODIFIER_ORDER = ("ctrl", "alt", "shift")
_MODIFIER_BITS = {"ctrl": 1, "alt": 2, "shift": 4}

_KEY_TO_VK = {
    **{chr(code): code for code in range(ord("A"), ord("Z") + 1)},
    **{str(code): 0x30 + code for code in range(10)},
    **{f"F{number}": 0x6F + number for number in range(1, 25)},
    **{f"NUMPAD{number}": 0x60 + number for number in range(10)},
    "MULTIPLY": 0x6A,
    "ADD": 0x6B,
    "SUBTRACT": 0x6D,
    "DECIMAL": 0x6E,
    "DIVIDE": 0x6F,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
    "HOME": 0x24,
    "END": 0x23,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
    "UP": 0x26,
    "DOWN": 0x28,
    "LEFT": 0x25,
    "RIGHT": 0x27,
    "SPACE": 0x20,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "BACKSPACE": 0x08,
    "PAUSE": 0x13,
    "CAPSLOCK": 0x14,
    "SCROLLLOCK": 0x91,
    "NUMLOCK": 0x90,
}


def _require_exact_fields(value: Mapping[str, Any], fields: set[str]) -> None:
    try:
        keys = set(value.keys())
    except (TypeError, ValueError):
        raise ValueError("invalid_hotkey") from None
    if keys != fields:
        raise ValueError("invalid_hotkey")


def normalize_hotkey(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return a canonical copy of a finite symbolic hotkey."""

    if not isinstance(value, Mapping):
        raise ValueError("invalid_hotkey")
    _require_exact_fields(value, {"modifiers", "key"})

    modifiers = value["modifiers"]
    key = value["key"]
    if type(modifiers) is not list or type(key) is not str or key not in _KEY_TO_VK:
        raise ValueError("invalid_hotkey")

    seen: set[str] = set()
    for modifier in modifiers:
        if type(modifier) is not str or modifier not in _MODIFIER_BITS or modifier in seen:
            raise ValueError("invalid_hotkey")
        seen.add(modifier)

    return {
        "modifiers": [modifier for modifier in _MODIFIER_ORDER if modifier in seen],
        "key": key,
    }


def hotkey_to_vk(value: Mapping[str, Any]) -> tuple[int, int]:
    """Return ``(virtual_key, modifier_bitmask)`` for a normalized hotkey."""

    normalized = normalize_hotkey(value)
    virtual_key = _KEY_TO_VK[normalized["key"]]
    modifier_mask = sum(_MODIFIER_BITS[modifier] for modifier in normalized["modifiers"])
    return virtual_key, modifier_mask
