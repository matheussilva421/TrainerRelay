"""Owned trainer process-group spawning and shutdown."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from .process import SessionIdentity


_SIGTERM = getattr(signal, "SIGTERM", 15)
_SIGKILL = getattr(signal, "SIGKILL", 9)


@dataclass
class RunnerHandle:
    session: SessionIdentity
    process: object
    process_group_id: int
    environment: Mapping[str, str]


def _signal_process_group(group_id: int, signum: int) -> None:
    kill_group = getattr(os, "killpg", None)
    if kill_group is not None:
        kill_group(group_id, signum)
    else:
        os.kill(group_id, signum)


class OwnedTrainerRunner:
    def __init__(
        self,
        umu_run: str | os.PathLike[str] | Callable[[], str | os.PathLike[str]],
        *,
        popen_factory: Callable[..., object] = subprocess.Popen,
        log_path: str | os.PathLike[str] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        signal_group: Callable[[int, int], None] = _signal_process_group,
    ) -> None:
        self.umu_run = umu_run
        self._popen = popen_factory
        self._log_path = Path(log_path) if log_path is not None else None
        self._monotonic = monotonic
        self._sleep = sleep
        self._signal_group = signal_group
        self._owned: list[RunnerHandle] = []

    @property
    def owned(self) -> tuple[RunnerHandle, ...]:
        return tuple(self._owned)

    def spawn(self, session: SessionIdentity, trainer_executable: str, environment: Mapping[str, str]) -> RunnerHandle:
        stream = subprocess.DEVNULL
        file_handle = None
        spawn_environment = dict(environment)
        umu_run = self.umu_run() if callable(self.umu_run) else self.umu_run
        if self._log_path is not None:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handle = self._log_path.open("ab")
            stream = file_handle
        try:
            process = self._popen(
                [str(umu_run), trainer_executable],
                cwd=str(Path(trainer_executable).parent),
                env=spawn_environment,
                shell=False,
                start_new_session=True,
                stdout=stream,
                stderr=stream,
            )
        except Exception:
            if file_handle is not None:
                file_handle.close()
            raise
        if file_handle is not None:
            file_handle.close()
        handle = RunnerHandle(session, process, int(process.pid), spawn_environment)
        self._owned.append(handle)
        return handle

    def poll(self, handle: RunnerHandle) -> int | None:
        return handle.process.poll()  # type: ignore[attr-defined]

    def forget(self, handle: RunnerHandle) -> None:
        if handle in self._owned:
            self._owned.remove(handle)

    def stop(self, handle: RunnerHandle) -> None:
        if not any(candidate is handle for candidate in self._owned):
            raise ValueError("unowned_process")
        self._signal_group(handle.process_group_id, _SIGTERM)
        deadline = self._monotonic() + 5.0
        while self.poll(handle) is None and self._monotonic() < deadline:
            self._sleep(0.1)
        if self.poll(handle) is None:
            self._signal_group(handle.process_group_id, _SIGKILL)
        self._owned.remove(handle)
