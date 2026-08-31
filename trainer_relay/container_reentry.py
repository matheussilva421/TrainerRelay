"""Fail-closed probe for UMU's same-prefix launcher service."""

from __future__ import annotations

import asyncio
import hashlib
import os
import posixpath
import re
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
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

    def __init__(
        self,
        code: str,
        *,
        failure_class: str | None = None,
        exit_code: int | None = None,
        bus_source: str | None = None,
        attempts: int | None = None,
    ) -> None:
        super().__init__(code)
        self.failure_class = failure_class
        self.exit_code = exit_code
        self.bus_source = bus_source
        self.attempts = attempts


@dataclass(frozen=True)
class ContainerReentryResolution:
    launch_client: Path
    bus_name: str
    runtime_variant: str
    attempts: int
    bus_source: str
    app_id_source: str
    session_environment: Mapping[str, str]
    launch_environment: Mapping[str, str]


@dataclass(frozen=True)
class _SessionBusCandidate:
    source: str
    environment: Mapping[str, str]


class ContainerReentryProbe:
    def __init__(
        self,
        home: str | os.PathLike[str],
        *,
        run: Callable[..., Any] = subprocess.run,
        sleep: Callable[[float], None] = time.sleep,
        attempts: int = 5,
        delay_seconds: float = 1.0,
        host_environment: Mapping[str, str] | None = None,
        target_uid: int | None = None,
        getuid: Callable[[], int] | None = None,
    ) -> None:
        if attempts < 1:
            raise ValueError("invalid_container_probe")
        self._home = Path(home)
        self._run = run
        self._sleep = sleep
        self._attempts = attempts
        self._delay_seconds = delay_seconds
        self._host_environment = {
            key: value
            for key, value in (os.environ if host_environment is None else host_environment).items()
            if isinstance(key, str) and isinstance(value, str)
        }
        default_getuid = getattr(os, "getuid", lambda: -1)
        self._getuid = getuid or default_getuid
        if target_uid is None:
            try:
                process_uid = int(self._getuid())
            except (OSError, TypeError, ValueError):
                process_uid = -1
            if process_uid > 0:
                target_uid = process_uid
            else:
                try:
                    target_uid = int(self._home.stat().st_uid)
                except (OSError, TypeError, ValueError):
                    target_uid = -1
        self._target_uid = target_uid

    @staticmethod
    def _absolute_runtime_dir(value: str | None) -> str | None:
        if not value:
            return None
        path = Path(value)
        return value if path.is_absolute() or posixpath.isabs(value) else None

    def _session_bus_candidates(self) -> tuple[_SessionBusCandidate, ...]:
        candidates: list[_SessionBusCandidate] = []
        seen_addresses: set[str] = set()
        host_address = self._host_environment.get("DBUS_SESSION_BUS_ADDRESS", "")
        host_runtime = self._absolute_runtime_dir(self._host_environment.get("XDG_RUNTIME_DIR"))

        try:
            process_uid = int(self._getuid())
        except (TypeError, ValueError, OSError):
            process_uid = -1
        try:
            target_uid = int(self._target_uid)
        except (TypeError, ValueError, OSError):
            target_uid = -1
        target_runtime = f"/run/user/{target_uid}" if target_uid >= 0 else None

        def add(source: str, address: str, runtime_dir: str | None) -> None:
            if not address or address in seen_addresses:
                return
            environment = {"DBUS_SESSION_BUS_ADDRESS": address}
            if runtime_dir is not None:
                environment["XDG_RUNTIME_DIR"] = runtime_dir
            candidates.append(_SessionBusCandidate(source, environment))
            seen_addresses.add(address)

        host_matches_target = (
            target_runtime is None
            or process_uid == target_uid
            or host_runtime == target_runtime
        )
        if host_matches_target:
            add("host_environment", host_address, host_runtime or target_runtime)
        if host_runtime is not None and host_matches_target:
            add("host_runtime_dir", f"unix:path={host_runtime}/bus", host_runtime)
        if target_uid > 0:
            runtime_dir = target_runtime
            assert runtime_dir is not None
            add("home_owner_runtime", f"unix:path={runtime_dir}/bus", runtime_dir)
        return tuple(candidates)

    def _probe_environment(self, session_environment: Mapping[str, str]) -> dict[str, str]:
        result = {
            key: value
            for key, value in self._host_environment.items()
            if key in {"HOME", "PATH", "LANG", "LANGUAGE"} or key.startswith("LC_")
        }
        result.update(session_environment)
        return result

    def _runtime_context(self) -> tuple[Path, dict[str, str]]:
        folders_value = self._host_environment.get("UMU_FOLDERS_PATH")
        if folders_value is not None:
            folders_root = Path(folders_value)
            if not folders_value or not folders_root.is_absolute():
                raise ContainerReentryError("container_reentry_unsupported")
            return folders_root / "umu", {"UMU_FOLDERS_PATH": folders_value}

        data_value = self._host_environment.get("XDG_DATA_HOME")
        if data_value is not None:
            data_home = Path(data_value)
            if not data_value or not data_home.is_absolute():
                raise ContainerReentryError("container_reentry_unsupported")
            return data_home / "umu", {"XDG_DATA_HOME": data_value}

        return self._home / ".local" / "share" / "umu", {}

    def _launch_environment(
        self,
        runtime_environment: Mapping[str, str],
        session_environment: Mapping[str, str],
    ) -> Mapping[str, str]:
        result = {
            "HOME": str(self._home),
            "PATH": self._host_environment.get("PATH") or os.defpath,
        }
        result.update(runtime_environment)
        result.update(session_environment)
        return MappingProxyType(result)

    @staticmethod
    def _failure_class(error: BaseException | None, returncode: int | None, stderr: str) -> str:
        if isinstance(error, subprocess.TimeoutExpired):
            return "launch_client_timeout"
        if error is not None:
            return "launch_client_unavailable"
        folded = stderr.casefold()
        if any(value in folded for value in ("permission denied", "access denied", "authentication failed")):
            return "dbus_access_denied"
        if any(
            value in folded
            for value in (
                "connection refused",
                "failed to connect",
                "cannot connect",
                "no such file",
                "dbus",
            )
        ):
            return "dbus_unavailable"
        return "launch_client_failed" if returncode else "probe_failed"

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
        umu_root, runtime_environment = self._runtime_context()
        launch_client = umu_root / variant / "pressure-vessel" / "bin" / "steam-runtime-launch-client"
        try:
            launch_client = launch_client.resolve(strict=True)
        except OSError as error:
            raise ContainerReentryError("container_reentry_unsupported") from error
        if not launch_client.is_file() or not os.access(launch_client, os.X_OK):
            raise ContainerReentryError("container_reentry_unsupported")

        digest = hashlib.md5(str(prefix).encode("utf-8"), usedforsecurity=False).hexdigest()
        captured_app_id = environment.get("STEAM_COMPAT_APP_ID")
        if captured_app_id is not None and captured_app_id.casefold() != digest:
            raise ContainerReentryError(
                "container_reentry_identity_mismatch",
                failure_class="app_id_mismatch",
                attempts=0,
            )
        app_id_source = "computed_and_captured" if captured_app_id is not None else "computed"
        bus_name = f"com.steampowered.App{digest}"
        expected = f"--bus-name={bus_name}"
        candidates = self._session_bus_candidates()
        if not candidates:
            raise ContainerReentryError(
                "container_reentry_probe_failed",
                failure_class="host_session_bus_unavailable",
                attempts=0,
            )
        saw_successful_listing = False
        successful_source: str | None = None
        last_exit_code: int | None = None
        last_source: str | None = None
        last_failure_class = "probe_failed"
        failure_priority = {
            "probe_failed": 0,
            "launch_client_failed": 1,
            "dbus_unavailable": 2,
            "launch_client_unavailable": 3,
            "launch_client_timeout": 4,
            "dbus_access_denied": 5,
        }
        invocation = 0
        while invocation < self._attempts:
            for candidate in candidates:
                if invocation >= self._attempts:
                    break
                invocation += 1
                probe_environment = self._probe_environment(candidate.environment)
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
                    failure_class = self._failure_class(error, None, "")
                    if failure_priority[failure_class] >= failure_priority[last_failure_class]:
                        last_exit_code = None
                        last_source = candidate.source
                        last_failure_class = failure_class
                    continue
                returncode = int(result.returncode)
                if returncode != 0:
                    failure_class = self._failure_class(None, returncode, str(result.stderr))
                    if failure_priority[failure_class] >= failure_priority[last_failure_class]:
                        last_exit_code = returncode
                        last_source = candidate.source
                        last_failure_class = failure_class
                    continue
                saw_successful_listing = True
                successful_source = candidate.source
                if expected in str(result.stdout).splitlines():
                    return ContainerReentryResolution(
                        launch_client,
                        bus_name,
                        variant,
                        invocation,
                        candidate.source,
                        app_id_source,
                        MappingProxyType(dict(candidate.environment)),
                        self._launch_environment(runtime_environment, candidate.environment),
                    )
            if invocation < self._attempts:
                self._sleep(self._delay_seconds)
        if saw_successful_listing:
            raise ContainerReentryError(
                "container_reentry_bus_missing",
                failure_class="bus_missing",
                exit_code=0,
                bus_source=successful_source,
                attempts=self._attempts,
            )
        raise ContainerReentryError(
            "container_reentry_probe_failed",
            failure_class=last_failure_class,
            exit_code=last_exit_code,
            bus_source=last_source,
            attempts=self._attempts,
        )

    async def verify(self, environment: Mapping[str, str]) -> ContainerReentryResolution:
        return await asyncio.to_thread(self._verify_sync, dict(environment))
