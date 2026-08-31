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

Experimental.19 has a physical functional GOG PASS: BioShock 2 Remastered and
its trainer opened in the verified UMU context, an in-game trainer function
worked, and shutdown targeted only the owned trainer process group. Next:
verify Force Sync persistence and diagnostic clear behavior for GOG, then run
the complete physical checklist for one Epic title. Keep the release
experimental until every required row passes for both stores.

## GitHub

The formal fork contains experimental.19 implementation commit `f89f476` on
both `feat/trainer-relay` and `main`. The earlier tags and assets remain
preserved. `v0.1.0-experimental.3` is explicitly marked superseded, and
`v0.1.0-experimental.19` is the recommended prerelease. Implementation runs
`33360558539` (feature branch), `33360558446` (`main`), and tag/release run
`33360577462` passed. Documentation runs `33360874832` (feature branch) and
`33360875103` (`main`) also passed. No upstream PR was opened. GOG has a
physical functional PASS with two checklist items still pending; Epic remains
untested.

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

## On-device Decky file-picker fallback — experimental.6

- A physical Deck photograph confirmed that `.5` fixed the plain-identity
  migration blocker for `gog:1482265568`: the legacy warning disappeared and
  the configuration section became available. The remaining failure was that
  **Choose trainer** did not produce a usable file-picker interaction.
- Remote CEF inspection showed no Trainer Relay JavaScript exception. Decky
  emitted a visible-modal focus warning, indicating that the picker request was
  accepted but its SteamUI modal was not usable from the active Quick Access
  layer. The later CEF connection timed out after remote debugging became
  unavailable, so the release does not claim an upstream Decky modal fix.
- TDD RED added a rendered page regression requiring an editable manual trainer
  path and a **Save trainer path** action even when Decky's picker cannot be
  used. A second RED proved that a relative `trainer.exe` was sent toward
  persistence instead of being rejected locally.
- The minimal fix keeps the existing picker and adds a synchronized manual
  path field. Saving trims the value, requires an absolute `.exe`, persists the
  per-game configuration disabled, and still requires explicit enablement.
  The shared action now rejects unsafe paths before any backend RPC.
- Focused GREEN: 6/6 tests. Full local validation: 153/153 frontend, 46/46
  backend, 1/1 package-layout test, Biome, both TypeScript typechecks,
  compileall, Rollup build, and `git diff --check` all passed.
- Delivery version advanced to `v0.1.0-experimental.6`. The deterministic
  19-entry ZIP is 176,555 bytes with SHA-256
  `95F9B39942F36651B82CD9E2B2734906D51C55A1B9EAA345D5982D16304AE7E6`.
- Pending: commit/push, publish and independently verify the `.6` release
  asset, create the `.6` user kit, mark `.5` superseded, then physically enter
  a real absolute trainer path and complete one GOG plus one Epic runtime
  checklist. Do not promote to stable.

### Experimental.6 publication checkpoint

- Runtime/release commit `962042bb0ddea7bbdb142b31aaae5509711fb8fa`
  was pushed to both `origin/feat/trainer-relay` and `origin/main` and tagged
  `v0.1.0-experimental.6`.
- Branch runs `33278100648` and `33278101875` passed. Tag/release run
  `33278126873` passed frontend, backend, build/package, and publication jobs.
- Release: https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.6
  The downloaded asset is 176,555 bytes and SHA-256
  `95F9B39942F36651B82CD9E2B2734906D51C55A1B9EAA345D5982D16304AE7E6`,
  byte-identical to the independently generated local archive.
- `.5` remains available for traceability and is marked superseded with a link
  to `.6`. No historical tag or asset was removed.
- Created `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.6-kit`
  containing the verified versioned installation ZIP and the Portuguese
  installation/testing/log guide.
- Remaining physical validation: replace `.5` with `.6`, enter the exact
  absolute Linux trainer path in the new field, press **Save trainer path**,
  enable the relay, and run the GOG checklist. Then repeat with one Epic title.
  Any remaining runtime failure requires fresh filtered Decky and CEF logs.

## CheatDeck-style native file picker — experimental.7

- The user rejected manual trainer-path entry and clarified that the installed
  CheatDeck already provides controller/touch folder navigation. `.6` therefore
  remains a diagnostic fallback release, not the desired interaction.
- Analysis compared CheatDeck tags `v0.5.1`, `v1.0.0`, `v1.1.6`, `v1.2.1`,
  and `v2.0.0`. Every inspected version calls Decky's native
  `openFilePicker(FileSelectionType.FILE, ...)`; the modern function signature
  was already identical in Trainer Relay.
- The reusable difference is CheatDeck's UI/focus contract: a disabled path
  `TextField` and compact folder `DialogButton` share a dedicated `Focusable`
  row, and the button receives `onBrowse` directly. Trainer Relay `.6` instead
  used a large textual button plus an editable path field.
- TDD RED required the CheatDeck-style read-only field/folder-button contract
  and absence of **Save trainer path**. The minimal implementation adds
  `src/components/TrainerFilePicker.tsx`, ports the focus/layout behavior from
  CheatDeck, removes manual draft state/actions, and retains the existing
  absolute `.exe` validation before persistence.
- Focused GREEN: 6/6 tests. Full local gates: 153/153 frontend, 46/46 backend,
  1/1 package layout, Biome, both TypeScript typechecks, compileall, and Rollup
  passed.
- Delivery version is `v0.1.0-experimental.7`. The deterministic 19-entry ZIP
  is 176,394 bytes with SHA-256
  `6375AF2391AB01179103F1A3E9A374CF56C69C0E4D377FC43E337B40CFEA6B73`.
- Pending: final diff review, commit/push/tag/release publication, independent
  asset verification, `.7` kit creation, and physical confirmation that the
  folder button exposes Decky's navigable picker on Decky 3.2.6. Do not promote
  to stable before one GOG and one Epic runtime checklist passes.

### Experimental.7 publication checkpoint

- Runtime/release commit `9798b7a8dd0e5c4260e50fa4a9e73d66b964a00f`
  was pushed to `origin/feat/trainer-relay` and `origin/main` and tagged
  `v0.1.0-experimental.7`.
- Branch runs `33278844376` and `33278846042` passed. Tag/release run
  `33278862228` passed frontend, backend, build/package, and publication jobs.
- Release: https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.7
  The downloaded asset is 176,394 bytes and SHA-256
  `6375AF2391AB01179103F1A3E9A374CF56C69C0E4D377FC43E337B40CFEA6B73`,
  byte-identical to the fresh local archive.
- `.6` remains available and is marked superseded with a link to `.7`; no
  historical tag or asset was removed.
- Created `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.7-kit`
  with the verified versioned installation ZIP and Portuguese guide.
- Remaining physical validation: replace `.6` with `.7`, open the GOG shortcut,
  press the compact folder button, navigate to and select the trainer `.exe`,
  verify that the read-only field updates, enable the relay, and run the GOG
  checklist. Then repeat with one Epic title. If the picker still fails, capture
  fresh CEF logs while pressing the folder button; do not reintroduce typing.

## File-picker CEF instrumentation — experimental.8

- Physical Deck validation reported that `.7` still rendered the folder control
  but did not expose a usable selection flow. This turn intentionally did not
  guess at another UI fix; it instrumented the button-to-Decky API chain first.
- Live remote CEF inspection succeeded at
  `http://192.168.1.247:8081`. The Console was configured as **Errors only**,
  hiding 2,065 lower-level messages. The existing logger routed every severity,
  including `logger.error`, through `console.log`, so Trainer Relay diagnostics
  could not appear under that filter.
- TDD RED proved three missing contracts: error events were absent from
  `console.error`, info events were absent from `console.info`, and activating
  the folder button emitted no picker event. A second RED proved the
  `openFilePicker` call and resolution/rejection boundaries were silent.
- The minimal diagnostic implementation now emits scoped events prefixed with
  `[TrainerRelay:picker]`: `plugin-loaded`, `ui-activated`, `handler-enter`,
  `handler-blocked`, `home-requested`, `home-resolved`, `api-call`,
  `api-resolved`, `api-rejected`, `selection-received`, `persistence-result`,
  and `handler-failed`. Logger levels now map to the matching Console methods.
- Privacy boundary: events record booleans, status names, requested extension,
  and a bounded failure reason. They do not record the full trainer/home path,
  process environment, launch options, cookies, tokens, or credentials.
- Focused GREEN: 6/6 tests. Fresh full gates: Biome checked 49 files; both
  TypeScript typechecks passed; Vitest passed 158/158 across 19 files; backend
  unittest passed 46/46; compileall, Rollup, package layout 1/1, and
  `git diff --check` passed.
- Diagnostic delivery version is `v0.1.0-experimental.8`. The deterministic
  19-entry ZIP is 179,470 bytes with SHA-256
  `6C193E5B237102FE5614CDC5833BC9E177771C224B4EBB3236B7D4C266B4CAF9`.
- Next physical step: install `.8`, keep CEF Console on **Default levels**,
  filter `[TrainerRelay:picker]`, open Trainer Relay, press the folder button
  once, and capture the complete sequence. The last emitted event identifies
  whether the failure is UI activation, controller readiness, home RPC,
  Decky modal creation, modal settlement, or persistence.

### Experimental.8 publication checkpoint

