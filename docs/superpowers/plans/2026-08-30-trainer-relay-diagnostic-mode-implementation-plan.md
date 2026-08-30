# Trainer Relay Persistent Diagnostic Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent, privacy-bounded 50 MiB diagnostic journal, live DevTools forwarding, and one-click TXT export that explains every Trainer Relay launch decision on a physical Steam Deck.

**Architecture:** A focused Python `DiagnosticRecorder` owns settings-independent event validation, rotation, cursors, export, and clear operations. Process discovery emits structured decisions into the watcher, while a typed Decky RPC boundary exposes only sanitized events. A persistent TypeScript bridge forwards new events to CEF DevTools, and a separate routed Diagnostics page manages the persistent toggle, latest events, export, and clear operations.

**Tech Stack:** Python 3.12 standard library and `unittest`; TypeScript 5, React 18, Decky API/UI, Vitest, Biome, Rollup, pnpm.

**Spec:** `docs/superpowers/specs/2026-08-30-trainer-relay-diagnostic-mode-design.md`

## Global Constraints

- Diagnostic mode remains enabled across plugin, Steam, and Deck restarts until explicitly disabled.
- Internal journal storage is exactly five files of at most 10 MiB each and never exceeds 50 MiB total.
- Journal files live only below `DECKY_PLUGIN_SETTINGS_DIR/diagnostics`; TXT exports go only to `/home/deck/Downloads`.
- Full environments, full command lines, trainer stdout/stderr, credentials, tokens, cookies, authorization data, and `PROTON_REMOTE_DEBUG_CMD` content are prohibited.
- Allowed technical values are expected/observed executable, trainer, prefix, `umu-run`, `GAMEID`, `STORE`, `WINEPREFIX`, and `PROTONPATH`.
- Diagnostics are observational: they never make an ineligible process eligible and never alter game or trainer lifecycle decisions.
- Every recorder/storage failure leaves the game and watcher running.
- Frontend diagnostics use cursor polling; no HTTP server, remote upload, shell command, or telemetry is introduced.
- Deliver as `v0.1.0-experimental.13`; do not promote stable before physical GOG and Epic acceptance.
- Follow strict TDD: observe each focused test fail for the expected missing behavior before modifying production code.

## File structure

### Backend

- Create `trainer_relay/diagnostic_settings.py`: decode/persistable value model for `diagnostic_settings_v1`.
- Create `trainer_relay/diagnostics.py`: event schemas, redaction, recorder, rotation, cursors, export, clear, and statistics.
- Modify `trainer_relay/process.py`: structured process decisions and relevant-candidate summaries.
- Modify `trainer_relay/watcher.py`: record config/map/process/state/trainer lifecycle events without changing decisions.
- Modify `trainer_relay/runner.py`: optional event callback for owned spawn/stop boundaries.
- Modify `trainer_relay/umu.py`: optional resolution-event callback or structured resolution result used by the watcher.
- Modify `trainer_relay/rpc.py`: diagnostic settings/events/export/clear adapter.
- Modify `main.py`: construct one recorder, wire it to watcher/RPC, expose Decky methods, flush on unload.

### Frontend

- Create `src/domain/diagnostics/types.ts`: public TypeScript contracts and conservative decoders.
- Create `src/infra/diagnosticRpc.ts`: typed callable wrappers.
- Create `src/hooks/diagnosticPolling.ts`: cursor loop and bounded backoff.
- Create `src/hooks/useDiagnosticsController.tsx`: page orchestration.
- Create `src/diagnostics/consoleBridge.ts`: persistent SharedJSContext event forwarding.
- Create `src/views/DiagnosticsPage.tsx`: separate Decky page.
- Modify `src/views/PageRouter.tsx`: add Diagnostics page.
- Modify `src/index.tsx`: start and stop the console bridge.

### Tests and documentation

- Create `tests_backend/test_diagnostic_settings.py`.
- Create `tests_backend/test_diagnostics.py`.
- Extend `tests_backend/test_process.py`, `test_watcher.py`, `test_runner.py`, `test_rpc.py`, and `test_main.py`.
- Create `tests/diagnostic-rpc.test.ts`, `diagnostic-polling.test.ts`, `diagnostic-console-bridge.test.ts`, and `diagnostics-page.test.ts`.
- Extend `tests/page-router.test.ts` and `tests_packaging/test_package_layout.py`; packaging must assert `TrainerRelay/py_modules/trainer_relay/diagnostics.py` and `diagnostic_settings.py` exist.
- Update README, Steam Deck guide, validation checklist, package version, and handoff.

