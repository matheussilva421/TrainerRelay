# Trainer Relay handoff — 2026-08-29

## Objective

Implement the approved Trainer Relay plan from upstream CheatDeck without
modifying UniFiDeck, Decky Loader, Proton, Steam Runtime, or the parent Mods
repository.

## Current state

- Worktree: `C:\Users\slvma\Downloads\Github\Mods\.worktrees\trainer-relay`
- Branch: `feat/trainer-relay`
- Base: `2921aaff9c46cc287e5d46210eaaee7dd906d932`
- Current frontend suite: 148 Vitest tests passed using a single fork worker.
- Current backend suite: 46 unittest tests passed.
- Current package: 19 deterministic archive entries; 53,227 bytes; SHA-256
  `3E3A83C282D935BFE9EF8FA0D76267EBEC2A20864190C15CA908920A2AF301FD`.
- GitHub CLI authentication is valid outside the sandbox.
- Fork: `https://github.com/matheussilva421/TrainerRelay`.

## Completed

- Upstream cloned and isolated worktree created.
- pnpm dependencies installed from the lockfile.
- Approved design and implementation plan recorded.
- Task 1 product identity, attribution, glossary, and watcher ADR implemented.
- Task 1 typecheck and build validation completed; the build workflow packages
  the product as `TrainerRelay.zip`.
- Task 2 added strict Epic/GOG shortcut classification, immutable v1 config
  decoding/helpers, and fail-closed legacy launch-option migration.
- Task 2 validation: 115/115 Vitest tests, both TypeScript typechecks, and
  focused Biome checks are green. Biome now explicitly uses the repository's
  LF line-ending convention, so the repository-wide check is green without
  changing removed or unrelated history.
- Task 3 implemented the Python runtime, stable `/proc` session discovery,
  environment/UMU resolution, owned process-group lifecycle and typed RPCs.
- Task 3 review added coverage for UniFiDeck's real negative signed app IDs;
  41/41 backend tests and compileall are green. Matching game processes that
  carry either legacy CheatDeck environment variable are now invalid_config
  and cannot launch a relay.
- Task 4 replaced the inherited generic UI with a focused fail-closed Relay
  page, typed RPC client, AppDetails hook, verified legacy migration flow,
  `.exe`-only picker, explicit enablement, prefix override and status/retry
  controls. Obsolete generic UI/settings files were removed.
- Task 4 validation: 136/136 Vitest tests, 41/41 backend tests, both
  TypeScript typechecks, Biome and Rollup are green. Details are in
  `.superpowers/sdd/2026-08-29-trainer-relay-implementation-plan/task-4-report.md`.
- Task 5 added deterministic packaging, artifact-layout tests, complete Python
  runtime packaging, CI gates, the experimental release documentation, and
  the physical Steam Deck validation checklist. The local package test is
  green and the extracted package compiles successfully.
- The first tag-triggered Actions run exposed two Linux-only gate issues: UMU
  temporary fixtures lacked executable bits, and the frontend checkout used
  LF while the repository baseline used CRLF. The fixture now sets execute
  permission and the maintained frontend is normalized to LF with Biome.
  Fresh local gates remain green and the package is now canonical across
  Windows and Linux checkout newline conversion.
- Package text entries are normalized to LF before compression, making the
  archive bytes independent of Windows checkout newline conversion. The
  release asset now matches the local validated hash exactly.

## Next action

Task 5 local gates and GitHub publication are complete. Next: run the physical
Steam Deck checklist for one Epic and one GOG title; keep the release
experimental until both pass.

## GitHub

The formal fork contains the complete implementation through `e082589` on
both `feat/trainer-relay` and `main`. The annotated tag
`v0.1.0-experimental.1` remains safely at `276e55c`; it was not overwritten.
Its published prerelease asset was replaced with the canonical, validated ZIP
whose digest is recorded above. No upstream PR was opened. The tag-triggered
run for the first commit failed only on the two platform-only issues recorded
above; subsequent `main` gates `33267343177`, `33267324072`, `33267539436`,
and `33267536034` passed. Steam Deck validation remains explicitly pending.

## Task 5 local checkpoint — package and gates complete

- Added `scripts/package_trainer_relay.py`, which emits a deterministic
  `TrainerRelay.zip` with one top-level directory and only relocatable runtime
  files. The package includes the complete `trainer_relay/` directory and
  excludes tests, caches, lockfiles, logs, environment files, and source maps.
- Added `tests_packaging/test_package_layout.py` and the `package`/
  `test:package` scripts. The focused and discovery package tests pass.
- Rewrote `README.md`, added `docs/STEAM-DECK-VALIDATION.md`, extended
  `CONTEXT.md`, corrected package ownership metadata, and removed obsolete
  generic settings RPCs from `main.py` and `src/infra/decky.ts`.
- Updated `.github/workflows/trainer-relay-build.yml` to gate pushes and pull
  requests with backend tests/compileall, frontend lint/typecheck/test/build,
  package-layout verification, and complete artifact packaging. `v*` tags
  publish the ZIP and experimental markers set prerelease status.
- Fresh local results: 41/41 backend unittest, compileall, Biome, both
  TypeScript typechecks, 136/136 Vitest, Rollup build, 1/1 package-layout test,
  extracted-package compileall, deterministic hash comparison — all green.
- No physical Steam Deck is attached. Do not promote this release to stable;
  execute `docs/STEAM-DECK-VALIDATION.md` on one Epic and one GOG title after
  publication.

## Task 5 follow-up checkpoint — Linux CI portability fix

- Root cause from failed Actions run `33267031544`: Linux correctly rejected
  non-executable temporary UMU fixtures, and the CI checkout presented the
  frontend files as LF while Biome was configured for CRLF.