- Runtime/docs commit: `83b4c2c5cbbcacaedcf682e500c6b67794603c81`
  (`fix: expose file picker diagnostics`). It was pushed to both
  `origin/feat/trainer-relay` and `origin/main`.
- Tag `v0.1.0-experimental.8` points to that commit. Release:
  https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.8
- Direct asset:
  https://github.com/matheussilva421/TrainerRelay/releases/download/v0.1.0-experimental.8/TrainerRelay.zip
- GitHub Actions passed for the branch (`33280628086`), main
  (`33280629868`), and tag/release (`33280639918`). The only annotation is the
  unrelated `actions/setup-python@v5` Node 20 deprecation notice; GitHub forced
  that action to Node 24 and all jobs passed.
- The official release asset is a 179,470-byte prerelease ZIP with GitHub
  digest `sha256:6c193e5b237102fe5614cdc5833bc9e177771c224b4ebb3236b7d4c266b4caf9`.
  An independent download matched the locally verified ZIP byte-for-byte.
- Release notes explicitly state that `.8` is diagnostic and does not claim
  the device-only file-picker issue is fixed.

## Device trace and routed-focus architecture — experimental.9

- The user installed `.8` and reported the same inability to select a trainer.
  Remote CEF inspection of the active `steamloopback.host/routes/apprunning`
  target found exactly one scoped event: `[TrainerRelay:picker] plugin-loaded`.
  There was no `ui-activated`, `handler-enter`, home RPC, or Decky API event.
  This localizes the failure before the button handler rather than inside
  `openFilePicker` or persistence.
- After the user explicitly requested a full UI audit, the official CheatDeck
  game-route architecture was compared across tags `v0.5.1`, `v1.0.0`,
  `v1.1.6`, `v1.2.1`, and `v2.0.0`. Every inspected release uses
  `SidebarNavigation`, then a page-level vertical `Focusable`, with the picker
  and other controls directly below it. `PanelSection` and `PanelSectionRow`
  are used by CheatDeck's Quick Access content, not its routed game pages.
- Trainer Relay had copied the picker control but not that surrounding routing
  contract: its game route rendered `RelayPage` directly and the page mixed
  Quick Access panel wrappers into the routed focus tree. This structural
  mismatch is the evidence-backed cause being addressed in `.9`.
- TDD RED added two architecture contracts: `PageRouter` must return a
  one-page `SidebarNavigation`, and the supported routed page must not contain
  `PanelSection` or `PanelSectionRow`. Both failed against the prior structure.
  GREEN refactored `PageRouter` and every `RelayPage` state to the CheatDeck
  hierarchy while leaving picker internals, Decky API calls, validation,
  persistence, backend/controller behavior, and diagnostic events unchanged.
- Focused result: 5/5 route/page tests passed. Fresh full gates reached 161/161
  Vitest tests across 20 files and 46/46 backend tests. Biome checked 50 files;
  both TypeScript typechecks, compileall, Rollup, and package layout 1/1 passed.
- Delivery version is `v0.1.0-experimental.9`. The 19-entry ZIP is 179,825
  bytes with SHA-256
  `B0D73E48543D03ED95B5C8AA192091A1E5410CB342CE1A726341E9312351F213`.
- Physical confirmation is still required: install `.9`, filter
  `[TrainerRelay:picker]`, press the folder button once, and confirm that
  `ui-activated`, `handler-enter`, `home-resolved`, and `api-call` appear and
  that the Decky browser becomes navigable. If `ui-activated` is still absent,
  collect the new trace and stop before another speculative UI patch.
- Final pre-publication rerun: Biome 50 files, production and test TypeScript,
  Vitest 161/161, backend unittest 46/46, compileall, Rollup, package layout
  1/1, and `git diff --check` all passed. The global `pnpm` launcher could not
  verify/download its pinned runtime because registry access was unavailable;
  the same frontend gates were therefore run through the already-installed
  project-local binaries. Two consecutive package runs produced the identical
  179,825-byte SHA-256 above.
- Runtime/docs commit `2135dd0` (`fix: match CheatDeck routed focus
  architecture`) was pushed to `origin/feat/trainer-relay` and `origin/main`.
  Tag `v0.1.0-experimental.9` points to that commit. Branch, main, and tag
  workflows passed (`33282002167`, `33282010962`, `33282033849`); the tag job
  published the prerelease and its `TrainerRelay.zip` asset.
- Release: https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.9
  Direct asset: https://github.com/matheussilva421/TrainerRelay/releases/download/v0.1.0-experimental.9/TrainerRelay.zip
  GitHub reports 179,825 bytes and digest
  `sha256:b0d73e48543d03ed95b5c8aa192091a1e5410cb342ce1a726341e9312351f213`;
  an independent download matched the local package exactly.
- User delivery kit created at
  `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.9-kit` with the
  official asset renamed to `TrainerRelay-v0.1.0-experimental.9.zip` and the
  Portuguese installation/testing/log guide. Physical Steam Deck validation
  remains the only unresolved gate.

## Disabled-control root cause — experimental.10

- The user installed `.9` and reported a narrower result: every control could
  receive visual focus, but pressing `A` activated nothing. This proves the
  routed focus tree is working and invalidates focus architecture as the
  remaining cause.
- The earlier device screenshot already showed `Legacy migration` as
  incomplete or unsafe. Code tracing found that `RelayPage` combined
  `model.migration.status !== "none"` into one `controlsDisabled` flag and
  passed it to the trainer picker, prefix editor, and enable toggle. SteamUI
  may visually focus a disabled `DialogButton`, but it does not invoke
  `onClick`; this exactly explains the absent `ui-activated` event.
- The fail-closed boundary was too broad. Selecting an absolute `.exe` is safe
  because `selectTrainerPath` always persists it with `enabled: false`, while
  `enableTrainerRelay` independently rejects every migration state other than
  `none`. Manual browsing and prefix editing therefore do not need to be
  disabled by legacy launch options; only enablement must remain blocked.
- TDD RED changed the view-model contract for both `ready` and `blocked`
  migration states and added a rendered-page test. Three assertions failed for
  the expected reason (`browse: false` and picker `disabled: true`). GREEN made
  supported browsing available, split configuration availability from
  enablement, and kept the toggle tied to `model.controls.enable`.
- Focused GREEN: 17/17 action/view/page tests. Fresh full results: Biome checked
  50 files, both TypeScript typechecks passed, Vitest passed 163/163 across 20
  files, backend unittest passed 46/46, and compileall plus Rollup passed.
- Delivery target is `v0.1.0-experimental.10`. The deterministic 19-entry ZIP
  is 179,747 bytes with SHA-256
  `1A29293153C6A5BDA47ADCC1877CFDF654DAA57685446B3B18CD31861992F864`.
  Physical validation is still required; no claim of a hardware fix should be
  made until the user presses `A` on `Choose trainer` in `.10`.
- Runtime/docs commit `bf6703f` (`fix: allow safe configuration during legacy
  migration`) was pushed to `origin/feat/trainer-relay` and `origin/main`.
  Branch and main workflows passed (`33283443497`, `33283443476`). Tag
  `v0.1.0-experimental.10` points to that commit; tag/release workflow
  `33283462760` passed and published the prerelease.
- Release: https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.10
  Direct asset: https://github.com/matheussilva421/TrainerRelay/releases/download/v0.1.0-experimental.10/TrainerRelay.zip
  The independently downloaded asset matched the local ZIP exactly at 179,747
  bytes and SHA-256
  `1A29293153C6A5BDA47ADCC1877CFDF654DAA57685446B3B18CD31861992F864`.
- User kit created at
  `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.10-kit` with the
  versioned official ZIP and updated Portuguese guide. Next action: install
  `.10`, open the same GOG shortcut, and press `A` on `Choose trainer`.

## Native action-row activation — experimental.11

- Physical validation of `.10` still reproduced the exact symptom: controls
  received visual focus, but pressing `A` did not reach
  `[TrainerRelay:picker] ui-activated` and no file browser opened.
- The previous tests mocked every `@decky/ui` component as a string and invoked
  `onClick` directly. They therefore bypassed SteamUI's activation contract and
  could stay green while Game Mode suppressed the action.
- The focused structural regression now requires one enabled native action
  row. Before the production change it failed 2/5: the picker still contained
  a disabled `TextField` and exposed no `ButtonItem` action. It intentionally
  does not claim to emulate SteamUI's physical gamepad event; the real-Deck
  check remains the acceptance gate.
- The minimal fix replaces the nested
  `Focusable -> Field -> Focusable -> disabled TextField + DialogButton`
  composition with one `ButtonItem`. The selected absolute path remains visible
  as its description; validation, Decky `openFilePicker`, persistence, backend,
  and fail-closed enablement are unchanged.
- Review fixes removed the unsupported-page GitHub control, preserved the
  ability to disable an already-enabled relay if legacy options reappear, and
  removed the trainer-output log sink. Trainer stdout/stderr now always use
  `DEVNULL` and `OwnedTrainerRunner` rejects the former `log_path` argument.
- Primary-source research is saved in
  `docs/research/2026-08-29-decky-game-mode-activation.md`. It confirms that
  focus and activation are separate in Decky UI and that `ButtonItem` is the
  official native action-row pattern; it also states that only the device can
  prove the final A-button behavior.
- Fresh local gates: Biome checked 50 files, both TypeScript typechecks passed,
  Vitest passed 165/165 across 20 files, backend unittest passed 47/47,
  compileall passed, Rollup built successfully, and the
  package-layout test passed 1/1.
