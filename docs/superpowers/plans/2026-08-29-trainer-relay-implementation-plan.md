# Trainer Relay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Follow TDD and commit each task.

**Goal:** Build and package Trainer Relay, a fail-closed Decky plugin that launches `.exe` trainers in the Wine prefix of supported UniFiDeck Epic/GOG sessions.

**Architecture:** A small TypeScript frontend classifies shortcuts, stores versioned per-game configuration, performs confirmed legacy migration, and displays backend state. A modular Python backend parses `games.map`, discovers stable processes through `/proc`, builds a sanitised UMU environment, and owns trainer lifecycle.

**Tech Stack:** TypeScript, React, Vitest, Python 3 standard library, Decky Loader APIs, pnpm/Rollup.

**Spec:** `docs/superpowers/specs/2026-08-29-trainer-relay-design.md`

## Global Constraints

- Support only literal `epic:<id>` and `gog:<id>` launch identities executed by `unifideck-launcher`.
- Accept only absolute regular `.exe` trainer files and absolute prefix overrides.
- Never use `shell=True`, eval shell source, log environment values, or terminate a process not created by Trainer Relay.
- Game launch and lifecycle remain independent of every relay failure.
- Use TDD: observe each new behavior test fail before writing production code.
- Preserve GPL-3.0-or-later attribution while using Trainer Relay branding and repository URLs.

---

### Task 1: Independent product identity and domain model

**Files:**
- Modify product metadata, route/menu keys, package metadata, README, and build/release workflow names.
- Create `CONTEXT.md` and `docs/adr/0001-session-watcher.md`.
- Preserve LICENSE and add explicit derivation attribution.

**Deliverable:** The plugin, package, routes, ZIP target, and documentation identify `Trainer Relay`/`TrainerRelay`, with no claim of official affiliation. General CheatDeck settings remain temporarily present until Task 4 replaces the UI.

**Verification:** Run focused metadata/build checks, `pnpm run typecheck`, and `pnpm run build`.

### Task 2: Frontend domain, shortcut classification, configuration, and migration

**Files:**
- Create focused domain modules under `src/domain/relay/`.
- Create or update Vitest tests under `tests/`.

**Interfaces:**
- Produce `LaunchIdentity`, `RelayGameConfig`, `RelayConfigV1`, `RelayStatus`, shortcut classification, config decoding/defaulting, and legacy migration planning.
- Migration must preserve unrelated launch-option source and return the exact expected persisted source for verification.

**Verification:** Focused red-green Vitest cycles followed by all frontend tests.

### Task 3: Python runtime discovery and lifecycle

**Files:**
- Create a focused `trainer_relay/` package for models, games-map parsing, process discovery, environment building, UMU resolution, runner, and watcher.
- Replace the backend entry point with RPC wiring and lifecycle startup/shutdown.
- Create `tests_backend/` using `unittest` and controlled fake proc/maps/UMU fixtures.

**Interfaces:**
- RPC methods: `get_relay_config`, `set_relay_game_config`, `get_relay_status`, `retry_relay`.
- Session identity is PID plus start time; polling is one second.
- Initial stability window is three seconds; one retry after two seconds; owned process-group termination grace is five seconds.

**Verification:** Focused red-green unittest cycles, full backend tests, and `python -m compileall`.

### Task 4: Decky frontend integration and supported-only UI

**Files:**
- Replace the existing general settings views/hooks with Trainer Relay configuration/status UI.
- Update Steam integration and context-menu routing as needed.
- Add frontend tests for state mapping and migration orchestration.

**Interfaces:**
- Unsupported shortcuts show information only.
- Supported shortcuts show `.exe` selection, enablement, optional prefix override, sanitised diagnostics, migration confirmation, status, and retry.
- Configuration is enabled only after legacy launch-option persistence is re-read and verified.

**Verification:** Focused red-green tests, then lint, typecheck, full Vitest, and build.

### Task 5: Packaging, CI, release documentation, and final validation

**Files:**
- Ensure Python package and frontend output are included in `TrainerRelay.zip`.
- Add backend gates to CI and an experimental release workflow/artifact name.
- Create Steam Deck validation guide and update `docs/notes/2026-08-29-trainer-relay-handoff.md`.

**Verification:** Run backend tests, compileall, lint, typecheck, frontend tests, build, generate ZIP, and inspect its exact contents. Record Steam Deck tests as pending until performed on-device.