- Fixed only the test fixtures and maintained frontend formatting convention.
  No production watcher behavior or packaged runtime file changed.
- Fresh results after the fix: 41/41 backend unittest, compileall, Biome,
  both TypeScript typechecks, 136/136 Vitest, Rollup, and 1/1 package-layout
  test all green. `TrainerRelay.zip` remains SHA-256
  `FFE03A31AB849982C3FFD5EC4AC13773E6B6452888C1CEE8C3644319D1251683`.
- The follow-up and cross-platform package normalization were committed and
  pushed. The existing experimental tag was preserved; the release asset was
  updated only after the final `main` gates passed.

## Final publication checkpoint

- Feature branch and fork `main`: `e0825892b61f1f24e90a75cd4d0360f71508f3ac`.
- Tag `v0.1.0-experimental.1`: `276e55c64ae82bfb1fce996c5413200581605f4e`.
- Release: https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.1
- Asset: `TrainerRelay.zip`, 52,220 bytes, SHA-256
  `FFE03A31AB849982C3FFD5EC4AC13773E6B6452888C1CEE8C3644319D1251683`.
- Main-gate runs: `33267343177`, `33267324072`, `33267539436`, and
  `33267536034`, all successful.
- Earlier tag-run failures `33267031544`, `33267058241`, and `33266971804`
  are retained as history; they did not change the runtime package and were
  superseded by the follow-up gates.
- No upstream PR was opened. Do not install the ZIP on Windows as Decky.
- Pending only: physical Steam Deck validation and any later stable promotion.

## Task 3 incremental checkpoint — RED config/map/runtime contracts

- Added initial `unittest` coverage under `tests_backend/` for config, games.map,
  process discovery, environment/UMU, runner, watcher, and RPC contracts.
- First RED was corrected from package import absence to the intended missing
  backend modules. The current RED run discovered 14 tests: 9 config/games.map
  tests passed and 5 test modules failed to import because `process`,
  `environment`, `rpc`, `runner`, and `watcher` were not implemented yet.
- Config and games.map implementation is now minimally GREEN: 9/9 tests pass.
- Portability decision: fixtures accept POSIX and Windows absolute spellings,
  while the runtime default prefix remains the Linux `/home/...` layout.
- Next action: implement the remaining backend modules test-first, then wire
  `main.py`, run the complete backend suite and `compileall`, write the Task 3
  report, and commit only the scoped files.

## Task 3 final checkpoint — Python runtime and lifecycle complete

- Implemented `trainer_relay/` with config validation, fail-closed
  `games.map`, stable `/proc` discovery, sanitised environment/UMU resolution,
  owned process-group runner, watcher/retry lifecycle, and RPC adapter.
- Replaced `main.py` with thin Decky-compatible wiring for one watcher task,
  unload cancellation/cleanup, `RelayConfigV1` persistence, status, and manual
  retry RPCs.
- Added `tests_backend/` unittest coverage for config/map rejection, stat/path
  matching, store/prefix/game checks, redaction, UMU candidates, exact spawn,
  retry timing, ownership, lifecycle cleanup, RPC validation, and main wiring.
- TDD evidence is recorded in
  `.superpowers/sdd/2026-08-29-trainer-relay-implementation-plan/task-3-report.md`:
  real RED import/contract failures were observed before the corresponding
  implementations, followed by focused GREEN cycles.
- Final local validation: `python -m unittest discover -s tests_backend -p
  "test_*.py"` passed 40/40; `python -m compileall -q main.py trainer_relay
  tests_backend` passed; `git diff --check` passed.
- No UI/TypeScript files, parent repository files, game process, wineserver,
  global UMU process, or unowned process group was modified or signalled.
- Commit scope: the Task 3 implementation, report, and this final checkpoint
  are committed in this worktree. No push, PR, release, or real Steam Deck
  validation is part of this checkpoint.

## Code-review correction checkpoint — experimental.2

- Corrected all six findings from the post-release review using observed
  RED/GREEN cycles.
- Process discovery no longer accepts `/proc/<pid>/comm` as a basename
  fallback. The exact normalized expected executable must appear in `cmdline`.
- PATH fallback now enumerates every executable `umu-run`, deduplicates the
  same resolved file, and fails with `umu_ambiguous` when distinct candidates
  exist.
- Python discovery and relay lifecycle states now use shared closed string
  enums. Invalid runtime state construction raises instead of admitting an
  arbitrary string.
- Frontend absolute-path and trainer-executable validation now live in one
  domain module used by config decoding, migration, actions, and prefix UI.
- Verified legacy migration now persists a disabled configuration before
  changing launch options, re-reads AppDetails, and only then persists the
  enabled configuration. Any verification or persistence failure leaves the
  relay disabled.
- `RelayPage` is now a presentation component; React effects, polling,
  persistence, migration orchestration, and actions moved to
  `useRelayPageController`.
- Added backend regression tests for exact executable matching, unique PATH
  resolution, and closed states. Added frontend tests for shared path
  validation and the complete migration activation order/failure behavior.
- Fresh pre-package gates: 46/46 backend tests and 148/148 frontend tests
  passed; compileall, Biome, both TypeScript typechecks, and Rollup passed.
- Delivery version advanced to `v0.1.0-experimental.2`; the existing `.1` tag
  and release remain immutable. The deterministic ZIP has 19 entries, is
  53,227 bytes, and has SHA-256
  `3E3A83C282D935BFE9EF8FA0D76267EBEC2A20864190C15CA908920A2AF301FD`.
  Commit, Actions, and release details will be recorded after publication.
- Physical Steam Deck validation remains pending; do not promote to stable.