- Delivery version is `v0.1.0-experimental.11`. The current deterministic
  19-entry ZIP is 176,965 bytes with SHA-256
  `5573EDB2E9AF27F51C320637ACCEC5A95C4F99519228FB8AE7EA678C67F99E0E`.
- Remote CEF verification could not be completed in this block: the existing
  DevTools target had no selected JavaScript context and
  `192.168.1.247:8081` stopped accepting connections. Do not claim a physical
  fix until `.11` is installed and pressing `A` emits `ui-activated` followed
  by `handler-enter` and opens Decky's browser.
- Pending: commit/push/tag/publish `.11`, independently verify the release asset, create
  the `.11` user kit, then run the physical GOG test followed by one Epic test.

### Experimental.11 publication checkpoint

- Runtime/research/release commit `e672c8f7529d2cda385b9ce1443a6bf0ddb4bc7f`
  was pushed to `origin/feat/trainer-relay` and `origin/main`.
- Tag `v0.1.0-experimental.11` points to that commit. Branch run
  `33285548694`, main run `33285560971`, and tag/release run `33285578347`
  all passed. The tag workflow published the prerelease and its installation
  asset.
- Release:
  `https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.11`.
  Direct asset:
  `https://github.com/matheussilva421/TrainerRelay/releases/download/v0.1.0-experimental.11/TrainerRelay.zip`.
- GitHub reports 176,965 bytes and digest
  `sha256:5573edb2e9af27f51c320637accec5a95c4f99519228fb8ae7ea678c67f99e0e`.
  A fresh independent download matched the local deterministic package
  byte-for-byte.
- User kit created at
  `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.11-kit` with
  `TrainerRelay-v0.1.0-experimental.11.zip` and the Portuguese `LEIA-ME.md`.
- Remaining acceptance gate: install `.11` on the physical Deck, open the same
  GOG shortcut, focus **Trainer executable**, press `A`, confirm
  `ui-activated -> handler-enter -> api-call` and navigate Decky's browser.
  Then finish the trainer launch/lifecycle checklist and repeat with one Epic
  shortcut. Do not promote to stable before both physical tests pass.

## Experimental.11 physical activation failure

- Physical photos on 2026-08-30 confirm that `.11` is installed for
  `gog:1482265568`: the new single `ButtonItem` row is visible with the text
  `Press A to browse the Deck...`.
- The row receives visual focus and SteamUI shows `A SELECT`, but pressing `A`
  still performs no action. This falsifies both the nested-picker hypothesis
  from `.10` and the claim that replacing it with `ButtonItem` alone repairs
  activation.
- `Save prefix` and `Enabled` are expected to remain disabled before a trainer
  path exists. The exact unresolved symptom is limited to the enabled
  `Trainer executable` action.
- The previous structural Vitest seam cannot reproduce or prove SteamUI's
  physical gamepad event. No `.12` production change should be made from that
  seam alone.
- The remote CEF endpoint `http://192.168.1.247:8081/json/list` was probed
  immediately after the report and refused the connection. The next required
  feedback loop is the live SharedJSContext with the Trainer Relay route left
  open, so the actual element props and A-button event path can be captured.
- Next action: enable Decky's remote CEF debugging until next boot, keep the
  same Trainer Relay screen open on the focused trainer row, and reconnect to
  port 8081. Do not publish another release before this trace identifies the
  boundary that suppresses activation.

### Remote CEF forwarding failure

- The user enabled Decky's remote CEF option and restarted Steam, while the
  Deck retained `192.168.1.247`. The host still answered ICMP, but TCP ports
  22, 8080, 8081, and 1337 were all closed from the development PC.
- This rules out a stale IP and confirms that Decky's remote toggle did not
  expose the local CEF endpoint on this installation.
- Official Decky discussion #860 records the same current failure: CEF remains
  bound to `127.0.0.1:8080` and must be forwarded manually to
  `0.0.0.0:8081` with `socat` for remote inspection:
  https://github.com/SteamDeckHomebrew/decky-loader/discussions/860
- Next action: from Desktop Mode, run a temporary foreground `socat` forward,
  reconnect to `http://192.168.1.247:8081`, and capture the live
  SharedJSContext event path. Keep this diagnostic bridge temporary and do not
  publish `.12` before the trace identifies the failing boundary.

### Live CEF root-cause trace

- Decky's normal remote port remained unavailable, so the user started a
  temporary user service forwarding local CEF `127.0.0.1:8080` to LAN port
  `18081` with `socat`. The host then connected successfully and enumerated
  the live Game Mode targets.
- The visible Trainer Relay UI is rendered in the main `Steam -- Big Picture`
  target, not in the empty `SharedJSContext` or `QuickAccess_uid2` documents.
  The current plugin execution target was
  `https://steamloopback.host/routes/trainer-relay/3535090580`.
- Live DOM and React-fiber inspection proved that the focused folder control is
  a real button, but its internal click value is removed because
  `TrainerFilePicker` receives `disabled=true`. The resulting button has the
  SteamUI `Disabled` class and no effective DOM `onClick`, which exactly
  explains focus plus `A SELECT` with no activation.
- The disabling input is not gamepad handling or legacy migration. Live
  `RelayPage` hooks showed `busy=false`, `migrationBusy=false`, and
  `configState.status="loading"`. The configuration load never transitions to
  `ready` or `error`, so every configuration control remains disabled without
  an explanatory message.
- Calling Decky's API-v2 transport directly from the plugin's
  `SharedJSContext` reproduced the backend fault: `get_relay_config` remained
  pending and the diagnostic `Promise.race` expired after five seconds. The
  API connection itself was present and reported version 2, so the unresolved
  boundary is the Trainer Relay Python process/socket response.
- Next action: capture the `plugin_loader.service` journal around Trainer Relay
  startup to obtain the Python traceback. Add a red backend/package regression
  for that exact failure, repair the process startup/RPC response, and add a
  frontend timeout/error-state regression so a future backend failure cannot
  leave a permanently disabled but apparently selectable UI. Do not publish
  `.12` before the real backend fix passes local gates and the same live RPC
  resolves on the Deck.

## Decky sandbox backend fix — experimental.12

- The physical Deck journal supplied the definitive startup traceback:
  `/home/deck/homebrew/plugins/TrainerRelay/main.py` failed at
  `from trainer_relay.config ...` with
  `ModuleNotFoundError: No module named 'trainer_relay'`.
- Root cause: the `.11` ZIP installed the Python package at
  `TrainerRelay/trainer_relay`, while Decky's sandbox adds only the plugin's
  `py_modules` directory to `sys.path`. The frontend loaded, but every RPC to
  the absent backend stayed pending, keeping `configState.status="loading"`
  and all configuration controls disabled.
- TDD packaging regression: the new test first failed against the old ZIP,
  both on the expected archive path and on an isolated import using only
  `TrainerRelay/py_modules`. The packager now writes the runtime package to
  `TrainerRelay/py_modules/trainer_relay`; both packaging tests pass.
- TDD frontend containment: an unresolved `get_relay_config` now transitions
  to the existing fail-closed error UI after five seconds. A late RPC response
  is ignored, and cleanup clears the timer. This does not hide backend failure
  or enable controls without configuration.
- Delivery version advanced to `v0.1.0-experimental.12`. The deterministic
  19-entry local ZIP is 177,892 bytes with SHA-256
  `695B53D47A2269CB29816F8CC8A77F22D1E7C04FD4C000FB21D87A8C5AB1B260`.
- Fresh local gates: backend unittest 47/47, compileall passed, Biome checked
  52 files, both TypeScript typechecks passed, Vitest 166/166 across 21 files,
  Rollup built, and package tests 2/2 passed. The environment's global `pnpm`
  shim hung, and the bundled fallback attempted an unnecessary noninteractive
  `node_modules` purge; the project-local binaries backing the same scripts
  were run directly and all passed.
- Pending: commit and push `.12`, publish and independently verify the release
  asset, create the user installation kit, then install it on the physical
  Deck. Acceptance requires a clean backend startup, a resolving
  `get_relay_config`, an enabled trainer action, and Decky's file browser
  opening with `A`. Trainer launch/lifecycle and one Epic title remain after
  the GOG selector check. Do not promote to stable yet.

### Experimental.12 publication checkpoint

- Fix commit `b6e9133f72b9466a35700e31b80a292b542df6ed` was pushed to
  `origin/feat/trainer-relay` and `origin/main`; tag
  `v0.1.0-experimental.12` points to that commit.
- Branch run `33306954118`, main run `33306963741`, and tag/release run
  `33306981842` all passed. The tag workflow published the prerelease and its
  installation asset.
- Release:
  `https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.12`.
  Direct asset:
  `https://github.com/matheussilva421/TrainerRelay/releases/download/v0.1.0-experimental.12/TrainerRelay.zip`.
- GitHub reports 177,892 bytes and digest
  `sha256:695b53d47a2269cb29816f8cc8a77f22d1e7c04fd4c000fb21d87a8c5ab1b260`.
  A fresh independent download matched the local deterministic ZIP exactly.
- Remaining acceptance gate: install `.12` on the physical Deck and confirm
  that the journal no longer contains the `trainer_relay` import error, the
  configuration RPC reaches `ready`, and pressing `A` opens the file browser.

