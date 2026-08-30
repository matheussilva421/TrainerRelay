"""Fail-closed probe for UMU's same-prefix launcher service."""

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


class ContainerReentryError(RuntimeError):
    """A bounded code describing why same-container re-entry is unavailable."""


@dataclass(frozen=True)
class ContainerReentryResolution:
    launch_client: Path
    bus_name: str
    runtime_variant: str
    attempts: int


class ContainerReentryProbe:
    def __init__(
        self,
        home: str | os.PathLike[str],
        *,
        run: Callable[..., Any] = subprocess.run,
        sleep: Callable[[float], None] = time.sleep,
        attempts: int = 5,
        delay_seconds: float = 1.0,
    ) -> None:
        if attempts < 1:
            raise ValueError("invalid_container_probe")
        self._home = Path(home)
        self._run = run
        self._sleep = sleep
        self._attempts = attempts
        self._delay_seconds = delay_seconds

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

        digest = hashlib.md5(str(prefix).encode("utf-8"), usedforsecurity=False).hexdigest()
        bus_name = f"com.steampowered.App{digest}"
        expected = f"--bus-name={bus_name}"
        probe_environment = {
            key: value
            for key, value in environment.items()
            if isinstance(key, str) and isinstance(value, str)
        }

        for attempt in range(1, self._attempts + 1):
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
                raise ContainerReentryError("container_reentry_probe_failed") from error
            if result.returncode != 0:
                raise ContainerReentryError("container_reentry_probe_failed")
            if expected in str(result.stdout).splitlines():
                return ContainerReentryResolution(launch_client, bus_name, variant, attempt)
            if attempt < self._attempts:
                self._sleep(self._delay_seconds)
        raise ContainerReentryError("container_reentry_bus_missing")

    async def verify(self, environment: Mapping[str, str]) -> ContainerReentryResolution:
        return await asyncio.to_thread(self._verify_sync, dict(environment))
