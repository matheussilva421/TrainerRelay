# Task 3 report: Python runtime discovery and lifecycle

## Result

Implemented the focused `trainer_relay/` backend package and thin Decky RPC
wiring in `main.py`. The backend now owns only Trainer Relay sidecars for
supported Epic/GOG identities, fails closed on ambiguous or invalid runtime
evidence, and persists configuration under the single `RelayConfigV1` key.

## TDD evidence

The implementation followed unittest RED/GREEN cycles. Representative runs:

| Cycle | Command | Observed result |
| --- | --- | --- |
| Initial package RED | `python -m unittest discover -s tests_backend -p "test_*.py"` | 2 import errors because `trainer_relay` did not exist. |
| Config/map RED | same focused discovery after package scaffold | 9 config/map tests exposed missing modules and portability assumptions; no runtime implementation was used to hide the failure. |
| Config/map GREEN | `python -m unittest tests_backend.test_config tests_backend.test_games_map` | 9/9 passed. |
| Runtime RED | `python -m unittest discover -s tests_backend -p "test_*.py"` | 14 discovered; 9 passed and 5 modules failed to import because process/environment/RPC/runner/watcher were absent. |
| Runtime GREEN | focused process/environment/runner, watcher/RPC, and main commands | 15/15, 10/10, and 2/2 passed respectively. |
| Hardening GREEN | focused recycled-session, ownership, missing-UMU, and new-session tests | 4/4 passed. |

The final full backend run discovered 40 tests and passed all 40.

## Implemented contracts

- `config.py`: exact `epic|gog` identity validation, v1 decoding/defaulting,
  strict trainer/prefix validation, default prefix derivation, and the
  `RelayConfigV1` storage key.
- `games_map.py`: fail-closed v1/v2/v3 parser, one-time `=` split, exact
  identity lookup, duplicate/unsupported/xcloud/relative/path-shape rejection,
  and sanitised diagnostics.
- `process.py`: numeric `/proc` enumeration, correct `/stat` field 22 parsing,
  before/after start-time stability checks, NUL cmdline/environment reads, Wine
  path normalisation, store/game/prefix/executable matching, and
  waiting/session/ambiguous outcomes.
- `environment.py` and `umu.py`: copied allowlisted environment with secret
  filtering and forced `PROTON_VERB=runinprefix`; unique bundled/PATH UMU
  resolution with zero/multiple-candidate diagnostics.
- `runner.py`: exact `[umu-run, trainer.exe]` spawn, trainer-parent cwd,
  `shell=False`, new session, DEVNULL/log streams, and SIGTERM/SIGKILL cleanup
  restricted to recorded owned process groups.
- `watcher.py`: one-second polling, three-second stability state, one automatic
  two-second retry, manual retry reset, session-change reset, ambiguity/end/
  disable/unload cleanup, and no game process lifecycle control.
- `rpc.py` and `main.py`: typed config/status/retry RPCs, strict request
  validation, sanitised status shape, SettingsManager persistence/notification,
  one watcher task, and cancellation/cleanup on unload.

## Files

Created:

- `trainer_relay/__init__.py`
- `trainer_relay/config.py`
- `trainer_relay/environment.py`
- `trainer_relay/games_map.py`
- `trainer_relay/process.py`
- `trainer_relay/rpc.py`
- `trainer_relay/runner.py`
- `trainer_relay/umu.py`
- `trainer_relay/watcher.py`
- `tests_backend/test_config.py`
- `tests_backend/test_environment.py`
- `tests_backend/test_games_map.py`
- `tests_backend/test_main.py`
- `tests_backend/test_process.py`
- `tests_backend/test_rpc.py`
- `tests_backend/test_runner.py`
- `tests_backend/test_watcher.py`

Modified:

- `main.py`
- `docs/notes/2026-08-29-trainer-relay-handoff.md`

## Validation

| Command | Result |
| --- | --- |
| `python -m unittest discover -s tests_backend -p "test_*.py"` | 40 tests, 40 passed, 0 failed. |
| `python -m compileall -q main.py trainer_relay tests_backend` | Passed with exit code 0. |
| `git diff --check` | Passed with exit code 0; only expected Git LF/CRLF normalization warnings appeared during diff inspection. |

The tests use controlled temporary proc trees, maps, clocks, process
factories, signals, SettingsManager fakes, and watcher fakes. No live game PID,
UMU process, or UI/TypeScript file was touched.

## Self-review against the brief

- [x] Config schema/version, exact identity regex, regular absolute `.exe`
  trainer validation, absolute existing prefix override, default prefix, and
  single persisted key.
- [x] games.map v1/v2/v3 parsing, embedded `=` preservation, all listed
  malformed/ambiguous rejection classes, fail-closed file diagnostics, and
  exact requested-identity lookup.
- [x] Numeric proc discovery, stable PID/start-time identity, robust stat
  parsing, NUL reads, Wine path matching, store/game/prefix checks, and
  zero/one/multiple result states.
- [x] Environment copy allowlist/redaction, forced `PROTON_VERB`, bundled/PATH
  UMU uniqueness, exact spawn options, no shell, and no environment logging.
- [x] Three-second running threshold, one automatic retry after two seconds,
  second-failure/manual-retry behavior, session-change reset, and owned-group
  termination only.
- [x] Disable/remove/game-end/ambiguity/unload cleanup without starting,
  stopping, or awaiting the game process.
- [x] Thin `_main`/`_unload` wiring and `get_relay_config`,
  `set_relay_game_config`, `get_relay_status`, and `retry_relay` RPC contracts.
- [x] Backend unittest coverage and compileall gate.

## Concerns and boundaries

- Steam Deck/real UniFiDeck process validation is intentionally still pending
  for the later release/device-validation task; this Task 3 validation is
  fixture-based.
- The worktree is ahead of `upstream/main`; this task creates the requested
  local commit but does not push or open a PR.
- Existing frontend/TypeScript behavior and inherited generic settings wrappers
  remain untouched for Task 4 compatibility.
