# Trainer Relay Cheat Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fail-closed FLiNG and manual cheat controls to the Decky sidebar using an ephemeral native `SendInput` helper, while defining the Relay-side cooperative-state contract.

**Architecture:** A separate controls configuration and exact-hash adapter catalog resolve symbolic hotkeys. The existing watcher exposes a revalidated command context, a bounded one-shot runner re-enters the same UMU container to execute a native helper, and typed RPC/UI layers expose command-only or authoritative controls without conflating them.

**Tech Stack:** Python 3/unittest, TypeScript/React/Vitest, C/Win32, MSVC GitHub Actions, Decky Loader RPC/UI, UMU/Proton.

**Spec:** `docs/superpowers/specs/2026-09-01-trainer-relay-cheat-controls-design.md`

## Global Constraints

- Do not implement or invoke XTest, X11 injection, Wayland injection, `uinput`, root privileges, or Decky root flags.
- FLiNG/manual success is exactly `outcome: "requested", state: "unknown"`; only a fresh cooperative acknowledgement may return `enabled` or `disabled`.
- Commands require the same running `pid + starttime`, owned trainer, effective prefix, verified container bus, and identity at dispatch time.
- The helper is native Win32, one-shot, `shell=False`, five-second timeout, one process group owned by Trainer Relay, and never resident.
- The hotkey surface is a finite symbolic allowlist; no shell text, arbitrary VK, executable path, trainer argument, or script may enter a command request.
- Existing `RelayConfigV1`, game/trainer lifecycle, and v0.1 diagnostics remain backward compatible.
- Use strict TDD: add one failing behavior test, observe the expected failure, implement the minimum, and rerun focused plus relevant regression tests.
- Do not log environments, absolute trainer paths, capability tokens, or arbitrary helper output.

---

### Task 1: Hotkey, manual-config, and exact-hash catalog domain

**Files:**
- Create: `trainer_relay/hotkeys.py`
- Create: `trainer_relay/cheat_config.py`
- Create: `trainer_relay/cheat_catalog.py`
- Create: `trainer_relay/data/fling_adapters_v1.json`
- Create: `tests_backend/test_hotkeys.py`
- Create: `tests_backend/test_cheat_config.py`
- Create: `tests_backend/test_cheat_catalog.py`
- Modify: `scripts/package_trainer_relay.py`
- Modify: `tests_packaging/test_package_layout.py`

**Interfaces:**
- Produces: `normalize_hotkey(value: Mapping[str, Any]) -> dict[str, Any]`
- Produces: `hotkey_to_vk(value: Mapping[str, Any]) -> tuple[int, int]`
- Produces: `decode_cheat_controls_config(value: Any) -> dict[str, Any]`
- Produces: `CheatCatalog.load(path: Path)`, `CheatCatalog.resolve(sha256: str, identity: str)`
- Produces: packaged read-only adapter JSON and data lookup helper.

- [ ] **Step 1: Write failing hotkey tests**

Add table-driven literals for canonical modifier ordering, every key family boundary, duplicates, unknown keys, arbitrary integers, extra fields, and control characters. The production mutation caught is accepting a key/chord outside the finite spec allowlist.

- [ ] **Step 2: Verify the hotkey tests fail because the module is absent**

Run: `python -m unittest tests_backend.test_hotkeys -v`  
Expected: FAIL/ERROR importing `trainer_relay.hotkeys`.

- [ ] **Step 3: Implement minimal symbolic normalization and VK mapping**

Use explicit dictionaries and modifier bits `ctrl=1`, `alt=2`, `shift=4`; reject non-mappings, extra fields, duplicate modifiers, non-canonical unsupported values, and booleans where integers might otherwise pass.

- [ ] **Step 4: Verify hotkey tests pass**

Run: `python -m unittest tests_backend.test_hotkeys -v`  
Expected: all tests PASS.

- [ ] **Step 5: Write failing config and catalog tests**

Cover separate key `CheatControlsConfigV1`, UUID IDs, 1–80 character labels, maximum 64 controls, exact trainer SHA-256 binding, invalid entry dropping on decode, strict persistence validation, duplicate catalog ID/hash/cheat rejection, identity restrictions, and unknown-hash `None`.

- [ ] **Step 6: Verify config/catalog tests fail for missing behavior**

Run: `python -m unittest tests_backend.test_cheat_config tests_backend.test_cheat_catalog -v`  
Expected: FAIL because config/catalog APIs are missing.

- [ ] **Step 7: Implement config and catalog minimally**

Use SHA-256 lowercase hex validation, backend-generated UUIDs, immutable descriptor dataclasses, and all-or-nothing catalog loading. Add only physically supported adapter records whose hashes and hotkeys are evidenced by the repository reports; placeholders stay absent.