### Experimental.12 physical picker and persistence PASS

- The user installed `.12` on the physical Steam Deck and successfully opened
  Decky's native file browser with `A`, navigated to a trainer, and selected it.
- Live CEF reconnected after the Steam reload to the new SharedJSContext target
  for `https://steamloopback.host/routes/trainer-relay/3535090580`. Filtering
  for Trainer Relay showed `selection-received` followed by
  `persistence-result`, with no filtered Trainer Relay error.
- A direct read-only Decky API-v2 verification completed without timeout:
  `get_relay_config` returned schema version 1 with one identity,
  `gog:1482265668`. Its trainer path is present and ends in
  `BioShock 2 Remastered v1.0-Update 2 Plus 15 Trainer.exe`; no prefix override
  is configured.
- `get_relay_status` returned `disabled` with `diagnostic: null`. This proves
  the `.11` backend-import/loading failure is repaired on the physical Deck and
  that picker persistence works. It does not yet prove trainer launch or
  in-game behavior.
- Next physical gate: turn **Enabled** on, launch the GOG shortcut, confirm the
  game starts before the trainer, then validate `waiting_for_game` to
  `launching` to `running`, one trainer instance, same-prefix behavior,
  selective shutdown, and failure/retry safety. One Epic title remains
  required afterward.

## Persistent diagnostic mode design approved

- With the GOG game physically open, four live API-v2 status samples remained
  `waiting_for_game` with no diagnostic. The game itself later opened, proving
  the current process discovery rejected every candidate without exposing
  which condition failed. The user cannot operate Konsole while the game is
  open, so an in-plugin diagnostic path is required.
- The user approved a persistent diagnostic mode that stays enabled until
  manually disabled, stores a circular maximum of 50 MB, exports a timestamped
  TXT automatically to `/home/deck/Downloads`, and offers confirmed clearing.
- Approved technical values include expected/observed executable, trainer,
  prefix, `umu-run`, `GAMEID`, `STORE`, `WINEPREFIX`, and `PROTONPATH`.
  Complete environments, command lines, credentials, tokens, cookies,
  authorization data, and trainer stdout/stderr remain prohibited.
- The approved UI uses a separate **Diagnostics** page with the latest 20
  events, persistent toggle, byte use, live updates, export, clear, and last
  export path. SharedJSContext forwards sanitized events to DevTools with the
  `[TrainerRelay:diagnostic]` prefix.
- Full architecture, RPC contracts, rotation, redaction, candidate-decision
  model, failure isolation, TDD strategy, and physical gates are recorded in
  `docs/superpowers/specs/2026-08-30-trainer-relay-diagnostic-mode-design.md`.
- Delivery target is `v0.1.0-experimental.13`. Next action: obtain approval of
  the written specification, then create the detailed TDD implementation plan.
  No production implementation has started.

### Persistent diagnostic mode implementation plan

- The user approved the written design and explicitly authorized
  implementation.
- The detailed ten-task TDD plan is saved at
  `docs/superpowers/plans/2026-08-30-trainer-relay-diagnostic-mode-implementation-plan.md`.
- Tasks cover persistent settings; sanitized journal and exact 50 MiB rotation;
  cursor/export/clear/failure isolation; structured `/proc` decisions;
  watcher/UMU/trainer events; backend RPC wiring; TypeScript contracts; the
  persistent DevTools bridge; the separate Diagnostics page; privacy,
  packaging, documentation, and `v0.1.0-experimental.13` delivery.
- The plan was checked against the design for scope, placeholders, and type
  consistency. Integration privacy testing was moved before watcher event
  implementation so it participates in a genuine RED/GREEN cycle.
- Next action: commit and push the plan checkpoint, then execute Task 1 through
  Task 10 inline with focused RED/GREEN evidence and small commits.

### Persistent diagnostics backend Tasks 1-5

- Implemented and committed persistent `DiagnosticSettingsV1`, defaulting to
  disabled and rejecting malformed persisted values.
- Added a privacy-bounded diagnostic recorder with exact event schemas,
  sequence/timestamp/session correlation, repeat consolidation, five rotating
  10 MiB NDJSON files, malformed-line recovery, opaque cursors, generation
  reset on clear, and disk-failure isolation from the watcher.
- Added deterministic UTF-8 TXT export through an fsynced temporary file and
  atomic rename. Exports use timestamp collision suffixes, remain outside the
  50 MiB journal, and are not removed by journal clearing.
- Refactored `/proc` discovery into fail-closed `CandidateDecision` results.
  Relevant processes now report bounded reasons for recycled PID, missing
  environment anchors, `GAMEID`, store, prefix, executable, and legacy launch
  settings without copying full environment or command line data.
- Wired sanitized games-map, process, UMU, spawn, running, exit, retry,
  session-change/end, SIGTERM, and SIGKILL events into `RelayWatcher`.
  `OwnedTrainerRunner.stop()` now returns whether escalation was required, and
  UMU resolution reports whether its unambiguous path came from the bundle or
  `PATH` while preserving the old path-only API.
- Privacy integration coverage proves a prefix rejection reaches cursor and
  TXT export with identity, PID/start time, and approved paths while excluding
  a seeded token, legacy command content, full argv, and unrelated process
  path. Current backend gate: 78/78 tests passed; compileall passed.
- Commits: `a2dbfc4`, `95f9ea8`, `b6ff587`, `d52199a`, and `62f8f3c`.
- Next action: Task 6, expose the recorder through strict Decky RPCs and make
  `main.py` own one shared recorder for watcher/RPC lifecycle.

### Experimental.13 persistent diagnostics local release candidate

- Completed Tasks 6-9: one recorder is shared by Decky lifecycle, watcher, and
  five strict RPCs; TypeScript decoders reject malformed/unsafe responses;
  SharedJSContext streams sanitized events under
  `[TrainerRelay:diagnostic]` with bound browser timers and bounded backoff;
  and a global **Diagnostics** page provides the persistent toggle, latest 20
  events, 50 MiB usage, TXT export, and confirmed journal-only clearing.
- Final review found and fixed two pre-release issues with new red/green tests:
  arbitrary `trainer_...` exception text can no longer become a logged/status
  code, and one-second statistics polling no longer rereads up to 50 MiB of
  journal contents. Stats now use incremental counts and only `stat()` the five
  journal files.
- Privacy integration still passes: allowed identity/session/prefix anchors
  reach cursor and TXT while seeded token, legacy debug command, full argv,
  and unrelated process path remain absent.
- Fresh local gates: backend 86/86; compileall passed; Biome checked 63 files;
  both TypeScript typechecks passed; frontend 185/185 in 25 files; Rollup
  passed; package layout/import 2/2.
- Deterministic `TrainerRelay.zip`: 21 entries, 253,404 bytes, SHA-256
  `BFA2EEF6EC96A0F4A97EBC995C142617D08C83DF488F5EB8E88F5B2F2619D481`.
  It contains both `py_modules/trainer_relay/diagnostics.py` and
  `diagnostic_settings.py` and excludes tests, maps, caches, logs, and
  `node_modules`.
- Version is `0.1.0-experimental.13` in package metadata and the fixed Python
  runtime constant. README, Portuguese installation/log guide, and physical
  validation checklist document persistence, 50 MiB rotation, allowed and
  prohibited data, DevTools filter, TXT export, and clear scope.
- Pending before delivery: commit this release candidate, push branch/main,
  tag and publish `.13`, verify CI and asset bytes, create the Downloads kit,
  then install on the physical Deck. GOG and Epic trainer behavior remain
  physical gates; do not promote to stable.

### Experimental.13 publication and user kit checkpoint

- Release candidate commit `abb8f53e23636199bb7bfd94af5c38249aac9bce`
  was pushed to `feat/trainer-relay` and `main`; tag
  `v0.1.0-experimental.13` points to it.
- GitHub Actions passed for the feature branch (`33310698181`), main
  (`33310699929`), and tag/release (`33310716123`).
- Prerelease:
  `https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.13`.
  Direct asset:
  `https://github.com/matheussilva421/TrainerRelay/releases/download/v0.1.0-experimental.13/TrainerRelay.zip`.
- The published asset is 253,404 bytes with SHA-256
  `BFA2EEF6EC96A0F4A97EBC995C142617D08C83DF488F5EB8E88F5B2F2619D481`.
  A fresh independent download matched the regenerated local deterministic
  ZIP byte-for-byte.
- Created the final delivery kit at
  `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.13-kit` with the
  versioned ZIP, Portuguese installation/log guide, Steam Deck validation
  checklist, `LEIA-ME.txt`, and `SHA256SUMS.txt`. The copied ZIP retained the
  expected size and SHA-256.
- Final post-publication gates on the tagged tree: backend 86/86; compileall;
  Biome 63 files; both TypeScript typechecks; frontend 185/185 in 25 files;
  Rollup build; package layout/import 2/2. The PowerShell `pnpm` wrapper waited
  on PTY input, so the same project-local Biome, TypeScript, Vitest, and Rollup
  binaries were executed directly and passed.
- Remaining product acceptance is physical only: install `.13`, leave
  diagnostics enabled, reproduce one GOG and one Epic session, export the TXT,
  and confirm trainer launch, one-instance behavior, retry safety, and
  selective shutdown. Keep the release experimental until both titles pass.

### Experimental.14 UniFiDeck `umu-0` process-discovery fix