---

### Task 1: Persistent diagnostic settings

**Files:**
- Create: `trainer_relay/diagnostic_settings.py`
- Create: `tests_backend/test_diagnostic_settings.py`

**Interfaces:**
- Produces: `DIAGNOSTIC_SETTINGS_KEY = "diagnostic_settings_v1"`.
- Produces: `empty_diagnostic_settings() -> dict[str, Any]` returning `{"schemaVersion": 1, "enabled": False}`.
- Produces: `decode_diagnostic_settings(value: Any) -> dict[str, Any]`, accepting mappings or JSON strings and failing closed.
- Produces: `validate_diagnostic_settings(value: Any) -> dict[str, Any]`, raising `ValueError("invalid_diagnostic_settings")` for malformed writes.

- [x] **Step 1: Write failing settings tests**

```python
class DiagnosticSettingsTests(unittest.TestCase):
    def test_defaults_disabled_and_decodes_only_exact_schema(self):
        self.assertEqual(empty_diagnostic_settings(), {"schemaVersion": 1, "enabled": False})
        self.assertEqual(decode_diagnostic_settings({"schemaVersion": 1, "enabled": True})["enabled"], True)
        for value in (None, {}, {"schemaVersion": 2, "enabled": True}, {"schemaVersion": 1, "enabled": "yes"}):
            with self.subTest(value=value):
                self.assertEqual(decode_diagnostic_settings(value), {"schemaVersion": 1, "enabled": False})

    def test_strict_validation_rejects_malformed_rpc_writes(self):
        with self.assertRaisesRegex(ValueError, "invalid_diagnostic_settings"):
            validate_diagnostic_settings({"schemaVersion": 1, "enabled": 1})
```

- [x] **Step 2: Run the focused test and verify RED**

Run: `python -m unittest tests_backend.test_diagnostic_settings -v`

Expected: import failure for missing `trainer_relay.diagnostic_settings`.

- [x] **Step 3: Implement the minimal decoder/validator**

Use exact-type checks (`type(enabled) is bool`), schema version 1, JSON-string parsing consistent with `trainer_relay/config.py`, and no settings I/O in this module.

- [x] **Step 4: Run focused and backend suites GREEN**

Run:

```bash
python -m unittest tests_backend.test_diagnostic_settings -v
python -m unittest discover -s tests_backend -p "test_*.py"
```

Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add -- trainer_relay/diagnostic_settings.py tests_backend/test_diagnostic_settings.py
git commit -m "feat: add persistent diagnostic settings"
```

### Task 2: Sanitized event model and bounded journal rotation

**Files:**
- Create: `trainer_relay/diagnostics.py`
- Create: `tests_backend/test_diagnostics.py`

**Interfaces:**
- Produces immutable `DiagnosticSession(pid: int, start_time: int)`.
- Produces `DiagnosticEvent` with `to_wire() -> dict[str, Any]`.
- Produces `DiagnosticRecorder(root: Path, *, enabled: bool, max_file_bytes: int = 10 * 1024 * 1024, max_files: int = 5, clock=..., wall_clock=...)`.
- Produces `record(category, event, outcome, *, identity=None, session=None, details=None) -> None`.
- Produces `set_enabled(enabled: bool) -> None`, `flush() -> None`, `stats() -> dict[str, Any]`.
- Event detail allowlists are a module constant keyed by event name; unknown event names or details keys raise `DiagnosticValidationError("diagnostic_event_rejected")` before disk write.

The initial allowlist is exact:

```python
EVENT_DETAIL_KEYS = {
    "diagnostic_mode_changed": {"enabled"},
    "plugin_loaded": {"version"},
    "plugin_unloaded": {"version"},
    "config_loaded": {"game_count"},
    "config_persisted": {"game_count", "enabled", "trainer_path", "prefix_override"},
    "games_map_loaded": {"entry_count", "map_path", "expected_executable"},
    "games_map_rejected": {"reason", "map_path"},
    "prefix_selected": {"source", "expected_prefix"},
    "process_scan_summary": {
        "process_count", "readable_count", "relevant_count", "accepted_count",
        "proc_entry_unreadable_count", "pid_reused_during_scan_count",
        "missing_required_environment_count", "game_id_mismatch_count",
        "store_mismatch_count", "prefix_mismatch_count", "executable_mismatch_count",
        "legacy_settings_present_count",
    },
    "candidate_rejected": {
        "reason", "expected_executable", "observed_executable", "expected_prefix",
        "observed_prefix", "game_id", "store", "wineprefix", "protonpath",
    },
    "candidate_accepted": {
        "expected_executable", "observed_executable", "expected_prefix",
        "observed_prefix", "game_id", "store", "wineprefix", "protonpath",
    },
    "umu_resolved": {"source", "umu_path"},
    "umu_rejected": {"reason"},
    "trainer_spawned": {"trainer_path", "process_group_id"},
    "trainer_spawn_failed": {"trainer_path", "reason"},
    "trainer_running": {"trainer_path", "elapsed_ms"},
    "trainer_exited": {"trainer_path", "exit_code", "elapsed_ms"},
    "trainer_retry_scheduled": {"retry_count", "delay_ms"},
    "trainer_manual_retry": {"retry_count"},
    "session_changed": {"previous_pid", "previous_start_time"},
    "session_ended": {},
    "owned_group_signal": {"process_group_id", "signal", "forced"},
    "event_repeated": {"repeated_event", "count", "elapsed_ms"},
}
```

- [x] **Step 1: Write failing event privacy and rotation tests**

```python
def test_rejects_forbidden_and_unknown_details_without_writing(self):
    recorder = DiagnosticRecorder(root, enabled=True, max_file_bytes=512)
    with self.assertRaisesRegex(DiagnosticValidationError, "diagnostic_event_rejected"):
        recorder.record("process", "candidate_rejected", "rejected", details={"token": "secret"})
    self.assertEqual(recorder.stats()["eventCount"], 0)

def test_rotates_exactly_five_files_under_the_hard_limit(self):
    recorder = DiagnosticRecorder(root, enabled=True, max_file_bytes=300, max_files=5)
    for sequence in range(100):
        recorder.record("lifecycle", "plugin_loaded", "info", details={"version": f"test-{sequence}"})
    files = sorted(root.glob("diagnostics.*.ndjson"))
    self.assertLessEqual(len(files), 5)
    self.assertTrue(all(path.stat().st_size <= 300 for path in files))
    self.assertLessEqual(sum(path.stat().st_size for path in files), 1500)
```

Include tests for allowed full technical paths, prohibited normalized key names, type/length bounds, ISO timestamp, monotonic sequence, malformed startup lines, a partial rotation state with missing middle files, and disabled no-write behavior.

- [x] **Step 2: Run focused test and verify RED**

Run: `python -m unittest tests_backend.test_diagnostics -v`

Expected: import failure for missing diagnostics module.

- [x] **Step 3: Implement the minimal recorder**

Implement JSON serialization with deterministic separators and sorted keys. Rotation must execute `.4` delete, `.3 -> .4`, `.2 -> .3`, `.1 -> .2`, `.0 -> .1`, then create `.0`. Reject a single serialized event larger than `max_file_bytes` with a bounded storage diagnostic; never truncate JSON.

- [x] **Step 4: Add repeat-consolidation tests RED, then implement GREEN**

Test first that identical consecutive fingerprints write one initial event and one `event_repeated` summary on fingerprint change, 30-second flush, disable, and unload flush. Ensure state changes and differing rejection reasons never consolidate together.

- [x] **Step 5: Run focused and backend suites GREEN**

Run:

```bash
python -m unittest tests_backend.test_diagnostics -v
python -m unittest discover -s tests_backend -p "test_*.py"
```

- [x] **Step 6: Commit**

```bash
git add -- trainer_relay/diagnostics.py tests_backend/test_diagnostics.py
git commit -m "feat: add bounded diagnostic journal"
```

### Task 3: Cursors, export, clear, and storage-failure isolation

**Files:**
- Modify: `trainer_relay/diagnostics.py`
- Modify: `tests_backend/test_diagnostics.py`

**Interfaces:**
- Produces `events_after(cursor: str | None, limit: int) -> dict[str, Any]` with `generation`, `nextCursor`, `cursorReset`, and `events`.
- Produces `export_text(downloads_dir: Path, plugin_version: str) -> dict[str, Any]` with absolute `path` and `bytesWritten`.
- Produces `clear() -> dict[str, Any]`, advancing generation only after journal paths are removed successfully.
- Produces `storage_diagnostic: str | None` and `last_export_path: str | None` through `stats()`.

- [x] **Step 1: Write cursor and clear tests RED**

```python
def test_cursor_paginates_and_clear_resets_generation(self):
    for count in range(3):
        recorder.record("lifecycle", "test_event", "info", details={"count": count})
    first = recorder.events_after(None, 2)
    second = recorder.events_after(first["nextCursor"], 2)
    self.assertEqual([event["details"]["count"] for event in first["events"] + second["events"]], [0, 1, 2])
    recorder.clear()
    stale = recorder.events_after(second["nextCursor"], 20)
    self.assertTrue(stale["cursorReset"])
    self.assertGreater(stale["generation"], first["generation"])