- [ ] **Step 8: Add package-data tests and implementation**

First make packaging assert `TrainerRelay/data/fling_adapters_v1.json`; observe failure; then include the catalog deterministically and normalize it as text.

- [ ] **Step 9: Run Task 1 regressions and commit**

Run: `python -m unittest tests_backend.test_hotkeys tests_backend.test_cheat_config tests_backend.test_cheat_catalog tests_packaging.test_package_layout -v`  
Run: `python -m unittest discover -s tests_backend -p "test_*.py"`  
Expected: all PASS.

Commit: `feat: add hash-bound cheat control catalog`

---

### Task 2: Revalidated command context and one-shot helper runner

**Files:**
- Create: `trainer_relay/command_runner.py`
- Create: `trainer_relay/helper_manifest.py`
- Create: `tests_backend/test_command_runner.py`
- Create: `tests_backend/test_helper_manifest.py`
- Modify: `trainer_relay/watcher.py`
- Modify: `trainer_relay/types.py`
- Modify: `tests_backend/test_watcher.py`

**Interfaces:**
- Produces: immutable `CommandContext(identity, session, trainer_sha256, trainer_arch, environment, umu_run, expected_reentry_bus)`.
- Produces: `RelayWatcher.command_context(identity: str) -> CommandContext` that raises a bounded reason when revalidation fails.
- Produces: `OneShotCommandRunner.run(context, helper, vk, modifiers, hold_ms=40) -> CommandExecution`.

- [ ] **Step 1: Write failing watcher command-context tests**

Cover running session success and rejection for disabled, launching, ended/recycled session, mismatched trainer ownership, ambiguity, changed trainer hash, and absent reentry bus. Assert no command process is spawned on every rejection.

- [ ] **Step 2: Observe RED**

Run: `python -m unittest tests_backend.test_watcher -v`  
Expected: FAIL because `command_context` and command metadata do not exist.

- [ ] **Step 3: Implement the minimum watcher context**

Retain the effective launch environment and verified bus only inside the active runtime state. Re-run process discovery with the exact expected session at command time, re-hash the trainer, and return an immutable copy. Do not expose this data through diagnostics or status RPC.

- [ ] **Step 4: Verify watcher GREEN**

Run: `python -m unittest tests_backend.test_watcher -v`  
Expected: PASS.

- [ ] **Step 5: Write failing manifest/runner tests**

Use temporary fake helper bytes and literal manifest hashes. Cover missing/corrupt/wrong-architecture helper, structured argv, `shell=False`, exact UMU environment, reentry marker, bounded JSON, accepted-count mismatch, non-zero exit, malformed/oversized output, five-second timeout, and process-group-only termination.

- [ ] **Step 6: Observe runner RED**

Run: `python -m unittest tests_backend.test_helper_manifest tests_backend.test_command_runner -v`  
Expected: FAIL because the modules are absent.

- [ ] **Step 7: Implement the one-shot runner**

Build argv exactly as `[umu_run, helper, "--protocol", "1", "--key", decimal_vk, "--modifiers", decimal_mask, "--hold-ms", "40"]`. Use `subprocess.Popen(..., shell=False, start_new_session=True)`, bounded capture, a five-second monotonic deadline, and only `killpg` for the helper's group.

- [ ] **Step 8: Run Task 2 regressions and commit**

Run: `python -m unittest tests_backend.test_watcher tests_backend.test_helper_manifest tests_backend.test_command_runner tests_backend.test_runner -v`  
Run: `python -m unittest discover -s tests_backend -p "test_*.py"`  
Expected: all PASS.

Commit: `feat: add fail-closed one-shot command runner`

---

### Task 3: Native Win32 SendInput helper and build/package pipeline

**Files:**
- Create: `native/input-helper/input_helper.c`
- Create: `native/input-helper/input_helper_test.c`
- Create: `native/input-helper/input_helper.h`
- Create: `scripts/build_input_helper.ps1`
- Create: `scripts/generate_helper_manifest.py`
- Create: `.github/workflows/build-input-helper.yml`
- Create after build: `bin/TrainerRelay.InputHelper.x86.exe`
- Create after build: `bin/TrainerRelay.InputHelper.x64.exe`
- Create after build: `bin/input-helper-manifest.json`
- Modify: `scripts/package_trainer_relay.py`
- Modify: `tests_packaging/test_package_layout.py`

**Interfaces:**
- Produces: helper protocol v1 defined by the spec.
- Consumes: only `--protocol`, `--key`, `--modifiers`, and `--hold-ms`.
- Produces: one bounded JSON line and documented exit codes.

- [ ] **Step 1: Write host-level failing C tests**

Inject a fake send function and sleep function. Assert literal input order for `ctrl+alt+F1`, reverse releases, partial-send cleanup, invalid argument rejection, bounded JSON, and no extra calls.

