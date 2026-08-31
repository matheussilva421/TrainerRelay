"""Fail-closed probe for UMU's same-prefix launcher service.

The launcher service that ``UMU_CONTAINER_NSENTER=1`` exposes is registered on
the *host* user-session D-Bus, because Decky runs this plugin as the host user.
The game-runtime environment copied out of a pressure-vessel descendant points
``DBUS_SESSION_BUS_ADDRESS`` at an in-container bus that the plugin cannot reach,
so the probe must resolve a host-visible session bus independently of the
game-runtime variables and hand the selected context back to the sidecar.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_RUNTIME_VARIANTS = {
    "1391110": "steamrt2",
    "1628350": "steamrt3",
    "4183110": "steamrt4",
    "4185400": "steamrt4-arm64",
}
_APP_ID_PATTERN = re.compile(r'"require_tool_appid"\s*"([0-9]+)"')
# Game-runtime D-Bus variables must never be trusted for the host-side probe.
_GAME_DBUS_KEYS = (
    "DBUS_SESSION_BUS_ADDRESS",
    "DBUS_STARTER_ADDRESS",
    "DBUS_STARTER_BUS_TYPE",
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(?:[\w-]*(?:token|secret|password|passwd|cookie|authorization|"
    r"credential|api[_-]?key|access[_-]?key|private[_-]?key)[\w-]*)\s*[=:]\s*\S+"
)


def _bounded_detail(text: Any, *, limit: int = 160) -> str:
    redacted = _SECRET_ASSIGNMENT.sub("[redacted]", str(text))
    collapsed = " ".join(redacted.split())
    return collapsed[:limit]


class ContainerReentryError(RuntimeError):
    """A bounded code describing why same-container re-entry is unavailable."""

    def __init__(self, code: str, *, evidence: Mapping[str, Any] | None = None) -> None:
        super().__init__(code)
        self.evidence: dict[str, Any] = dict(evidence) if evidence is not None else {}


@dataclass(frozen=True)
class _HostBus:
    address: str
    source: str


@dataclass(frozen=True)
class ContainerReentryResolution:
    launch_client: Path
    bus_name: str
    runtime_variant: str
    attempts: int
    dbus_address: str
    dbus_source: str


class ContainerReentryProbe:
    def __init__(
        self,
        home: str | os.PathLike[str],
        *,
        run: Callable[..., Any] = subprocess.run,
        sleep: Callable[[float], None] = time.sleep,
        attempts: int = 5,
        delay_seconds: float = 1.0,
        host_environ: Mapping[str, str] | None = None,
        getuid: Callable[[], int] | None = None,
    ) -> None:
        if attempts < 1:
            raise ValueError("invalid_container_probe")
        self._home = Path(home)
        self._run = run
        self._sleep = sleep
        self._attempts = attempts
        self._delay_seconds = delay_seconds
        self._host_environ = dict(host_environ) if host_environ is not None else dict(os.environ)
        self._getuid = getuid if getuid is not None else getattr(os, "getuid", None)

    @staticmethod
    def _runtime_variant(proton_path: Path) -> str:
        manifest = proton_path / "toolmanifest.vdf"
        try:
            if manifest.stat().st_size > 1024 * 1024:
                raise ContainerReentryError("container_reentry_unsupported")
            source = manifest.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise ContainerReentryError("container_reentry_unsupported") from error
        app_ids = set(_APP_ID_PATTERN.findall(source))
        if len(app_ids) != 1:
            raise ContainerReentryError("container_reentry_unsupported")
        variant = _RUNTIME_VARIANTS.get(next(iter(app_ids)))
        if variant is None:
            raise ContainerReentryError("container_reentry_unsupported")
        return variant

    def _host_bus_candidates(self) -> list[_HostBus]:
        seen: set[str] = set()
        candidates: list[_HostBus] = []

        def add(address: str | None, source: str) -> None:
            if not isinstance(address, str) or not address or address in seen:
                return
            seen.add(address)
            candidates.append(_HostBus(address, source))

        add(self._host_environ.get("DBUS_SESSION_BUS_ADDRESS"), "host_env")
        runtime_dir = self._host_environ.get("XDG_RUNTIME_DIR")
        if isinstance(runtime_dir, str) and runtime_dir:
            add(f"unix:path={runtime_dir.rstrip('/')}/bus", "xdg_runtime_dir")
        if self._getuid is not None:
            try:
                uid = self._getuid()
            except OSError:
                uid = None
            if uid is not None:
                add(f"unix:path=/run/user/{int(uid)}/bus", "uid_default")
        return candidates

    def _verify_sync(self, environment: Mapping[str, str]) -> ContainerReentryResolution:
        try:
            prefix = Path(environment["WINEPREFIX"]).expanduser().resolve(strict=False)
            proton_path = Path(environment["PROTONPATH"]).expanduser().resolve(strict=True)
        except (KeyError, OSError) as error:
            raise ContainerReentryError("container_reentry_unsupported") from error

        variant = self._runtime_variant(proton_path)
        if "UMU_FOLDERS_PATH" in environment:
            folders_root = Path(environment["UMU_FOLDERS_PATH"])
            if not environment["UMU_FOLDERS_PATH"] or not folders_root.is_absolute():
                raise ContainerReentryError("container_reentry_unsupported")
            umu_root = folders_root / "umu"
        else:
            data_home = Path(environment.get("XDG_DATA_HOME", self._home / ".local" / "share"))
            if not data_home.is_absolute():
                raise ContainerReentryError("container_reentry_unsupported")
            umu_root = data_home / "umu"
        launch_client = umu_root / variant / "pressure-vessel" / "bin" / "steam-runtime-launch-client"
        try:
            launch_client = launch_client.resolve(strict=True)
        except OSError as error:
            raise ContainerReentryError("container_reentry_unsupported") from error
        if not launch_client.is_file() or not os.access(launch_client, os.X_OK):
            raise ContainerReentryError("container_reentry_unsupported")

        candidates = self._host_bus_candidates()
        if not candidates:
            raise ContainerReentryError(
                "container_reentry_probe_failed",
                evidence={"returncode": None, "detail": "no_host_session_bus"},
            )

        digest = hashlib.md5(str(prefix).encode("utf-8"), usedforsecurity=False).hexdigest()
        bus_name = f"com.steampowered.App{digest}"
        expected = f"--bus-name={bus_name}"
        base_environment = {
            key: value
            for key, value in environment.items()
            if isinstance(key, str) and isinstance(value, str) and key not in _GAME_DBUS_KEYS
        }

        saw_reachable = False
        last_failure: dict[str, Any] = {"returncode": None, "detail": "unknown"}
        for attempt in range(1, self._attempts + 1):
            for candidate in candidates:
                probe_environment = dict(base_environment)
                probe_environment["DBUS_SESSION_BUS_ADDRESS"] = candidate.address
                try:
                    result = self._run(
                        [str(launch_client), "--list"],
                        env=probe_environment,
                        shell=False,
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=2.0,
                    )
                except (OSError, subprocess.SubprocessError) as error:
                    last_failure = {"returncode": None, "detail": _bounded_detail(error)}
                    continue
                if result.returncode != 0:
                    last_failure = {
                        "returncode": int(result.returncode),
                        "detail": _bounded_detail(result.stderr),
                    }
                    continue
                saw_reachable = True
                if expected in str(result.stdout).splitlines():
                    return ContainerReentryResolution(
                        launch_client=launch_client,
                        bus_name=bus_name,
                        runtime_variant=variant,
                        attempts=attempt,
                        dbus_address=candidate.address,
                        dbus_source=candidate.source,
                    )
            if attempt < self._attempts:
                self._sleep(self._delay_seconds)

        if saw_reachable:
            raise ContainerReentryError(
                "container_reentry_bus_missing",
                evidence={"returncode": 0, "detail": "prefix_bus_absent"},
            )
        raise ContainerReentryError("container_reentry_probe_failed", evidence=last_failure)

    async def verify(self, environment: Mapping[str, str]) -> ContainerReentryResolution:
        return await asyncio.to_thread(self._verify_sync, dict(environment))
