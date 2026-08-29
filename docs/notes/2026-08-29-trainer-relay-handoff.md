# Trainer Relay handoff — 2026-08-29

## Objective

Implement the approved Trainer Relay plan from upstream CheatDeck without
modifying UniFiDeck, Decky Loader, Proton, Steam Runtime, or the parent Mods
repository.

## Current state

- Worktree: `C:\Users\slvma\Downloads\Github\Mods\.worktrees\trainer-relay`
- Branch: `feat/trainer-relay`
- Base: `2921aaff9c46cc287e5d46210eaaee7dd906d932`
- Current frontend suite: 151 Vitest tests passed using a single fork worker.
- Current backend suite: 46 unittest tests passed.
- Current package: 19 deterministic stored archive entries; 174,406 bytes;
  SHA-256
  `E2D0418B70E8C4BEC62BEEF45C65FC7700BEABA1DA91095EFAF42A6BD5997125`.
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

The plain UniFiDeck launch-option migration blocker is fixed locally in
experimental.5. Next: publish and independently verify `.5`, replace `.4` on
the physical Steam Deck, repeat the photographed GOG launch, then run the
complete checklist for one GOG and one Epic title. Keep the release
experimental until both pass.

## GitHub

The formal fork contains the runtime hotfix commit
`9e6e9837d5d41c41b6584dcc89212419a4b8c586` on both
`feat/trainer-relay` and `main`. The earlier tags and assets remain preserved.
`v0.1.0-experimental.3` is explicitly marked superseded, and
`v0.1.0-experimental.4` is the recommended prerelease. Branch/main runs
`33275180521` and `33275182249`, plus tag/release run `33275289569`, all
passed. Documentation follow-up runs `33275665417` (feature branch) and
`33275681132` (`main`) also passed. No upstream PR was opened. Physical
GOG/Epic validation remains explicitly pending.

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

## Cross-runtime package reproducibility follow-up — experimental.3

- The `.2` tag workflow passed and published a prerelease, but independent
  download verification found that its ZIP container hash differed from the
  locally validated ZIP: all 19 entry names, sizes, and uncompressed SHA-256
  values matched, while Deflate output differed across Python/zlib runtimes.
- Added a RED package regression test requiring stored ZIP entries, then
  changed the packager from Deflate to `ZIP_STORED`. This removes compressor
  implementation/version variability while retaining deterministic metadata,
  LF-normalized text, exact layout, and the same runtime contents.
- `.2` remains immutable as historical evidence and is superseded by `.3`.
  No existing tag was moved and no release asset was overwritten.
- Delivery version advanced to `v0.1.0-experimental.3`. The current local ZIP
  has 19 stored entries, is 173,662 bytes, and has SHA-256
  `94808E9493AF40BC752749D3604CA1E2F56BCE9C7F1CBDBA84E1E931FDBB8443`.
- `.3` was published and independently verified. Runtime/package commit:
  `0e054dca8ed4b3518e39d4c427b3bf228a5c4671`. Branch and main runs
  `33273940797` and `33273952986` passed. Tag/release run `33273992659`
  passed all backend, frontend, build-plugin, layout, artifact, and publication
  jobs.
- Release: https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.3
- The downloaded GitHub asset is a prerelease ZIP with exactly 173,662 bytes
  and SHA-256
  `94808E9493AF40BC752749D3604CA1E2F56BCE9C7F1CBDBA84E1E931FDBB8443`,
  byte-identical to the fresh local package.
- The only remaining product gate is physical Steam Deck validation with one
  Epic and one GOG title. Stable promotion remains blocked until that manual
  checklist passes.

## User installation kit checkpoint

- Added `docs/GUIA-INSTALACAO-TESTES-E-LOGS.md`, a Portuguese end-user guide
  covering ZIP/hash verification, local/URL Decky installation, Epic/GOG
  configuration, legacy migration, state meanings, minimum device checks,
  privacy-bounded backend/frontend/plugin logs, a report template,
  troubleshooting, and rollback.
- The guide points only to `v0.1.0-experimental.3` and records the independently
  verified 173,662-byte ZIP/SHA-256. It does not weaken the physical Epic/GOG
  validation gate or expand the v1 runtime scope.
- Created the versioned user kit at
  `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.3-kit` with the
  installation ZIP and an identical `LEIA-ME` copy of the guide. The copied
  ZIP was rehashed as
  `94808E9493AF40BC752749D3604CA1E2F56BCE9C7F1CBDBA84E1E931FDBB8443`.
  No runtime/release asset changes were required.

## On-device Decky 3.2.6 crash hotfix — experimental.4

- User photographs from a physical Steam Deck showed BioShock 2 Remastered's
  UniFiDeck shortcut with literal identity `gog:482265568`, followed by Decky's
  plugin error screen. The trace was `TypeError: Illegal invocation` at
  `startRelayStatusPolling`, with `RelayPage` in the component stack.