- [ ] **Step 2: Observe C test RED in CI/local toolchain**

Run through `scripts/build_input_helper.ps1 -TestOnly`; on this workstation, record the missing C compiler as an environment boundary and run the same command in Windows GitHub Actions where MSVC is available.

- [ ] **Step 3: Implement minimal Win32 helper**

Use `SendInput`, `Sleep`, fixed-size arrays/buffers, `strtoul` with full-consumption checks, finite VK validation duplicated defensively in C, and best-effort key-up cleanup. Do not link networking, shell, process discovery, or trainer code.

- [ ] **Step 4: Build x86/x64 and verify PE architecture**

The PowerShell script locates Visual Studio with `vswhere`, invokes `vcvarsall.bat x86` and `vcvarsall.bat amd64`, compiles with `/O1 /GS /DYNAMICBASE /NXCOMPAT`, runs host tests, and writes the two PEs. The Python manifest script reads the PE machine field, hashes both files, and emits deterministic JSON.

- [ ] **Step 5: Make packaging tests fail then include binaries**

Add assertions for both PEs, exact manifest hashes, no executable permission requirement inside ZIP, and deterministic package bytes. Observe RED before changing package sources.

- [ ] **Step 6: Add CI artifact path and run Task 3 gates**

The workflow builds helpers on `windows-latest`, uploads only both PEs and manifest, then a package job downloads them and runs backend/frontend/package gates. No release is published automatically.

Run: `python -m unittest tests_packaging.test_package_layout -v`  
Run: `python scripts/package_trainer_relay.py`  
Expected: PASS and ZIP contains all three `bin/` entries.

Commit: `feat: package ephemeral win32 input helper`

---

### Task 4: Cheat-control service, cooperative boundary, and typed RPCs

**Files:**
- Create: `trainer_relay/cheat_service.py`
- Create: `trainer_relay/cooperative.py`
- Create: `tests_backend/test_cheat_service.py`
- Create: `tests_backend/test_cooperative.py`
- Modify: `trainer_relay/rpc.py`
- Modify: `main.py`
- Modify: `tests_backend/test_rpc.py`
- Modify: `tests_backend/test_main.py`
- Modify: `trainer_relay/diagnostics.py`
- Modify: `tests_backend/test_diagnostics.py`

**Interfaces:**
- Produces RPCs `get_cheat_controls`, `add_manual_cheat_control`, `remove_manual_cheat_control`, and `send_cheat_command`.
- Consumes Task 1 catalog/config and Task 2 command context/runner.
- Produces cooperative descriptor/ack decoders that never connect unless a trainer supplies a valid v1 endpoint descriptor.

- [ ] **Step 1: Write failing service tests**

Cover adapter precedence, exact-hash manual fallback, changed-hash hiding, zero/multiple/no running sessions, one in-flight command, adapter/manual requested+unknown, runner failure, and bounded diagnostics.

- [ ] **Step 2: Observe service RED**

Run: `python -m unittest tests_backend.test_cheat_service -v`  
Expected: FAIL because service is absent.

- [ ] **Step 3: Implement minimum service**

Generate UUID command IDs server-side, resolve descriptors server-side, call `watcher.command_context` immediately before launch, serialize per identity with `asyncio.Lock`, and map all internal exceptions to allowlisted codes.

- [ ] **Step 4: Write and implement cooperative decoder tests**

Test schema version, identity/build/token binding, operation allowlist, monotonic revision, command-ID acknowledgement, freshness deadline, and stale fallback to unknown. Implement only the Relay-side transport/decoder boundary; do not claim a legacy trainer supports it.

- [ ] **Step 5: Write failing RPC/main tests then expose calls**

Require exact request key sets, label/hotkey validation, safe response decoding, and no environment/path/raw exception leakage. Add Decky classmethods only after observing missing-method failures.

- [ ] **Step 6: Extend diagnostic allowlists with tests first**

Add `command` category and only the events listed by the spec. Reject arbitrary detail keys and values.

- [ ] **Step 7: Run Task 4 regressions and commit**

Run: `python -m unittest tests_backend.test_cheat_service tests_backend.test_cooperative tests_backend.test_rpc tests_backend.test_main tests_backend.test_diagnostics -v`  
Run: `python -m unittest discover -s tests_backend -p "test_*.py"`  
Expected: all PASS.

Commit: `feat: expose typed cheat control rpc`

---

### Task 5: Decky routed-page and Quick Access controls

