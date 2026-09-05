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


def _umu_prefix_root(prefix_anchor: str) -> str:
    return prefix_anchor.rstrip("/\\") or prefix_anchor


def build_sanitized_environment(source: Mapping[str, str], prefix_anchor: str | None = None) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in source.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        if key == "PROTON_REMOTE_DEBUG_CMD" or _is_secret(key):
            continue
        if key in EXACT_KEYS or key.startswith(ALLOWED_PREFIXES):
            result[key] = value
    result.pop("PROTON_REMOTE_DEBUG_CMD", None)
    # This is derived by umu-run. Replaying the Proton child's value can pin a
    # symlinked Steam root and make pressure-vessel fail before Wine starts.
    result.pop("STEAM_COMPAT_CLIENT_INSTALL_PATH", None)
    # A launcher service inherited from the game points at the existing UMU
    # process. umu-run must resolve the service itself for this invocation.
    result.pop("STEAM_COMPAT_LAUNCHER_SERVICE", None)
    # UMU saves the incoming SteamGameId, then replaces it with its own game
    # ID (usually zero). Restore the saved shortcut ID before the nested UMU
    # invocation, which otherwise overwrites that saved identity with zero.
    original = result.get("UMU_STEAM_GAME_ID", "")
    if (original.isascii() and original.isdecimal() and len(original) <= 20
            and result.get("SteamGameId", "0") in {"0", original}):
        shortcut = int(original)
        if (shortcut < (1 << 64) and shortcut >> 32 >= 0x80000000
                and shortcut & 0xffffffff == 0x02000000):
            result["SteamGameId"] = original
    if prefix_anchor is not None:
        umu_prefix = _umu_prefix_root(prefix_anchor)
        result["WINEPREFIX"] = umu_prefix
        result["STEAM_COMPAT_DATA_PATH"] = umu_prefix
    result["UMU_CONTAINER_NSENTER"] = "1"
    result["PROTON_VERB"] = "runinprefix"
    return result