```

Also test limit clamping 1..200 and restart recovery of generation/sequence metadata.

- [x] **Step 2: Run focused test RED, implement cursor metadata, run GREEN**

Run: `python -m unittest tests_backend.test_diagnostics -v`

- [x] **Step 3: Write export tests RED**

Test oldest-to-newest order, deterministic line format, UTF-8, timestamped collision suffix, header privacy notice, atomic temporary rename, and that a forced write/rename failure preserves journal and prior export.

- [x] **Step 4: Implement streaming TXT export GREEN**

Use `tempfile.NamedTemporaryFile` in the downloads directory, close/fsync, then `os.replace`. Do not shell out. Flush repeat summaries before reading journal files. Return only safe codes such as `diagnostic_export_failed` from callers.

- [x] **Step 5: Write storage-failure isolation and clear-scope tests RED, then implement GREEN**

Inject filesystem operations so tests prove append/rotation failure sets `diagnostic_storage_unavailable`, future ordinary record calls do not retry or raise, and explicit `set_enabled`, `clear`, `export_text`, or restart retries storage. Clear must target only `diagnostics.[0-4].ndjson` and recorder metadata under its exact root.

- [x] **Step 6: Run backend suite and commit**

```bash
python -m unittest tests_backend.test_diagnostics -v
python -m unittest discover -s tests_backend -p "test_*.py"
git add -- trainer_relay/diagnostics.py tests_backend/test_diagnostics.py
git commit -m "feat: export and page diagnostic history"
```

### Task 4: Structured `/proc` decisions and relevant-candidate summaries

**Files:**
- Modify: `trainer_relay/process.py`
- Modify: `tests_backend/test_process.py`

**Interfaces:**
- Produces `CandidateDecision(pid, start_time, relevant, accepted, reason, details, session, environment)` with details limited to process diagnostic fields.
- Extends `DiscoveryResult` with `decisions: tuple[CandidateDecision, ...]` and `rejection_counts: Mapping[str, int]` without changing existing `state`, `session`, `environment`, or `candidates` behavior.
- Relevant anchor is true when expected executable basename, expected `GAMEID`, expected store plus expected prefix, or literal identity token matches.
- Strongest safe no-candidate diagnostic precedence: `legacy_settings_present`, `pid_reused_during_scan`, `missing_required_environment`, `game_id_mismatch`, `store_mismatch`, `prefix_mismatch`, `executable_mismatch`, then `None` for no relevant process.

- [x] **Step 1: Extend fake `/proc` test helpers and write reason tests RED**

Add one focused test per reason. Example:

```python
def test_reports_prefix_mismatch_for_relevant_game_process(self):
    write_candidate(root, 123, start_time=10, executable=expected, prefix="/wrong", game_id="game", store="gog")
    result = ProcessDiscoverer(root).discover("gog:game", expected, expected_prefix)
    self.assertEqual(result.state, "waiting_for_game")
    self.assertEqual(result.diagnostic, "prefix_mismatch")
    self.assertEqual(result.decisions[0].reason, "prefix_mismatch")
    self.assertNotIn("command_line", result.decisions[0].details)