**Files:**
- Create: `src/domain/cheats/types.ts`
- Create: `src/domain/cheats/decoder.ts`
- Create: `src/infra/cheatRpc.ts`
- Create: `src/hooks/useCheatControls.ts`
- Create: `src/components/CheatControlList.tsx`
- Create: `src/components/ManualCheatEditor.tsx`
- Create: `tests/cheat-decoder.test.ts`
- Create: `tests/cheat-rpc.test.ts`
- Create: `tests/cheat-control-list.test.ts`
- Create: `tests/manual-cheat-editor.test.ts`
- Create: `tests/cheat-sidebar.test.ts`
- Modify: `src/views/RelayPage.tsx`
- Modify: `src/views/Content.tsx`
- Modify: `tests/relay-page.test.ts`

**Interfaces:**
- Consumes Task 4 RPC wire contracts.
- Produces focused `ButtonItem` rows for command-only cheats and authoritative toggles only for fresh cooperative state.

- [ ] **Step 1: Repair/install the locked frontend dependencies if necessary**

Use the committed `pnpm-lock.yaml` and `pnpm@11.5.0`; do not update versions. Verify `pnpm exec vitest --version` before changing source.

- [ ] **Step 2: Write failing decoder/RPC tests**

Cover malformed identities/hashes/hotkeys, extra fields, unsafe diagnostic strings, requested+unknown, and rejection of enabled/disabled without cooperative authority.

- [ ] **Step 3: Observe frontend RED then implement typed boundary**

Run: `pnpm exec vitest run tests/cheat-decoder.test.ts tests/cheat-rpc.test.ts`  
Expected: FAIL for missing modules, then PASS after minimal implementation.

- [ ] **Step 4: Write failing component tests**

Assert native focused rows, label/hotkey rendering, busy disablement, no fake toggle for adapter/manual, `Comando enviado; estado desconhecido`, cooperative toggle freshness, add/remove manual controls, finite key selector, 80-character limit, and touch/controller callbacks.

- [ ] **Step 5: Implement page and sidebar controls minimally**

Reuse Decky `ButtonItem`, `DialogButton`, `Field`, `Focusable`, `ModalRoot`, and finite selectors. Poll only while mounted and use bound browser timers. Never expose a free-form VK or command input.

- [ ] **Step 6: Run Task 5 regressions and commit**

Run: `pnpm exec vitest run tests/cheat-decoder.test.ts tests/cheat-rpc.test.ts tests/cheat-control-list.test.ts tests/manual-cheat-editor.test.ts tests/cheat-sidebar.test.ts tests/relay-page.test.ts`  
Run: `pnpm run lint`  
Run: `pnpm run typecheck`  
Run: `pnpm run test`  
Run: `pnpm run build`  
Expected: all PASS.

Commit: `feat: add trainer controls to decky sidebar`

---

### Task 6: Version, documentation, full gates, and experimental artifact

**Files:**
- Modify: `package.json`
- Modify: `main.py`
- Modify: `README.md`
- Modify: `CONTEXT.md`
- Modify: `docs/GUIA-INSTALACAO-TESTES-E-LOGS.md`
- Modify: `docs/STEAM-DECK-VALIDATION.md`
- Modify: `docs/notes/2026-08-29-trainer-relay-handoff.md`

**Interfaces:**
- Produces matching experimental version in package/backend and an installable deterministic `TrainerRelay.zip`.

- [ ] **Step 1: Add failing version/package assertions**

Change packaging expectations first to the next experimental version and require helper/catalog/control runtime files; observe RED.

- [ ] **Step 2: Update versions and user documentation**

Document automatic exact-hash controls, manual fallback, helper ephemerality, unknown-state semantics, no XTest/root, diagnostics events, rollback, and the physical validation checklist.

- [ ] **Step 3: Run all local gates**

Run: `python -m unittest discover -s tests_backend -p "test_*.py"`  
Run: `python -m compileall main.py trainer_relay tests_backend scripts`  
Run: `pnpm run lint`  
Run: `pnpm run typecheck`  
Run: `pnpm run test`  
Run: `pnpm run build`  
Run: `python -m unittest discover -s tests_packaging -p "test_*.py"`  
Run: `python scripts/package_trainer_relay.py`  
Run: `git diff --check`  
Expected: all PASS; summarize counts without dumping logs.

- [ ] **Step 4: Inspect the archive and update handoff**

Record ZIP SHA-256, entry count, helper PE architectures/hashes, tests, unverified physical gates, exact installation steps, and rollback. Preserve the statement that cooperative state is not physically validated.

- [ ] **Step 5: Commit and push**

Commit: `release: package experimental cheat controls`  
Push branch `feat/trainer-relay` without tagging or publishing a GitHub Release until the Steam Deck gate passes.

- [ ] **Step 6: Physical Steam Deck gate**

Install the ZIP, test one recognized FLiNG and one manual chord, export diagnostics, and verify ephemeral helper cleanup/no stuck modifiers/game-trainer survival. Record results in `docs/STEAM-DECK-VALIDATION.md`; only then consider a release tag.
