"""Build the restricted environment passed to an owned trainer."""

from __future__ import annotations

from collections.abc import Mapping


EXACT_KEYS = {
    "HOME",
    "PATH",
    "LANG",
    "LANGUAGE",
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "XAUTHORITY",
    "DBUS_SESSION_BUS_ADDRESS",
    "XDG_RUNTIME_DIR",
    "XDG_CURRENT_DESKTOP",
    "WINEPREFIX",
    "PROTONPATH",
    "GAMEID",
    "STORE",
    "PROTON_VERB",
    "UMU_LOG",
    "UMU_NO_RUNTIME",
    "UMU_NO_PROTON",
    "UMU_RUNTIME",
    "STEAM_COMPAT_CLIENT_INSTALL_PATH",
    "STEAM_COMPAT_DATA_PATH",
    "STEAM_COMPAT_INSTALL_PATH",
    "STEAM_COMPAT_LIBRARY_PATHS",
    "SteamAppId",
    "SteamGameId",
    "WINEARCH",
    "WINEDEBUG",
    "WINEESYNC",
    "WINEFSYNC",
    "WINEDLLOVERRIDES",
}
ALLOWED_PREFIXES = ("STEAM_COMPAT_", "Steam", "PROTON_", "UMU_", "WINE", "DXVK_", "VKD3D_", "XDG_", "LC_")
SECRET_PARTS = ("TOKEN", "PASSWORD", "SECRET", "COOKIE", "AUTH")


def _is_secret(key: str) -> bool:
    folded = key.upper()
    return any(part in folded for part in SECRET_PARTS)


def build_sanitized_environment(source: Mapping[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in source.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        if key == "PROTON_REMOTE_DEBUG_CMD" or _is_secret(key):
            continue
        if key in EXACT_KEYS or key.startswith(ALLOWED_PREFIXES):
            result[key] = value
    result.pop("PROTON_REMOTE_DEBUG_CMD", None)
    result["PROTON_VERB"] = "runinprefix"
    return result