- The physical GOG diagnostic export contained 5,322 events. No candidate was
  accepted; 3,920 rejections were `game_id_mismatch`. Stable Wine children had
  the correct GOG store and per-game prefix but UniFiDeck intentionally set
  `GAMEID=umu-0` because the title has no per-game UMU database identifier.
- A shallow read-only UniFiDeck `staging` clone at commit `cb2eeaa` confirmed
  `_build_umu_env()` uses `env["GAMEID"] = umu_id or "umu-0"` while pinning
  the real game identity through the per-game `WINEPREFIX`. The previous relay
  incorrectly treated the UMU database ID as the GOG/Epic shortcut ID.
- TDD regression fixtures reproduce the observed wrappers, Wine helpers, and
  real `X:\\Games\\...\\Bioshock2HD.exe` process. RED rejected all candidates;
  GREEN accepts only the real PID after resolving the Wine drive through the
  prefix `dosdevices` symlink and requiring the Linux process name, full
  resolved executable, store, prefix, and stable PID/start time to agree.
- Linux `/proc/<pid>/comm` truncation is accepted only for an ASCII expected
  basename whose first 15 characters match, and only together with a complete
  executable-path match. Multiple real matches remain `ambiguous`; helpers and
  wrappers become `process_name_mismatch` and never launch a trainer.
- `GAMEID` remains required and is preserved for the trainer's UMU environment,
  but it is no longer compared with the shortcut identity. Diagnostics now
  include the bounded `process_name` field and
  `process_name_mismatch_count`; complete command lines and environments remain
  prohibited.
- Upstream CheatDeck `main` was inspected before release. It performs no PID or
  executable discovery: it writes `PROTON_REMOTE_DEBUG_CMD` and
  `PRESSURE_VESSEL_FILESYSTEMS_RW` into Steam launch options and relies on
  Proton's direct sidecar hook. That design cannot identify a process behind
  UniFiDeck's nested native launcher, so no CheatDeck process-matching code was
  available to reuse.
- Fresh local gates: backend 88/88; compileall passed; Biome checked 63 files;
  both TypeScript typechecks passed; frontend 185/185 in 25 files; Rollup
  passed; package layout/import 2/2. The global PowerShell `pnpm` wrapper again
  waited indefinitely, so project-local binaries were used successfully.
- Deterministic `.14` candidate: 21 stored entries, 255,508 bytes, SHA-256
  `5A3EFB2E7C81DF5A4F166AC21B14193C81A50665BF72AB24325176FC831FE337`.
  Two independent local package generations matched byte-for-byte.
- Current files changed: `trainer_relay/process.py`, diagnostics/watcher RPC
  allowlists, backend regression/integration tests, package version, README,
  Portuguese guide, validation checklist, package test, and this handoff.
- Pending: review the complete diff, commit and push `feat/trainer-relay`, merge
  or fast-forward `main` following the established release flow, tag/publish
  `v0.1.0-experimental.14`, verify CI and published asset hash, create the
  versioned user kit, then physically verify trainer launch and selective
  shutdown on the same BioShock 2 GOG shortcut. Epic remains a separate gate;
  do not promote stable.

### Experimental.14 publication and user kit checkpoint

- Runtime fix commit `a3de376` and release preparation commit `1cf1773` were
  pushed to both `feat/trainer-relay` and `main`. Annotated tag
  `v0.1.0-experimental.14` points to `1cf1773`.
- GitHub Actions passed for the feature branch (`33322747421`), main
  (`33322749027`), and tag/release (`33322777087`). The tag run completed all
  backend, frontend, package, and publish jobs. Its only annotation is the
  upstream Node 20 deprecation notice for `actions/setup-python@v5`; it did not
  affect the successful result.
- Prerelease:
  `https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.14`.
  Direct asset:
  `https://github.com/matheussilva421/TrainerRelay/releases/download/v0.1.0-experimental.14/TrainerRelay.zip`.
- The published 255,508-byte asset has SHA-256
  `5A3EFB2E7C81DF5A4F166AC21B14193C81A50665BF72AB24325176FC831FE337`
  and matches the fresh local deterministic package byte-for-byte.
- Created `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.14-kit`
  with the versioned published ZIP, Portuguese guide, validation checklist,
  concise `LEIA-ME.txt`, and `SHA256SUMS.txt`.
- Two independent review subagents failed to return a report and were stopped
  without write access. A manual fail-closed review plus fresh committed-tree
  gates found no release blocker. No claim of physical trainer success is made.
- Next action: install `.14` over the existing plugin, keep diagnostics enabled,
  start the same BioShock 2 GOG shortcut, wait for the trainer, and export a new
  TXT whether it succeeds or fails. Confirm the trainer exits with the game and
  that retry/failure never terminates the game. Epic validation remains pending.

### Experimental.15 mutable-main-thread session revalidation

- The physical `.14` export
  `TrainerRelay-diagnostics-20260830-164555.txt` established the exact failure
  sequence. PID `57719`, start time `2457048`, executable
  `Bioshock2HD.exe`, GOG store, UniFiDeck prefix, and required environment were
  accepted twice. The trainer was spawned as owned group `57748`.
- Two seconds later the same PID/start-time pair and every stable anchor were
  unchanged, but `/proc/57719/comm` became `Main Game Threa`. The watcher
  rejected it as `process_name_mismatch`, emitted `session_ended`, and sent
  `SIGTERM` to the trainer group before the three-second running gate. The
  same game PID persisted with the renamed thread for almost two further
  minutes, disproving game exit and PID reuse.
- TDD RED reproduced both missing contracts: `ProcessDiscoverer.discover()`
  could not accept an expected session, and `RelayWatcher` passed no existing
  session on later scans. GREEN adds an optional exact `expected_session`.
  Only that PID/start-time pair may bypass a changed `comm`; full executable,
  prefix, store, required environment, stable double-stat read, and legacy
  checks still run. New PIDs and recycled start times remain strict.
- A real fake-`/proc` watcher integration now covers acquisition, trainer
  spawn, main-thread rename, revalidation, and transition to `running` without
  `session_ended` or an owned-group stop. Additional tests cover an unrelated
  pinned session and a recycled PID.
- Diagnostics now emits privacy-bounded `candidate_revalidated` events. The
  Python journal and TypeScript RPC decoder share the same allowlisted fields;
  full command lines and environments remain prohibited.
- Primary-source findings are recorded in
  `docs/research/2026-08-30-trainer-relay-runtime-contracts.md`. Linux documents
  `comm` as thread-mutable and 15-character-truncated; UniFiDeck documents that
  UMU wrappers inherit `WINEPREFIX`; UMU and Proton/GE document
  `runinprefix` for additional executables in an active prefix.
- Version advanced to `0.1.0-experimental.15`. Fresh local gates: backend
  94/94; compileall passed; Biome checked 63 files; both TypeScript typechecks
  passed; frontend 186/186 in 25 files; Rollup built; package layout/import
  2/2.
- Deterministic `.15` candidate: 21 stored entries, 257,815 bytes, SHA-256
  `569CD7A42E5B781529E39AF26AC1A464AEB811A4BD59E152FADFACADEFCD077E`.
  Two independent package generations matched byte-for-byte.
- Pending: inspect the final diff, commit and push `feat/trainer-relay`, update
  `main`, publish and verify `v0.1.0-experimental.15`, create the user kit, and
  then install it on the physical Deck. The required physical GOG result is a
  `candidate_revalidated` event followed by `trainer_running`, with no early
  `session_ended`/`owned_group_signal`. Epic remains a separate gate; do not
  promote stable.

### Experimental.15 publication and user kit checkpoint

- Runtime fix commit `715ebc9` and release preparation commit `597c2eb` were
  pushed to both `feat/trainer-relay` and `main`. Annotated tag
  `v0.1.0-experimental.15` points to `597c2eb`.
- GitHub Actions passed for the feature branch (`33325317711`), main
  (`33325317839`), and tag/release (`33325348759`). The tag run built and
  published the Decky asset successfully.
- Prerelease:
  `https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.15`.
  Direct asset:
  `https://github.com/matheussilva421/TrainerRelay/releases/download/v0.1.0-experimental.15/TrainerRelay.zip`.
- The published 257,815-byte asset has SHA-256
  `569CD7A42E5B781529E39AF26AC1A464AEB811A4BD59E152FADFACADEFCD077E`
  and matches the fresh local deterministic package byte-for-byte.
- Created `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.15-kit`
  with the versioned ZIP, Portuguese guide, validation checklist,
  `LEIA-ME.txt`, and `SHA256SUMS.txt`.
- No physical PASS is claimed yet. Install `.15` over the current plugin, keep
  Diagnostics enabled, launch the same BioShock 2 GOG shortcut, wait at least
  five seconds after the game appears, and export a new TXT. The expected
  sequence is `candidate_revalidated` followed by `trainer_running`, without
  premature `session_ended`/`owned_group_signal`. Confirm selective shutdown
  when the game closes. Epic remains a separate gate; do not promote stable.

### Experimental.16 UMU launch-boundary correction

- The physical `.15` exports
  `TrainerRelay-diagnostics-20260830-175619.txt` and
  `TrainerRelay-diagnostics-20260830-175636.txt` describe the same run. They
  confirm that `.15` fixed session retention: game PID `59645`, start time
  `2879747`, executable path, GOG identity, and prefix were retained through
  121 `candidate_revalidated` events until the real `session_ended` more than
  two minutes later.
