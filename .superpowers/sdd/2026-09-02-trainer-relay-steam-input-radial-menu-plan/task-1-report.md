# Task 1 report: deterministic Steam Input radial planner

Date: 2026-09-02
Branch: `feat/trainer-relay`
Status: DONE

## Implementation

Implemented the pure TypeScript Steam Input domain slice required by Task 1:

- `SteamInputCommandItem`, `SteamInputRadialPage`, `SteamInputRadialPlanV1`,
  `BuildRadialPlanInput`, and `Sha256Digest` in `src/domain/steamInput/types.ts`.
- `buildSteamInputCommandItems` in `planner.ts`:
  - returns no commands when command capability is disabled;
  - accepts only the existing finite symbolic hotkey allowlist;
  - skips empty, whitespace-padded, bounded-text-invalid, or control-character
    labels and invalid hotkeys;
  - expands multiple alternatives in source order;
  - deduplicates alternatives by canonical modifier/key chord;
  - uses deterministic `${cheat.id}:${zeroBasedHotkeyIndex}` IDs;
  - appends compact formatted hotkeys only when a cheat has multiple valid
    alternatives; and
  - excludes cheat state from all command labels and authority data.
- `canonicalizeCheatAuthority` uses the required stable object shape and keeps
  original command order.
- `computeCatalogFingerprint` UTF-8 encodes the canonical authority, calls the
  injected SHA-256 digest, requires exactly 32 bytes, and returns lowercase
  hexadecimal.
- `buildSteamInputRadialPlan` validates positive safe-integer AppIDs, matching
  identity, matching/lowercase 64-character trainer SHA-256, lowercase
  64-character catalog fingerprints, and at least one command. It creates
  deterministic six-command pages with reserved command positions, previous
  and next page targets, and the exact physical-click left-trackpad contract.

The planner creates fresh page/item/hotkey arrays and does not mutate the input
control snapshot. Navigation is represented only by page targets; it has no
keyboard hotkey, release action, or state field.

## Files

Created and included in the task commit:

- `src/domain/steamInput/types.ts`
- `src/domain/steamInput/planner.ts`
- `tests/steam-input-planner.test.ts`
- `.superpowers/sdd/2026-09-02-trainer-relay-steam-input-radial-menu-plan/task-1-report.md`

No unrelated files were modified. The pre-existing untracked
`.codex-remote-attachments/` directory was not read, changed, staged, or
committed.

## TDD RED/GREEN evidence

### Cycle 1: command expansion and fingerprint

RED command:

```text
node_modules/.bin/vitest.cmd run tests/steam-input-planner.test.ts
```

Result: expected failure before implementation. Vitest reported that it could
not find `../src/domain/steamInput/planner`; 0 tests ran.

GREEN result after the minimum command/fingerprint implementation: 6 tests
passed, 0 failed in the focused file.

### Cycle 2: pagination and activation

RED result after adding the pagination tests: 10 tests were collected; the 6
existing tests passed and 4 new tests failed with the expected
`buildSteamInputRadialPlan is not a function` error.

GREEN result after the minimum pagination implementation: all 10 focused tests
passed.

## Exact validation results

Final focused planner test:

```text
node_modules/.bin/vitest.cmd run tests/steam-input-planner.test.ts
```

Result: 1 test file passed; 10 tests passed; 0 failed.

Requested frontend regression tests:

```text
node_modules/.bin/vitest.cmd run tests/cheat-decoder.test.ts tests/cheat-control-list.test.ts tests/steam-input-planner.test.ts
```

Result: 3 test files passed; 21 tests passed; 0 failed.

Requested test TypeScript check:

```text
node_modules/.bin/tsc.cmd --noEmit -p tsconfig.test.json
```

Result: exit code 0; no diagnostics.

Additional production TypeScript check:

```text
node_modules/.bin/tsc.cmd --noEmit
```

Result: exit code 0; no diagnostics.

Lint/format check:

```text
node_modules/.bin/biome.cmd check src tests vitest.config.ts
```

Result: 78 files checked; no fixes and no errors.

Full frontend suite:

```text
node_modules/.bin/vitest.cmd run
```

Result: 31 test files passed; 227 tests passed; 0 failed. This includes the
10 new Task 1 tests and is 10 tests above the stated 217-test frontend
baseline.

## Self-review

