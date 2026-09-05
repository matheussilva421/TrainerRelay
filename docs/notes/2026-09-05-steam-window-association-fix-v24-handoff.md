# TrainerRelay experimental.24 — process-identity window association handoff

## Summary

Experimental.23 is superseded and must not be installed. Its window ownership check compared `_NET_WM_PID` with the outer `umu-run` process group. Official Steam Runtime source shows that `steam-runtime-launcher-service` creates the actual command in a new session/process group, invalidating that premise.

Experimental.24 replaces that check with stable process identity: exact trainer executable, exact Wine prefix anchor, PID and `/proc/<pid>/stat` start time. It revalidates immediately before and after writing `STEAM_GAME` and refuses all writes if distinct matching process identities are present.

## Files changed

- `trainer_relay/process.py`: added exact sidecar PID verification with stable start-time, command-line executable resolution and prefix matching.
- `trainer_relay/window_probe.py`: removed PGID ownership; added exact process verification, two-pass ambiguity detection and absolute-path validation.
- `trainer_relay/watcher.py`: passes trainer path/prefix to the associator and recognizes bounded invalid/ambiguous statuses.
- `tests_backend/test_process.py`, `tests_backend/test_window_probe.py`, `tests_backend/test_watcher.py`: regression, TOCTOU, ambiguity and integration coverage.
- `main.py`, `package.json`, `tests_packaging/test_package_layout.py`: version advanced to `0.1.0-experimental.24`.
- `README.md`, `docs/STEAM-DECK-VALIDATION.md`: candidate/checklist updated.
- `docs/notes/2026-09-05-steam-runtime-launcher-process-identity-research.md`: primary-source cause analysis.
- `docs/notes/2026-09-05-decky-local-plugin-install-reload-research.md`: official local ZIP/reload/rollback procedure produced by the research agent.
- `docs/notes/2026-09-05-steam-window-association-fix-handoff.md`: marked superseded.

## TDD evidence

- RED: service-launched trainer topology returned `not_implemented`; GREEN: exact PID identity associated only PID 31304, not game PID 31186.
- RED: default verifier returned `no_owned_windows`; GREEN: real `/proc` fixture associated after exact path/prefix/start-time verification.
- RED: watcher passed `(environment, PGID, SteamGameId)`; GREEN: it passes `(environment, trainer path, prefix anchor, SteamGameId)`.
- RED: two matching process identities produced writes; GREEN: `ambiguous_owned_windows`, zero writes.
- RED: relative trainer/prefix paths reached enumeration; GREEN: bounded invalid status before X11 access.
- RED: package still embedded `.23`; GREEN: package metadata and backend version embed `.24`.

## Validation status

- Backend full suite: 289/289 passed, 0 failed.
- Packaging full suite: 7/7 passed, 0 failed.
- Frontend: 30 files and 217/217 tests passed, 0 failed.
- TypeScript app and test configs: both exited 0.
- Biome: 75 files checked, no fixes or errors.
- Rollup build and Python `compileall`: exited 0.
- `git diff --check`: no whitespace errors; only Windows LF-to-CRLF notices.
- Physical Steam Deck validation: pending. No device/plugin/game state was changed during this correction.

## Artifact

- `artifacts/TrainerRelay-v0.1.0-experimental.24.zip`
- Size: 773,485 bytes.
- SHA-256: `CFDAB3D2BDCC1959817DE05121C62A1BAF94669BEB1E2578337A0F7A5D3538FB`.
- Entries: 34.
- Embedded `package.json` and `main.py`: `0.1.0-experimental.24`.
- Root `TrainerRelay.zip` was not overwritten.

## Git and artifact status

- Branch: `feat/trainer-relay`.
- Last pushed commit before this correction: `b8a8dd5`.
- Commit/push for experimental.24: pending at this checkpoint.
- `.codex-remote-attachments/` remains untracked and must not be read, modified or staged.
- Existing experimental.23 artifact is superseded. Do not install it.

## Resume

1. Run all backend, frontend, packaging, typecheck, lint and build gates.
2. Run `git diff --check` and an independent review of the exact diff.
3. Build a versioned experimental.24 ZIP without overwriting the root known artifact; record SHA-256, size, entry count and embedded versions.
4. Update this handoff with final evidence, commit the exact intended files, and push.
5. At the explicit device checkpoint, preserve a known-good ZIP/hash, install experimental.24, collect plugin recognition/backend/frontend evidence, start a fresh game session, wait through association retries, then verify both windows in Steam and actual switching. Stop on `no_owned_windows`, `ambiguous_owned_windows`, partial/failure/deadline or any rollback problem.