- A deterministic controller-mount regression test reproduced the exact error
  by using browser-style timer methods that reject a missing receiver. The RED
  command produced the same `Illegal invocation` before any status response.
- Root cause: `useRelayPageController` passed `window.setInterval` and
  `window.setTimeout` as unbound callbacks. Decky/CEF invokes these WebIDL
  methods only with their original `window` receiver. Existing unit tests used
  plain functions and therefore did not model this browser contract.
- Added `bindBrowserTimers`, which wraps all four timer operations and calls
  them as methods of the original browser scope. Polling now binds
  set/clearInterval, and migration verification binds set/clearTimeout.
- Added regression coverage for both the real controller call site and all four
  browser timer methods. Focused RED became 2/2 GREEN; full local validation is
  46/46 backend and 150/150 frontend tests, with Biome, both TypeScript
  typechecks, compileall, and Rollup green.
- Delivery version advanced to `v0.1.0-experimental.4`. The deterministic
  19-entry package is 174,040 bytes with SHA-256
  `4AFD5979757B0CFD517A0EB89D3A2B424B6A90B262CA1ACF8625BDC10570E060`.
  Runtime hotfix commit: `9e6e9837d5d41c41b6584dcc89212419a4b8c586`.
- Branch/main runs `33275180521` and `33275182249` passed. Tag/release run
  `33275289569` passed frontend, backend, build/package and publication jobs.
- Release: https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.4
  The downloaded GitHub asset is exactly 174,040 bytes and SHA-256
  `4AFD5979757B0CFD517A0EB89D3A2B424B6A90B262CA1ACF8625BDC10570E060`,
  byte-identical to the locally validated package.
- The `.3` tag and asset were preserved for traceability, while its release is
  marked superseded with a link to `.4`.
- Created the replacement user kit at
  `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.4-kit`.
  Its renamed installation ZIP has the same verified SHA-256; the kit also
  contains the updated Portuguese installation, test and log guide. The `.3`
  kit was not changed or removed.
- Pending: uninstall/replace `.3` on the physical Deck, confirm the plugin page
  renders on Decky 3.2.6, repeat BioShock 2 Remastered (`gog:482265568`), and
  complete one GOG plus one Epic validation. Do not promote to stable yet.

## On-device plain UniFiDeck migration blocker — experimental.5

- Physical Deck photographs showed that `.4` loaded without the earlier CEF
  crash and classified `gog:1482265568`, but displayed `Legacy migration` as
  incomplete or unsafe and disabled trainer browsing, prefix saving, and
  enablement.
- Remote CEF logs confirmed that Trainer Relay loaded and issued
  `get_relay_config`/`get_relay_status` RPCs without a new JavaScript error.
- A read-only Vite probe reproduced the exact contract mismatch:
  `planLegacyMigration("gog:1482265568")` returned `blocked`, while
  `%command% gog:1482265568` returned `none`.
- Root cause: shortcut classification deliberately accepts the one-token
  UniFiDeck form, but migration planning rejected every non-empty source that
  omitted `%command%` before checking whether a legacy assignment existed.
- TDD RED added a real view-model regression for the photographed GOG identity;
  it failed because migration was `blocked`. The minimal fix reuses the shared
  literal identity parser and returns `none` only for one valid plain Epic/GOG
  identity. Malformed documents and partial legacy pairs remain blocked.
- Focused GREEN: 31/31 tests. Full local gates: 46/46 backend, 151/151
  frontend, 1/1 package layout, compileall, Biome, both TypeScript typechecks,
  and Rollup all passed.
- Delivery version is `v0.1.0-experimental.5`. The deterministic 19-entry ZIP
  is 174,406 bytes with SHA-256
  `E2D0418B70E8C4BEC62BEEF45C65FC7700BEABA1DA91095EFAF42A6BD5997125`.
- Runtime/release commit: `a2615b4ee4370c2ee85a028103d8c26440a636a9`.
  Branch/main runs `33276936863` and `33276938414` passed. Tag/release run
  `33277003480` passed frontend, backend, build/package and publication.
- Release: https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.5
  Its downloaded asset is byte-identical to the fresh local package at the
  size and SHA-256 above.
- `.4` is marked superseded with a link to `.5`; its tag and asset remain
  preserved. `.5` is the recommended prerelease with the verified size/hash.
- Created `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.5-kit`
  with the ZIP renamed to `TrainerRelay-v0.1.0-experimental.5.zip` and an
  updated Portuguese `LEIA-ME`. The kit ZIP is 174,406 bytes and SHA-256
  `E2D0418B70E8C4BEC62BEEF45C65FC7700BEABA1DA91095EFAF42A6BD5997125`.
  Kits `.3` and `.4` were not changed or removed.
- Pending only: commit/push this final documentation checkpoint and physically
  confirm that `.5` enables browsing/configuration for `gog:1482265568`, then
  complete the one-GOG/one-Epic runtime checklist. Do not promote to stable.