- The public plan contains exactly `schemaVersion: 1`,
  `controller: "steam_deck_builtin"`, `input: "left_trackpad"`, and
  `activation: "physical_click"`.
- Command sectors remain at array positions 0 through 5 on every page; page
  navigation occupies the reserved positions 6 and 7 through the page target
  fields and never carries a keyboard command.
- Page sizes for fourteen commands are `6, 6, 2`; page 1 has only `nextPage`,
  page 2 has both targets, and page 3 has only `previousPage`.
- No random IDs, trainer paths, arbitrary Steam payloads, free-form commands,
  touch-release actions, release actions, or state fields enter the plan.
- Local `node_modules` binaries were used for all JavaScript/TypeScript/Vitest/
  Biome gates, as required.

## Concerns and boundaries

- Physical Steam Deck interaction, private Steam Input adapter behavior, layout
  persistence, and configurator handoff are intentionally not part of Task 1;
  they remain follow-up task boundaries and were not claimed as validated here.
- The exact Task 1 interfaces represent command sectors by stable item array
  positions and navigation by `previousPage`/`nextPage`; explicit sector fields
  are not added because they are absent from the required public interfaces.
- The working tree contained the pre-existing ignored `.codex-remote-attachments/`
  directory. It remains outside the task commit.

## GitHub / continuation

The required commit subject is:

```text
feat: add deterministic Steam Input radial planner
```

The commit SHA is supplied in the final handoff. To continue Task 2, consume
`SteamInputRadialPlanV1` and keep the adapter/runtime work separate from this
pure domain module; re-run the focused planner test and the frontend TypeScript
check before integration.

## Fix round 1

Date: 2026-09-02
Status: DONE

### Review findings addressed

- Final generated labels are now bounded to 80 characters after appending the
  formatted hotkey. Only the base label is shortened; every valid alternative
  remains present and its full hotkey suffix remains visible.
- Label validation now rejects the complete Unicode C1 control range
  U+0080 through U+009F in addition to C0 controls and DEL.
- The mutation test now compares the complete input against a deep-cloned
  baseline, including nested hotkeys and modifier arrays.
- Focused edge coverage now includes an exactly 80-character source label,
  bounded final alternative labels, trainer SHA-256 mismatch, and explicit
  `hotkeys` precedence when both `hotkey` and `hotkeys` are present.
- The deduplication test no longer asserts a duplicate-specific item-ID
  renumbering policy that is not required by the brief.

### TDD RED evidence

Command:

```text
node_modules/.bin/vitest.cmd run tests/steam-input-planner.test.ts
```

Result before the production fix: 13 tests collected; 11 passed and 2 failed.
The expected failures showed alternative labels emitted at 90 characters
instead of the required 80 maximum, and labels containing U+0080/U+009F being
accepted instead of skipped.

### TDD GREEN evidence

The same focused command after the minimum production fix passed 1 test file,
13 tests passed, and 0 failed.

### Fix round 1 validation

Focused planner:

```text
node_modules/.bin/vitest.cmd run tests/steam-input-planner.test.ts
```

Result: 1 test file passed; 13 tests passed; 0 failed.

Required frontend regressions:

```text
node_modules/.bin/vitest.cmd run tests/cheat-decoder.test.ts tests/cheat-control-list.test.ts tests/steam-input-planner.test.ts
```

Result: 3 test files passed; 24 tests passed; 0 failed.

Test TypeScript check:

```text
node_modules/.bin/tsc.cmd --noEmit -p tsconfig.test.json
```

Result: exit code 0; no diagnostics.

Production TypeScript check:

```text
node_modules/.bin/tsc.cmd --noEmit
```

Result: exit code 0; no diagnostics.

Biome:

```text
node_modules/.bin/biome.cmd check src tests vitest.config.ts
```

Result: 78 files checked; no fixes and no errors.

Full frontend suite:

```text
node_modules/.bin/vitest.cmd run
```

Result: 31 test files passed; 230 tests passed; 0 failed.

Git whitespace validation:

```text
git diff --check
```

Result: exit code 0; no whitespace errors. The pre-existing ignored
`.codex-remote-attachments/` directory remains untouched and outside the fix
commit.

### Fix round 1 concerns

No open Task 1 code concern remains from this review round. Physical Steam
Input generation and Steam Deck validation remain later-task boundaries and
are not claimed by this pure planner fix.