```

Test irrelevant processes are aggregated without path/details, relevant acceptance still requires exact existing rules, PID reuse is reported, ambiguity remains fail-closed, and no full environment appears in decision serialization.

- [x] **Step 2: Run process tests and verify RED**

Run: `python -m unittest tests_backend.test_process -v`

Expected: missing `decisions`/reason diagnostics.

- [x] **Step 3: Refactor `_candidate` into evaluation without changing eligibility**

Create `_evaluate_candidate(...) -> CandidateDecision`; keep environment only on accepted internal decisions. Build sanitized details from explicit allowed fields. `discover()` derives the same accepted candidates plus rejection counts and strongest reason.

- [x] **Step 4: Run focused, watcher, and full backend tests GREEN**

```bash
python -m unittest tests_backend.test_process tests_backend.test_watcher -v
python -m unittest discover -s tests_backend -p "test_*.py"
```

- [x] **Step 5: Commit**

```bash
git add -- trainer_relay/process.py tests_backend/test_process.py tests_backend/test_watcher.py
git commit -m "feat: explain process candidate rejection"
```

### Task 5: Watcher, UMU, trainer, retry, and shutdown events

**Files:**
- Modify: `trainer_relay/watcher.py`
- Modify: `trainer_relay/runner.py`
- Modify: `trainer_relay/umu.py`
- Modify: `tests_backend/test_watcher.py`
- Modify: `tests_backend/test_runner.py`
- Modify: `tests_backend/test_environment.py`
- Create: `tests_backend/test_diagnostic_integration.py`

**Interfaces:**
- `RelayWatcher(..., diagnostics: DiagnosticRecorder | NullDiagnosticRecorder | None = None)`.
- `NullDiagnosticRecorder.record(...)` and `flush()` are no-ops, preserving existing callers.
- Produces `StopResult(forced: bool)` from `OwnedTrainerRunner.stop(handle)` so the watcher can record whether SIGKILL escalation occurred; existing callers may ignore the return value.
- Produces `UmuResolution(path: Path, source: Literal["bundled", "path"])` from `resolve_umu_run_details(...)`; existing `resolve_umu_run(...)` delegates and returns only `.path` for compatibility.
- Watcher records only allowlisted event names and passes `DiagnosticSession(pid, start_time)`.

- [ ] **Step 1: Write watcher event tests RED**

Use a fake recorder collecting calls. Assert exact event order for:

```text
games_map_loaded -> process_scan_summary -> candidate_accepted -> umu_resolved -> trainer_spawned -> trainer_running
```

Add focused tests for malformed map, each structured process rejection, `umu_not_found`, `umu_ambiguous`, spawn failure, early exit, one automatic retry, manual retry, session replacement, game end, SIGTERM, and SIGKILL escalation.

Create the end-to-end privacy test before event wiring. Seed a fake relevant
candidate with an allowed prefix mismatch plus forbidden marker values. Drive
one watcher poll, one recorder cursor read, and one TXT export. Assert the event
and TXT contain `prefix_mismatch`, identity, PID/start time, and
expected/observed prefix, but not forbidden keys/values, unrelated process
paths, or the full argv.

- [ ] **Step 2: Run focused tests RED**

Run: `python -m unittest tests_backend.test_watcher tests_backend.test_runner tests_backend.test_environment tests_backend.test_diagnostic_integration -v`

- [ ] **Step 3: Implement minimal event hooks**

Centralize watcher recording in `_record(...)` that catches `DiagnosticValidationError`, `OSError`, and `ValueError`. Do not wrap or change discovery/runner control flow. Never pass `discovery.environment` to the recorder; construct details from named allowed fields only.

- [ ] **Step 4: Run focused and full backend suites GREEN**

```bash
python -m unittest tests_backend.test_watcher tests_backend.test_runner tests_backend.test_environment tests_backend.test_diagnostic_integration -v
python -m unittest discover -s tests_backend -p "test_*.py"
```

- [ ] **Step 5: Commit**

```bash
git add -- trainer_relay/watcher.py trainer_relay/runner.py trainer_relay/umu.py tests_backend/test_watcher.py tests_backend/test_runner.py tests_backend/test_environment.py tests_backend/test_diagnostic_integration.py
git commit -m "feat: record relay lifecycle diagnostics"
```

### Task 6: Backend diagnostic RPCs and Decky lifecycle wiring

**Files:**
- Modify: `trainer_relay/rpc.py`
- Modify: `main.py`
- Modify: `tests_backend/test_rpc.py`
- Modify: `tests_backend/test_main.py`

**Interfaces:**
- `RelayRpc(settings, watcher, diagnostics, *, downloads_dir, plugin_version)`.
- Methods: `get_diagnostic_settings()`, `set_diagnostics_enabled(data)`, `get_diagnostic_events(data)`, `export_diagnostics()`, `clear_diagnostics()`.
- Main owns `_diagnostics`, initializes it from `diagnostic_settings_v1`, and passes the same instance to watcher and RPC.
- Main unload flushes diagnostics after watcher shutdown and does not delete history.

- [ ] **Step 1: Write RPC contract tests RED**

Test settings response exact fields, strict boolean input, cursor/limit decoding, bounded RPC error codes, export path/bytes, clear generation, settings commit before enabling recorder, and no raw exception text.

```python
response = await rpc.set_diagnostics_enabled({"enabled": True})
self.assertTrue(response["settings"]["enabled"])
self.assertEqual(settings.set_calls[-1][0], "diagnostic_settings_v1")
self.assertTrue(diagnostics.enabled)
```

- [ ] **Step 2: Run RPC tests RED, implement adapter, run GREEN**

Run: `python -m unittest tests_backend.test_rpc -v`

- [ ] **Step 3: Write main wiring tests RED**

Patch `DiagnosticRecorder` and assert one recorder under `/settings/diagnostics`, persisted enabled state, same instance passed to watcher/RPC, all five Plugin classmethods delegated, and unload flushes once even after watcher failure.

- [ ] **Step 4: Implement main wiring and Plugin RPC methods GREEN**

Use `decky.DECKY_PLUGIN_SETTINGS_DIR` and `Path(decky.HOME or HOME) / "Downloads"`. Read package version from a fixed Python constant or injected main value that packaging tests can verify; do not parse package.json at runtime on every export.

- [ ] **Step 5: Run backend and compile gates, commit**

```bash
python -m unittest tests_backend.test_rpc tests_backend.test_main -v
python -m unittest discover -s tests_backend -p "test_*.py"
python -m compileall -q main.py trainer_relay tests_backend
git add -- main.py trainer_relay/rpc.py tests_backend/test_rpc.py tests_backend/test_main.py
git commit -m "feat: expose diagnostic backend RPCs"
```

### Task 7: TypeScript diagnostic contracts and RPC decoding

**Files:**
- Create: `src/domain/diagnostics/types.ts`
- Create: `src/infra/diagnosticRpc.ts`
- Create: `tests/diagnostic-rpc.test.ts`

**Interfaces:**
- Produces exact spec interfaces `DiagnosticSettingsV1`, `DiagnosticEvent`, `DiagnosticSettingsResponse`, `DiagnosticEventsRequest`, and `DiagnosticEventsResponse`.
- Produces conservative `decodeDiagnosticSettingsResponse`, `decodeDiagnosticEventsResponse`, and `decodeDiagnosticExportResponse`.
- Produces `diagnosticRpc` with five methods matching backend RPC names.

- [ ] **Step 1: Write decoder and client tests RED**

Test valid response, unknown category/outcome, malformed sequence/session/details, unsafe details keys, limit/cursor serialization, and safe failure behavior. A malformed event must reject the response rather than partially trust it.

- [ ] **Step 2: Run focused test RED**

Run: `.\node_modules\.bin\vitest.cmd run tests/diagnostic-rpc.test.ts --reporter verbose`

- [ ] **Step 3: Implement exact decoders and callable wrappers GREEN**

Reuse no backend implementation details. Clamp request limits before the callable boundary and return immutable copied values.

- [ ] **Step 4: Run focused TypeScript gates and commit**

```bash
.\node_modules\.bin\vitest.cmd run tests/diagnostic-rpc.test.ts --reporter verbose
.\node_modules\.bin\tsc.cmd --noEmit
.\node_modules\.bin\tsc.cmd --noEmit -p tsconfig.test.json
git add -- src/domain/diagnostics/types.ts src/infra/diagnosticRpc.ts tests/diagnostic-rpc.test.ts
git commit -m "feat: add typed diagnostic RPC client"
```

### Task 8: Cursor polling and persistent DevTools console bridge

**Files:**
- Create: `src/hooks/diagnosticPolling.ts`
- Create: `src/diagnostics/consoleBridge.ts`
- Modify: `src/index.tsx`
- Create: `tests/diagnostic-polling.test.ts`
- Create: `tests/diagnostic-console-bridge.test.ts`

**Interfaces:**
- `startDiagnosticPolling({loadSettings, loadEvents, onEvents, onSettings, onError, timers}) -> () => void`.
- Check settings every 1,000 ms. While enabled, read events in the same cycle; while disabled, read no event pages. Use 2s, 4s, 8s, then 10s capped backoff per failure episode.
- `startDiagnosticConsoleBridge(rpc, timers) -> () => void` emits `console.info("[TrainerRelay:diagnostic]", event)` and one bounded warning per failure episode.
- `index.tsx` starts one bridge in `definePlugin` and stops it in `onDismount`.

- [ ] **Step 1: Write timer/backoff tests RED**

Use fake timers to prove immediate settings check, enabled polling, cursor advancement, `cursorReset`, no duplicate events, capped backoff, recovery to one second, disabled pause, and cleanup cancelling every timer/late promise.

- [ ] **Step 2: Run polling test RED, implement polling GREEN**

Run: `.\node_modules\.bin\vitest.cmd run tests/diagnostic-polling.test.ts --reporter verbose`

- [ ] **Step 3: Write console bridge and plugin lifecycle tests RED**

Assert exact prefix, sanitized object passthrough, one warning per failure episode, and `onDismount` cleanup. Do not log configuration responses or export paths through this bridge.

- [ ] **Step 4: Implement console bridge and index wiring GREEN**

Bind browser timers with `bindBrowserTimers(window)` so CEF does not throw `Illegal invocation`.

- [ ] **Step 5: Run frontend tests/typechecks and commit**

```bash
.\node_modules\.bin\vitest.cmd run tests/diagnostic-polling.test.ts tests/diagnostic-console-bridge.test.ts --reporter verbose
.\node_modules\.bin\tsc.cmd --noEmit
.\node_modules\.bin\tsc.cmd --noEmit -p tsconfig.test.json
git add -- src/hooks/diagnosticPolling.ts src/diagnostics/consoleBridge.ts src/index.tsx tests/diagnostic-polling.test.ts tests/diagnostic-console-bridge.test.ts
git commit -m "feat: stream diagnostics to DevTools"
```

### Task 9: Separate Diagnostics page

**Files:**
- Create: `src/hooks/useDiagnosticsController.tsx`
- Create: `src/views/DiagnosticsPage.tsx`
- Modify: `src/views/PageRouter.tsx`
- Create: `tests/diagnostics-page.test.ts`
- Modify: `tests/page-router.test.ts`

**Interfaces:**
- Controller returns settings/load/error state, latest 20 events, bytes used/limit, storage diagnostic, last export path, busy action, and `toggle`, `exportText`, `requestClear`, `clearConfirmed` actions.
- Page uses Decky `Field`, `ToggleField`, `DialogButton`, `ConfirmModal`, and `showModal` with direct focusable controls.
- Router has exactly two pages: `Trainer Relay` and `Diagnostics`.

- [ ] **Step 1: Extend router test RED**

Assert second page title `Diagnostics`, diagnostics icon, and `DiagnosticsPage` content receives no trainer identity or private config props.

- [ ] **Step 2: Write page/controller tests RED**

Test active indicator, `bytesUsed / 52428800`, last 20 events oldest-to-newest, empty state, storage error, toggle persistence, export success path, export failure notice, clear confirmation, clear refresh/cursor reset, disabled history retention, global availability when the current shortcut is unsupported, and controls disabled during RPC failure.

- [ ] **Step 3: Implement controller and page GREEN**

Use independent cursor polling; never couple page open/close to backend recording. Format detail values deterministically and truncate only visual display, not backend export. Do not render raw HTML.

- [ ] **Step 4: Run frontend suite, lint, typecheck, and build**

```bash
.\node_modules\.bin\biome.cmd check src tests vitest.config.ts
.\node_modules\.bin\tsc.cmd --noEmit
.\node_modules\.bin\tsc.cmd --noEmit -p tsconfig.test.json
.\node_modules\.bin\vitest.cmd run
.\node_modules\.bin\rollup.cmd -c
```

- [ ] **Step 5: Commit**

```bash
git add -- src/hooks/useDiagnosticsController.tsx src/views/DiagnosticsPage.tsx src/views/PageRouter.tsx tests/diagnostics-page.test.ts tests/page-router.test.ts
git commit -m "feat: add in-plugin diagnostics page"
```

### Task 10: Final privacy gate, packaging, documentation, and experimental.13

**Files:**
- Verify: `tests_backend/test_diagnostic_integration.py`
- Modify: `tests_packaging/test_package_layout.py`
- Modify: `package.json`
- Modify: `README.md`
- Modify: `docs/GUIA-INSTALACAO-TESTES-E-LOGS.md`
- Modify: `docs/STEAM-DECK-VALIDATION.md`
- Modify: `docs/notes/2026-08-29-trainer-relay-handoff.md`

**Interfaces:**
- End-to-end fake `/proc` integration creates a relevant rejected process, watcher poll, RPC cursor read, and TXT export.
- Export must contain the expected safe reason and allowed anchors, and must not contain seeded forbidden secret values or raw full command line.
- Version becomes exactly `0.1.0-experimental.13`.

- [ ] **Step 1: Re-run the end-to-end privacy gate**

Run: `python -m unittest tests_backend.test_diagnostic_integration -v`

Expected: PASS with the real process-decision, watcher, recorder, cursor, and export chain.

- [ ] **Step 2: Assert the install ZIP contains both diagnostic backend modules**

Add exact assertions for
`TrainerRelay/py_modules/trainer_relay/diagnostics.py` and
`TrainerRelay/py_modules/trainer_relay/diagnostic_settings.py`, generate the
archive, and run `python -m unittest discover -s tests_packaging -p "test_*.py"`.

- [ ] **Step 3: Update version and user documentation**

Document persistent 50 MB behavior, allowed/prohibited data, Diagnostics page workflow, export/clear, DevTools filter `[TrainerRelay:diagnostic]`, and physical test steps. Preserve `.12` as the known picker/backend fix and mark `.13` experimental.

- [ ] **Step 4: Run every local gate fresh**

```bash
python -m unittest discover -s tests_backend -p "test_*.py"
python -m compileall -q main.py trainer_relay tests_backend tests_packaging
.\node_modules\.bin\biome.cmd check src tests vitest.config.ts
.\node_modules\.bin\tsc.cmd --noEmit
.\node_modules\.bin\tsc.cmd --noEmit -p tsconfig.test.json
.\node_modules\.bin\vitest.cmd run
.\node_modules\.bin\rollup.cmd -c
python scripts/package_trainer_relay.py
python -m unittest discover -s tests_packaging -p "test_*.py"
```

Expected: zero failures; report exact backend/frontend/package counts, ZIP entry count, bytes, and SHA-256.

- [ ] **Step 5: Review and privacy-audit the final diff**

Run:

```bash
rg -n "token|secret|password|cookie|authorization|credential|PROTON_REMOTE_DEBUG_CMD|cmdline|environ" trainer_relay src tests_backend tests
git diff --check
git status --short --branch
```

Every production occurrence must be a rejection/redaction rule or controlled read; no logging call may receive complete `cmdline` or `environ` content.

- [ ] **Step 6: Update handoff and commit release candidate**

```bash
git add -- package.json README.md docs/GUIA-INSTALACAO-TESTES-E-LOGS.md docs/STEAM-DECK-VALIDATION.md docs/notes/2026-08-29-trainer-relay-handoff.md tests_backend/test_diagnostic_integration.py tests_packaging/test_package_layout.py
git commit -m "release: prepare experimental 13 diagnostics"
```

- [ ] **Step 7: Push, tag, verify CI/release asset, and create user kit**

Push `feat/trainer-relay` and `main`, tag `v0.1.0-experimental.13`, wait for branch/main/tag workflows, download the published `TrainerRelay.zip`, compare SHA-256 byte-for-byte with the local deterministic ZIP, and create `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.13-kit` containing the verified ZIP and Portuguese guide.

- [ ] **Step 8: Run physical GOG then Epic gates**

On the Deck, confirm diagnostic persistence across restart, live DevTools candidate reasons, TXT export, clear scope, successful trainer state transitions, one instance, retry safety, selective shutdown, then repeat the functional path for one Epic shortcut. Keep the release experimental until both pass.