- The trainer's owned UMU group `59674` exited with code `1` after 3,248 ms and
  never reached `trainer_running`. The game stayed alive, so this is a
  sidecar-launch failure, not game discovery or game termination.
- The captured Proton descendant exposed
  `WINEPREFIX=/home/deck/.local/share/unifideck/prefixes/1482265668/pfx/`.
  UniFiDeck instead launches UMU with both `WINEPREFIX` and
  `STEAM_COMPAT_DATA_PATH` set to the parent compatdata root. Replaying the
  descendant value can make a new UMU invocation treat `pfx` as its root.
- UniFiDeck also explicitly removes `STEAM_COMPAT_CLIENT_INSTALL_PATH` before
  invoking UMU because UMU derives it; replaying the child value can pin a
  symlinked Steam root and fail inside pressure-vessel. Trainer Relay now omits
  it as well.
- TDD regressions cover the transformed child prefix, an explicit override
  ending in `pfx`, a default game ID literally named `pfx`, the effective
  sanitized spawn diagnostic, and exclusion of the UMU-derived client path.
  The sidecar now launches with equal root `WINEPREFIX` and
  `STEAM_COMPAT_DATA_PATH`, with `PROTON_VERB=runinprefix` assigned last.
- Retry is now based on the state observed by the watcher. A first process that
  exits before `trainer_running` receives the one automatic retry even if the
  next one-second poll observes the exit just after three seconds. A process
  previously observed running still fails without an automatic relaunch.
- Version advanced to `0.1.0-experimental.16`. Current gates: backend 103/103;
  targeted compileall passed; Biome checked 63 files; both TypeScript
  typechecks passed; frontend 187/187 in 25 files. The global `pnpm` shim hung
  without output even for `pnpm --version`; the same project-local Biome, tsc,
  and Vitest binaries completed successfully. Rollup built, package layout and
  isolated installed import passed 2/2. Two independent package generations
  produced identical 21-entry, ZIP_STORED archives: 261,236 bytes, SHA-256
  `DB88075B7D3A00B9077775A349B3D0632C5CE3FBAE39E0900FADB6FCA491CBCE`.
  Final review, commit, push, tag/release verification, user kit, and physical
  GOG validation are still pending.
- The next physical diagnostic must show `trainer_spawned` with equal
  `wineprefix` and `steam_compat_data_path` values ending in
  `/prefixes/1482265668` (not `/pfx`) plus `proton_verb=runinprefix`. Success is
  still `trainer_running`. If the first attempt exits before that state, the
  journal must show one `trainer_retry_scheduled` and a second
  `trainer_spawned`. Do not promote stable until GOG and Epic pass physically.
- Two-axis read-only review against `v0.1.0-experimental.15` found no hard
  standards violation and no scope creep. Standards reported one judgement-call
  duplication between prefix normalization at the watcher boundary and the
  environment builder; it remains intentionally local so the environment
  builder is safe when called independently.
- Spec review correctly found that the ignored root `TrainerRelay.zip` still
  contained `.15`. It was rebuilt and now matches the deterministic `.16`
  candidate: 261,236 bytes and SHA-256
  `DB88075B7D3A00B9077775A349B3D0632C5CE3FBAE39E0900FADB6FCA491CBCE`.
  Its broader allowlist concern does not contradict the written requirement,
  which explicitly permits necessary variables *and categories*; the named
  categories remain bounded by secret filtering and explicit removals. Existing
  `test_runner.py`, watcher, fake-`/proc`, and diagnostic integration tests cover
  structured argv, environment handoff, new-session ownership, selective group
  shutdown, and privacy. No production change was made for those two findings.

### Experimental.16 publication and user kit checkpoint

- Runtime commit `ea52795` and release commit `9ca7f8b` were pushed to both
  `feat/trainer-relay` and `main`. Annotated tag
  `v0.1.0-experimental.16` points to `9ca7f8b`.
- GitHub Actions passed for the feature branch (`33328679987`), main
  (`33328680258`), and tag/release (`33328693883`). The tag workflow published
  the Decky asset successfully.
- Prerelease:
  `https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.16`.
  Direct asset:
  `https://github.com/matheussilva421/TrainerRelay/releases/download/v0.1.0-experimental.16/TrainerRelay.zip`.
- The public asset is 261,236 bytes with SHA-256
  `DB88075B7D3A00B9077775A349B3D0632C5CE3FBAE39E0900FADB6FCA491CBCE`
  and matches the freshly rebuilt local package byte-for-byte.
- Created `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.16-kit`
  with the versioned published ZIP, Portuguese guide, validation checklist,
  README, `LEIA-ME.txt`, and `SHA256SUMS.txt`; the kit copy has the same hash.
- Local committed-tree gates passed: backend 103/103; compileall; Biome 63
  files; two TypeScript typechecks; frontend 187/187 in 25 files; Rollup;
  package layout/import 2/2; deterministic ZIP. The global `pnpm` shim remained
  hung without output, so the equivalent project-local executables were used;
  all Linux CI workflows using pnpm passed independently.
- Physical validation remains pending. Install `.16`, keep Diagnostics enabled,
  test the same BioShock 2 GOG shortcut, and export a TXT after the game/trainer
  attempt. GOG and Epic must both pass before stable promotion.

### Experimental.16 physical GOG result — UMU exits before trainer running

- `TrainerRelay-diagnostics-20260830-205118.txt` confirms the Deck installed
  plugin version `0.1.0-experimental.16`. The real BioShock process was accepted
  as PID `61566`, start time `3930176`, and retained through 119
  `candidate_revalidated` events until the actual game session ended.
- `.16` reconstructed the intended UMU boundary correctly on both attempts:
  `WINEPREFIX` and `STEAM_COMPAT_DATA_PATH` were equal to
  `/home/deck/.local/share/unifideck/prefixes/1482265668`, without `/pfx`, and
  `PROTON_VERB=runinprefix`. The bundled UniFiDeck `umu-run` was resolved.
- First owned group `61580` exited code `1` after 3,218 ms. The new retry rule
  scheduled exactly one retry after two seconds. Second owned group `61685`
  exited code `1` after 3,171 ms. Neither attempt emitted `trainer_running`.
  No `owned_group_signal` was sent and the game remained active for more than
  two additional minutes. Therefore session retention, prefix reconstruction,
  retry cardinality, and game isolation passed; trainer launch failed.
- Strongest next hypothesis: Trainer Relay still copies the game's
  `STEAM_COMPAT_INSTALL_PATH`. UniFiDeck sets it to the game work directory,
  while the selected FLiNG executable is under `/home/deck/Games/Trainers`.
  Current UMU preserves a supplied nonempty install path and only derives the
  executable parent when it is absent. A new pressure-vessel invocation may
  therefore lack the correct trainer-side mount/path context and exit before
  Wine keeps the trainer alive.
- Next correction must be TDD-first: rebuild
  `STEAM_COMPAT_INSTALL_PATH` from the trainer executable's parent (or omit it
  so UMU derives that parent), expose the effective value in the bounded
  `trainer_spawned` diagnostic, retain `PROTON_VERB` assignment last, and add
  regressions for trainers outside the game directory. Do not claim this
  hypothesis proven until a new physical export reaches `trainer_running`.
- No runtime source was changed in this diagnostic turn. Physical GOG status is
  FAIL for trainer startup but PASS for leaving the game intact. Epic remains
  untested and stable promotion remains blocked.

### Systematic-debugging checkpoint — install-path A/B required

- A deterministic local contract probe reproduced the suspect boundary: for a
  trainer under `/home/deck/Games/Trainers`, the current environment builder
  preserves `STEAM_COMPAT_INSTALL_PATH=/home/deck/Games/BioShock 2
  Remastered/Build/Final` from the game. The probe reports `CONTRACT_RED=True`.
  Existing environment tests remain green because none relates the selected
  trainer parent to the effective install path; this is a coverage gap, not yet
  proof that the mismatch caused UMU exit code `1` on the Deck.
- Ranked hypotheses after the `.16` trace and current UMU source inspection:
  (1) the inherited game install path gives the fresh pressure-vessel launch
  the wrong executable-side path context; (2) another copied Proton/UMU value
  differs from the running game's configuration; (3) this FLiNG executable
  exits under the selected GE-Proton regardless of the mount; (4) a generic
  second UMU invocation cannot join this live prefix/runtime combination.
- Before changing production code, run a reversible one-variable physical A/B:
  copy (do not move) the same trainer beside `Bioshock2HD.exe` under the game's
  `Build/Final` directory, select that copy in Trainer Relay, launch the same
  shortcut, and export diagnostics. If the same binary remains active or emits
  `trainer_running`, hypothesis 1 is strongly supported. If it still exits code
  `1`, do not implement the install-path rewrite as a claimed fix; instrument
  bounded UMU stderr and compare the effective environment next.
- No `.17` build or runtime edit is authorized by this checkpoint. The invoked
  diagnosis skills require the physical A/B or equivalent captured evidence
  before proceeding to a TDD fix.

### Physical install-path A/B — hypothesis refuted

- `TrainerRelay-diagnostics-20260830-211159.txt` used plugin `.16` and the same
  FLiNG trainer copied beside `Bioshock2HD.exe` in the game's `Build/Final`
  directory. The real game session was accepted as PID `75175`, start time
  `4053062`, and remained valid through 134 `candidate_revalidated` events.
- First owned trainer group `75202` exited code `1` after 2,134 ms. The single
  automatic retry launched group `75520`, which exited code `1` after 3,207
  ms. There was no `trainer_running`; the game session remained intact until
  `session_ended` at 21:11:51 UTC.
- Because the same executable failed identically after moving inside the game
  install directory, the inherited `STEAM_COMPAT_INSTALL_PATH` mismatch is not
  the primary cause. Do not ship the previously proposed install-path rewrite
  as a claimed fix.
- Remaining ranked causes are: an incompatible copied Proton/Steam variable; a
  need to re-enter the existing UMU container; a FLiNG/GE-Proton-specific
  startup failure; or an untracked child process after the UMU parent exits.
  The `.16` export cannot distinguish them because it intentionally excludes
  trainer/UMU stdout and stderr.
- Proposed bounded diagnostic change, awaiting explicit approval: continuously
  drain UMU stdout/stderr to prevent pipe blocking while retaining only a small
  sanitized tail; record bounded byte counts, redacted tail/classification, and
  process-group member metadata when the UMU parent exits. Apply TDD first and
  do not change prefix, environment, retry, or launch behavior in that build.

### Experimental.17 same-container re-entry implementation

- The user explicitly approved the diagnostic and runtime correction after the
  `.16` A/B refuted trainer location. Primary-source analysis of UniFiDeck's
  bundled UMU 1.4.4 identified its supported `UMU_CONTAINER_NSENTER=1` path:
  the initial game container exposes a prefix-keyed launcher service and a
  later invocation can use `steam-runtime-launch-client` with
  `PROTON_VERB=runinprefix`.
- The source-preserving launch-option flow now adds exactly one
  `UMU_CONTAINER_NSENTER=1` after explicit confirmation and AppDetails
  verification. Plain `gog:<id>`/`epic:<id>` shortcuts are converted to an
  explicit `%command%` form; legacy CheatDeck variables are the only values
  removed. The relay remains disabled until verification succeeds and a game
  already running must be restarted.
- Process discovery rejects an otherwise matching game whose inherited flag is
  missing. Before spawn, `ContainerReentryProbe` resolves the runtime from the
  active Proton `toolmanifest.vdf`, mirrors UMU's `UMU_FOLDERS_PATH` then
  `XDG_DATA_HOME` location precedence, computes the exact MD5 prefix bus, and
  requires `steam-runtime-launch-client --list` to contain that bus. Missing,
  unsupported, or failed probes launch no trainer and leave the game intact.
- The sidecar still uses structured argv and its owned process group. It removes
  stale `STEAM_COMPAT_LAUNCHER_SERVICE`, forces re-entry, and assigns
  `PROTON_VERB=runinprefix` last. Diagnostic mode uses `UMU_LOG=info`, captures
  continuously drained 4 KiB tails, stores at most 1,024 sanitized characters
  per stream after exit, and records bounded group/descendant names. Common
  token/password/cookie/authorization/credential/API-key/access-key/private-key
  forms and credential-bearing URLs are redacted.
- Version is `0.1.0-experimental.17`. Fresh local gates: backend 124/124;
  compileall passed; frontend 191/191 in 25 files; Biome checked 63 files; both
  TypeScript typechecks passed; Rollup built; package layout/import 2/2. The
  global pnpm version switch could not verify the registry signature in the
  restricted environment, so the same project-local scripts ran through npm.
- Three independently generated ZIP_STORED archives match byte-for-byte: 22
  entries, 285,075 bytes, SHA-256
  `9516DA7AB6ECC92448F21C785D136EE7A4E53B2F74355194ABD227E1BE8CC095`.
  Two independent read-only reviewer attempts stalled without a report and
  were shut down. The main-agent two-axis review found and fixed two concrete
  issues before commit: UMU runtime-root precedence/relative-path ambiguity and
  an overstrong documentation claim about inherited stdout/stderr. Commit/push,
  tag/release, public asset comparison, kit creation, and physical GOG/Epic
  validation remain pending at this checkpoint.

### Experimental.17 publication and installation kit

- Commit `7a1e593` (`fix: re-enter active UMU container`) was pushed to both
  `feat/trainer-relay` and `main`. Annotated tag
  `v0.1.0-experimental.17` points to the same commit.
- GitHub Actions passed for the feature branch (`33340211504`), main
  (`33340225388`), and tag/release (`33340251841`). The tag workflow completed
  frontend, backend, package-layout/build, and release publication jobs.
- Prerelease:
  `https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.17`.
  Direct asset:
  `https://github.com/matheussilva421/TrainerRelay/releases/download/v0.1.0-experimental.17/TrainerRelay.zip`.
- The public asset is 285,075 bytes with SHA-256
  `9516DA7AB6ECC92448F21C785D136EE7A4E53B2F74355194ABD227E1BE8CC095`.
  Its bytes exactly match the final local deterministic package.
- Created and verified
  `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.17-kit` with
  the versioned public ZIP, Portuguese guide, validation checklist, README,
  context, `LEIA-ME.txt`, and `SHA256SUMS.txt`. The kit ZIP and copied guide
  match their sources byte-for-byte.
- Physical validation remains the only blocker. Install `.17`, select the
  trainer, confirm **Prepare UMU container re-entry**, close/relaunch the GOG
  game, and export a TXT. Expected order:
  `container_reentry_verified`, `trainer_spawned`, `trainer_running`. If the
  preflight fails, send the bounded `container_reentry_*` code and TXT; no
  trainer should have been launched. Epic remains a separate gate and stable
  promotion remains prohibited until both stores pass.

### Experimental.17 physical GOG preflight failure

- `TrainerRelay-diagnostics-20260830-233641.txt` confirms the physical Deck
  installed `0.1.0-experimental.17`. The real BioShock process was accepted as
  PID `79033`, start time `4885149`, with the expected executable, GOG store,
  GE-Proton 11-6, compatdata root, and inherited re-entry flag.
- A deterministic replay check over the captured export is red for the exact
  symptom: 462 accepted/revalidated observations, 462
  `container_reentry_probe_failed` rejections, zero `trainer_spawned`, and zero
  `trainer_running`. The game stayed isolated and eventually emitted
  `session_ended`.
- Failure occurs before runner spawn. `steam-runtime-launch-client --list`
  returns nonzero in about 10 ms, but `.17` discards its return code, bounded
  stderr, and D-Bus source classification. The watcher then repeats the same
  preflight once per second for the unchanged session, producing 7.5 MiB of
  diagnostics in about eight minutes.
- Root boundary: the preflight is a host-side D-Bus control operation, while
  `.17` executes it with the sanitized environment copied from a Windows
  descendant inside pressure-vessel. Decky runs this non-root plugin as the
  host user, so escalating the plugin is neither necessary nor an appropriate
  correction. The probe must resolve a host-visible user-session bus
  independently of game-runtime variables and pass the same resolved context
  to the later UMU invocation.
- Proposed bounded correction, awaiting the post-diagnosis approval gate:
  resolve and validate host D-Bus candidates fail-closed; accept only the
  candidate whose `--list` output contains the exact prefix bus; return that
  context to the sidecar environment; preserve structured argv and ownership;
  record bounded probe return code/error classification; and latch an invalid
  preflight for the same PID/start-time until manual retry or a new session.
- TDD seams: a game-internal/unreachable bus plus a valid host bus must select
  the host context; zero valid buses must remain fail-closed with sanitized
  evidence; a successful resolution must reach the runner with the selected
  D-Bus context; and an unchanged invalid session must execute one preflight,
  not one per watcher tick. No production file was changed in this diagnostic
  checkpoint.

### Experimental.18 host-session D-Bus correction

- The user explicitly approved extensive analysis and correction after the
  `.17` GOG export. The 6,214,132-byte source report reproduced the exact
  boundary: stable session PID `79033` plus start time `4885149`, repeated
  `container_reentry_probe_failed`, and no `trainer_spawned`.
- Primary-source research is recorded in
  `docs/research/2026-08-30-trainer-relay-dbus-host-context.md`. Decky with
  `flags=[]` drops the backend to `HOST_USER`; UMU 1.4.4 invokes
  `steam-runtime-launch-client --list` in its current process environment and
  silently falls back to an independent launch when the exact prefix service
  is absent. Trainer Relay must therefore enforce its own host-session
  preflight and fail closed.
- TDD corrections now isolate the control operation from the Wine descendant:
  use Decky's host-user home, build a bounded host D-Bus/XDG pair, require the
  exact MD5 prefix service, forward only the verified immutable pair to UMU,
  and restore `PROTON_VERB=runinprefix` as the final assignment. The game
  process's nested D-Bus/XDG values are never reused.
- A rejected preflight is latched to the stable PID/start-time pair. The same
  session no longer probes once per watcher tick; explicit Retry performs one
  new bounded preflight, and a new game session clears the latch. The global
  cap is five launch-client invocations across all candidates, not five rounds
  per candidate.
- Bounded diagnostics add failure class, launch-client exit code, bus-source
  category, and invocation count. Raw D-Bus addresses, stderr, and complete
  environments are not retained. Failure-class priority prevents a specific
  permission/timeout result from being overwritten by a later generic error.
- Two-axis review found and this block corrected: wrong Decky/root home
  assumption, partial nested `XDG_RUNTIME_DIR` leakage, mutable verified
  environment, last-candidate diagnostic overwrite, and a nominal five-probe
  limit that could execute ten subprocesses.
- Version target is `0.1.0-experimental.18`. Fresh final local gates after the
  clean second review: backend 137/137; frontend 191/191 in 25 files; Biome 63
  files; both TypeScript typechecks; compileall; Rollup; package layout/import
  2/2. Two post-review packages are byte-identical: 22 entries, 296,194 bytes,
  SHA-256 `BF1DFB6C873C506404333679701AC3DE9E60AAE1FB327F993E5358FBE767584B`.
- Publication remained gated on the clean second review and fresh local gates;
  the following publication block records their completed GitHub verification.
  Physical GOG and Epic validation still block stable promotion.

### Experimental.18 publication and installation kit

- Commit `9477c5a` (`fix: use host session bus for UMU re-entry`) was pushed to
  both `feat/trainer-relay` and `main`. Annotated tag
  `v0.1.0-experimental.18` points to that implementation commit.
- GitHub Actions passed for the feature branch (`33346234146`), main
  (`33346236984`), and tag/release (`33346349508`). The tag workflow completed
  frontend, backend, package-layout/build, and release-publication jobs.
- Prerelease:
  `https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.18`.
  Direct asset:
  `https://github.com/matheussilva421/TrainerRelay/releases/download/v0.1.0-experimental.18/TrainerRelay.zip`.
- The public asset is 296,194 bytes with SHA-256
  `BF1DFB6C873C506404333679701AC3DE9E60AAE1FB327F993E5358FBE767584B`.
  A fresh download is byte-identical to the final local deterministic package.
- Created and verified
  `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.18-kit` with the
  versioned public ZIP, Portuguese guide, validation checklist, README,
  context, `LEIA-ME.txt`, and `SHA256SUMS.txt`. All six manifest entries passed
  after the copy. A standalone installation ZIP was also copied to
  `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.18.zip`.
- Physical validation remains the only runtime blocker. Install `.18`, keep
  diagnostic mode enabled, relaunch the same GOG game, and export a TXT.
  Expected order: `container_reentry_verified`, `trainer_spawned`, then
  `trainer_running`. A failed preflight should appear once for the same stable
  session and launch no trainer. Epic remains a separate gate; do not promote
  this build to stable until both stores pass.

### Experimental.19 container re-entry confirmation hardening

- The Claude root-cause report in the independent `trainer-relay-third`
  worktree was reviewed against the final `.18` implementation and the local
  UniFiDeck/UMU sources. The useful residual findings were host runtime-root
  consistency and the lack of proof that the spawned UMU process actually
  re-entered the verified launcher service. The inherited launcher-service
  marker remains diagnostic only; it is never a launch authority.
- TDD now forces one verified host launch context for both the preflight and
  sidecar. The watcher removes pressure-vessel `HOME`, `PATH`,
  `XDG_DATA_HOME`, `UMU_FOLDERS_PATH`, D-Bus, and runtime-dir values before
  applying the immutable host context returned by the successful probe.
- The prefix MD5 remains authoritative for the expected bus. If a captured
  `STEAM_COMPAT_APP_ID` exists, it is accepted only as a matching cross-check;
  disagreement fails before invoking the launch client with
  `container_reentry_identity_mismatch`.
- The runner drains stdout/stderr continuously and recognizes the exact UMU
  INFO line `Re-entering container through bus '<expected-bus>'`, including a
  line split across pipe reads. Another bus never confirms the launch. The
  exact expected `Failed to find bus name` line is recorded as a bounded
  failure observation.
- `UMU_LOG=info` is now always set because that INFO line is part of the
  fail-closed correctness contract; DEBUG remains prohibited because it emits
  the full derived environment. `running` requires both exact re-entry
  confirmation and three seconds of process activity.
- If confirmation is absent after three seconds, Trainer Relay records
  `container_reentry_confirmation_failed`, terminates only its owned process
  group, leaves the game intact, latches the same PID/start-time session in
  `failed`, and requires manual Retry. This deadline precedes UMU 1.4.4's
  normal independent-container fallback window.
- New bounded diagnostics include `app_id_source`,
  `service_marker_present`, `container_reentry_confirmed`, and
  `container_reentry_confirmation_failed`; they expose neither D-Bus addresses
  nor complete environments. Current focused gate: 149/149 backend tests pass.
- The mandatory two-axis review initially reported six actionable items. All
  were corrected before publication: game-private `UMU_FOLDERS_PATH` fallback
  was removed; success is now the exact stderr line
  `INFO: Re-entering container through bus '<expected-bus>'`; failure requires
  the exact INFO prefix plus a numeric `(retry N)` suffix; a bounded 50 ms
  condition wait reduces pipe-drain scheduling races; the observation's own
  monotonic timestamp must be within the three-second deadline; repeated launch
  state cleanup moved to one helper; and the stale `.18` hash was removed from
  the `.19` guide pending final packaging. The official UMU source and formatter
  were consulted directly to confirm `SIMPLE_FORMAT = "%(levelname)s: %(message)s"`.
- Version target is `0.1.0-experimental.19`. Full frontend/package gates,
  deterministic ZIP review, commit/push, tag/release, public-asset comparison,
  installation kit, and physical GOG/Epic validation remain pending at this
  checkpoint. Stable promotion is still prohibited until both stores pass.

### Experimental.19 final local verification

- Direct post-review verification is clean. Backend: 149/149. Packaging:
  2/2. Frontend: 191/191 in 25 files. Biome: 63 files. Both TypeScript
  typechecks, `compileall`, Rollup build, and `git diff --check` passed.
- The requested `pnpm` entrypoints were attempted first, but the local package
  manager refused its registry-mediated pnpm 11.5.0 switch because the registry
  signature could not be verified in the restricted environment. No override
  was used. The exact project-local Biome, TypeScript, Vitest, and Rollup
  binaries then passed through `npm exec --offline`.
- Two final package generations are byte-identical. The ZIP uses stored entries
  only, contains 22 entries, passes `ZipFile.testzip()`, has 307,848 bytes, and
  SHA-256
  `316C1D172CA3FF806D54ED6B831E92DA242D3354CB8149F1E9991C4A55FD16B1`.
- Commit/push, annotated tag, GitHub prerelease workflow, public-asset byte
  comparison, and installation-kit creation are the remaining publication
  steps. Physical GOG and Epic checks remain mandatory after installation.

### Experimental.19 publication and installation kit

- Commit `f89f476` (`fix: confirm UMU container re-entry`) was pushed to both
  `feat/trainer-relay` and `main`. Annotated tag
  `v0.1.0-experimental.19` points to that implementation commit.
- GitHub Actions passed for the feature branch (`33360558539`), main
  (`33360558446`), and tag/release (`33360577462`). The tag workflow completed
  backend, frontend, package-layout/build, artifact, and release-publication
  jobs. Its only annotations concern GitHub's Node.js 20 action deprecation;
  no Trainer Relay gate failed.
- Prerelease:
  `https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.19`.
  Direct asset:
  `https://github.com/matheussilva421/TrainerRelay/releases/download/v0.1.0-experimental.19/TrainerRelay.zip`.
- The public asset is 307,848 bytes with SHA-256
  `316C1D172CA3FF806D54ED6B831E92DA242D3354CB8149F1E9991C4A55FD16B1`.
  A fresh download is byte-identical to the final local deterministic package,
  and GitHub reports the same digest.
- Created and verified
  `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.19-kit` with the
  versioned public ZIP, Portuguese guide, validation checklist, README,
  context, `LEIA-ME.txt`, and `SHA256SUMS.txt`. All six manifest entries pass.
  Also created standalone installation ZIP
  `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.19.zip` and kit
  archive
  `C:\Users\slvma\Downloads\TrainerRelay-v0.1.0-experimental.19-kit.zip`.
- Physical validation remains the runtime gate. Install `.19`, keep diagnostic
  mode enabled, relaunch the GOG title, and export a TXT. Expected healthy
  order: `container_reentry_verified`, `trainer_spawned`,
  `container_reentry_confirmed`, `trainer_running`. GOG and Epic must both pass
  before any stable promotion.

### Experimental.19 physical GOG functional PASS

- The physical Steam Deck export
  `TrainerRelay-diagnostics-20260831-181847.txt` records one complete healthy
  BioShock 2 Remastered GOG session for identity `gog:1482265668`.
- The runtime verified container re-entry on the first attempt, spawned one
  trainer process group, confirmed the expected UMU bus after 1,221 ms, and
  reached `trainer_running` after 3,289 ms. The game and trainer both used
  `/home/deck/.local/share/unifideck/prefixes/1482265668`.
- The user explicitly confirmed that an in-game trainer function worked. This
  upgrades the GOG result from launch-only evidence to a functional PASS.
- When the game session ended, Trainer Relay sent non-forced `SIGTERM` only to
  its owned process group. The export contains no failure, retry, ambiguity,
  premature trainer exit, or container-confirmation failure.
- The repeated `candidate_rejected` events are expected fail-closed filtering
  of trainer-side processes, but are diagnostically noisy; they did not create
  another trainer instance or affect the successful run.
- Remaining GOG checklist items are Force Sync persistence and diagnostic
  clear behavior. Epic physical validation remains entirely pending. Do not
  promote to stable until both store columns satisfy the promotion gate.
