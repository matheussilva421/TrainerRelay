# Trainer Relay Steam Input Radial Menu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a separate, reviewable Steam Input layout whose left trackpad exposes every eligible Trainer Relay hotkey across physically clicked radial-menu pages without changing the user's selected layout.

**Architecture:** A pure TypeScript planner turns strict cheat-control snapshots into deterministic six-command pages. A private-API adapter is isolated behind runtime fingerprints and a read-only probe; it may clone a layout only after a physical Steam Deck capture proves a distinct-save sequence and unchanged selection. Python persists bounded generated-layout metadata and sanitized probe reports, while the routed Decky page owns preview, confirmation, generation, and configurator opening.

**Tech Stack:** TypeScript 5.9, React 18, Vitest 4, Decky UI/API, private `SteamClient.Input`/`SteamClient.App` feature probes, Python 3/unittest, SettingsManager, Steam Input on Steam Deck.

**Spec:** `docs/superpowers/specs/2026-09-02-trainer-relay-steam-input-radial-menu-design.md`

## Global Constraints

- Target only the built-in Steam Deck (`Neptune`) controller and the left trackpad.
- Touch selects a radial sector; only a physical left-trackpad click may emit its hotkey or page action. Touch release emits nothing.
- Use six command sectors plus fixed previous/next sectors per page. Navigation never emits a keyboard command.
- Clone the selected source into a distinct personal layout. Never modify, select, publish, delete, or reapply a layout silently.
- Before and after saving, prove that the selected source-layout identifier is unchanged and that the generated identifier is distinct.
- Unknown Steam runtime fingerprints, opaque response shapes, changed authority, or unprovable invariants fail closed to `Open Steam controller configurator`.
- Do not call `RegisterForControllerConfigInfoMessages`; Decky's own type definition warns that it can break layout selection.
- Do not edit active VDF files or use XTest, X11/Wayland injection, `uinput`, root privileges, shell/eval, memory patching, or a resident helper.
- Hotkeys come only from the existing finite `SymbolicHotkey` domain. Generated labels never claim enabled or disabled state.
- Logs and probe exports contain no complete controller payload, account identifier, trainer path, cloud token, environment dump, or arbitrary private response.
- Use strict TDD for every behavior change: RED for the expected missing/incorrect behavior, minimum GREEN, relevant regressions, then a small commit.
- Preserve the current Quick Access cheat controls and every non-left-trackpad binding.
- The probe build is `0.1.0-experimental.21.probe.1`; the physically validated generation candidate is `0.1.0-experimental.21`.

## File map

- `src/domain/steamInput/types.ts`: public immutable domain types for plans, pages, probe results, registry records, and generation results.
- `src/domain/steamInput/planner.ts`: cheat expansion, label normalization, catalog authority serialization, and deterministic pagination.
- `src/domain/steamInput/decoder.ts`: strict decoding of registry/probe/generation wire responses and private adapter summaries.
- `src/infra/steamInput/adapter.ts`: narrow dependency-injected Steam client boundary, read-only probe, configurator opening, and profile dispatch.
- `src/infra/steamInput/runtimeFingerprint.ts`: deterministic runtime-shape fingerprinting without recording private values.
- `src/infra/steamInput/profiles/neptuneRuntimeV1.ts`: the only writable runtime profile; created only after Task 5 physical evidence.
- `src/infra/radialLayoutRpc.ts`: typed registry and probe-export RPC client.
- `src/hooks/useSteamInputRadialMenu.ts`: authority revalidation and UI state machine.
- `src/components/SteamInputRadialMenu.tsx`: preview, confirmation, failure, stale, and open-configurator UI.
- `trainer_relay/radial_registry.py`: strict `RadialLayoutRegistryV1` decoding, validation, revision allocation, and bounded persistence data.
- `trainer_relay/steam_input_probe.py`: strict sanitized probe-report validation and atomic Downloads export.
- `trainer_relay/rpc.py` and `main.py`: registry/probe RPC exposure only; layout editing remains frontend-owned.
- `tests/fixtures/steam-input/neptune-runtime-v1.json`: synthetic, sanitized contract fixture derived from Task 5 evidence.
- `docs/notes/2026-09-02-steam-input-neptune-runtime-v1-evidence.md`: exact physical evidence and mutation/no-mutation decision.

---

### Task 1: Pure radial plan, hotkey expansion, and deterministic pages

**Files:**
- Create: `src/domain/steamInput/types.ts`
- Create: `src/domain/steamInput/planner.ts`
- Create: `tests/steam-input-planner.test.ts`

**Interfaces:**
- Consumes: `ReadyCheatControls`, `CheatDescriptor`, and `SymbolicHotkey` from `src/domain/cheats/types.ts`.
- Produces: `canonicalizeCheatAuthority(controls: ReadyCheatControls): string`.
- Produces: `computeCatalogFingerprint(controls: ReadyCheatControls, digest: Sha256Digest): Promise<string>`.
- Produces: `buildSteamInputCommandItems(controls: ReadyCheatControls): SteamInputCommandItem[]`.
- Produces: `buildSteamInputRadialPlan(input: BuildRadialPlanInput): SteamInputRadialPlanV1`.
- Produces: the exact interfaces from the spec with `controller: "steam_deck_builtin"`, `input: "left_trackpad"`, and `activation: "physical_click"`.

Define the supporting input type in `types.ts`:

```ts
export interface BuildRadialPlanInput {
  appId: number;
  identity: LaunchIdentity;
  trainerSha256: string;
  catalogFingerprint: string;
  controls: ReadyCheatControls;
}

export type Sha256Digest = (value: Uint8Array) => Promise<Uint8Array>;
```

- [ ] **Step 1: Write the failing command-expansion tests**

Add tests with these literal expectations:

```ts
const controls: ReadyCheatControls = {
  identity: "gog:1482265668",
  status: "ready",
  trainerSha256: "a".repeat(64),
  source: "adapter",
  trainerLabel: "BioShock 2 FLiNG",
  capabilities: { commands: true, authoritativeState: false, toggles: false },
  diagnostic: null,
  cheats: [
    { id: "health", label: "Infinite Health", hotkey: { modifiers: [], key: "NUMPAD1" }, state: "unknown" },
    {
      id: "ammo",
      label: "Infinite Ammo",
      hotkeys: [
        { modifiers: [], key: "NUMPAD2" },
        { modifiers: ["ctrl"], key: "F2" },
      ],
      state: "unknown",
    },
  ],
};

expect(buildSteamInputCommandItems(controls).map(({ label }) => label)).toEqual([
  "Infinite Health",
  "Infinite Ammo (NUMPAD2)",
  "Infinite Ammo (Ctrl+F2)",
]);
```

Also assert commands are empty when `capabilities.commands` is false, malformed/empty labels cannot enter the plan, alternatives are deduplicated by canonical chord, input order is stable, and no cheat state text enters a label.

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `node_modules/.bin/vitest.cmd run tests/steam-input-planner.test.ts`

Expected: FAIL importing `src/domain/steamInput/planner.ts`.

- [ ] **Step 3: Implement the minimum expansion and authority serialization**

Use the existing `formatHotkey` for display only. Serialize authority with sorted object keys and original cheat order:

```ts
export const canonicalizeCheatAuthority = (controls: ReadyCheatControls): string =>
  JSON.stringify({
    identity: controls.identity,
    trainerSha256: controls.trainerSha256,
    source: controls.source,
    commands: buildSteamInputCommandItems(controls).map(({ itemId, cheatId, label, hotkey }) => ({
      itemId,
      cheatId,
      label,
      hotkey,
    })),
  });
```

Generate `itemId` as `${cheat.id}:${zeroBasedHotkeyIndex}`. Do not use random IDs. `computeCatalogFingerprint` UTF-8 encodes `canonicalizeCheatAuthority`, passes it to the injected digest, requires exactly 32 returned bytes, and emits lowercase hexadecimal.

- [ ] **Step 4: Write the failing pagination and activation tests**

Create fourteen distinct controls and assert pages of `6, 6, 2`, fixed sector numbers `0..5`, previous sector `6`, next sector `7`, no previous target on page 1, no next target on page 3, and unchanged command-sector positions after navigation sectors are omitted.

Assert the plan literal contains:

```ts
{
  controller: "steam_deck_builtin",
  input: "left_trackpad",
  activation: "physical_click",
}
```

and has no `touch_release`, `release`, or state field.

- [ ] **Step 5: Implement deterministic pagination and verify GREEN**

`buildSteamInputRadialPlan` validates positive safe-integer AppID, matching identity, lowercase 64-character SHA-256, lowercase 64-character catalog fingerprint, and at least one command. It slices six commands per page and assigns navigation targets without mutating input arrays.

Run: `node_modules/.bin/vitest.cmd run tests/steam-input-planner.test.ts`

Expected: all Task 1 tests PASS.

- [ ] **Step 6: Run frontend regressions and commit**

Run: `node_modules/.bin/tsc.cmd --noEmit -p tsconfig.test.json`

Run: `node_modules/.bin/vitest.cmd run tests/cheat-decoder.test.ts tests/cheat-control-list.test.ts tests/steam-input-planner.test.ts`

Expected: all PASS.

Commit: `feat: add deterministic Steam Input radial planner`

---

### Task 2: Bounded generated-layout registry and backend RPCs

**Files:**
- Create: `trainer_relay/radial_registry.py`
- Create: `tests_backend/test_radial_registry.py`
- Modify: `trainer_relay/rpc.py`
- Modify: `main.py`
- Modify: `tests_backend/test_rpc.py`
- Modify: `tests_backend/test_main.py`

**Interfaces:**
- Produces: `RADIAL_LAYOUT_REGISTRY_KEY = "RadialLayoutRegistryV1"`.
- Produces: `empty_radial_layout_registry() -> dict[str, Any]`.
- Produces: `decode_radial_layout_registry(value: Any) -> dict[str, Any]`.
- Produces: `validate_generated_radial_layout(value: Any) -> dict[str, Any]`.
- Produces: `next_radial_layout_revision(registry, app_id, identity, trainer_sha256, catalog_fingerprint) -> int`.
- Produces RPCs `get_radial_layout_registry()` and `record_generated_radial_layout(data)`.

- [ ] **Step 1: Write failing registry tests**

Use one literal valid record:

```python
VALID = {
    "appId": 123456789,
    "identity": "gog:1482265668",
    "trainerSha256": "a" * 64,
    "catalogFingerprint": "b" * 64,
    "steamRuntimeFingerprint": "c" * 64,
    "sourceLayoutId": "autosave://123/source",
    "generatedLayoutId": "personal://123/generated",
    "generatedLayoutName": "Trainer Relay — BioShock 2 — aaaaaaaa — r1",
    "revision": 1,
    "createdAt": "2026-09-02T12:00:00Z",
}
```

Assert strict exact keys, positive safe AppID, launch identity, three lowercase hashes, distinct source/generated IDs, 1–256 bounded printable IDs, 1–120 bounded printable name, revision `1..2**31-1`, UTC timestamp, a 128-record maximum, invalid-entry dropping on decode, all-or-nothing validation on write, and monotonic revision allocation scoped by AppID+identity+trainer hash+catalog fingerprint.

- [ ] **Step 2: Run registry tests and confirm RED**

Run: `python -m unittest tests_backend.test_radial_registry -v`

Expected: ERROR importing `trainer_relay.radial_registry`.

- [ ] **Step 3: Implement strict registry validation**

Follow `trainer_relay/cheat_config.py`: parse JSON strings, reject booleans as integers, normalize no opaque identifier, reject Unicode control characters, and return a new dictionary. Keep at most the newest 128 valid decoded records ordered by `(createdAt, revision)`; never delete a Steam layout.

- [ ] **Step 4: Write failing RPC/main tests**

Assert `get_radial_layout_registry` returns strict safe metadata, `record_generated_radial_layout` rejects extra keys and same source/generated IDs, SettingsManager write failures return `radial_registry_persistence_failed`, and no RPC accepts a controller payload or a command.

- [ ] **Step 5: Implement backend RPCs minimally**

Add methods to `RelayRpc` and classmethods to `Plugin`. `record_generated_radial_layout` re-reads settings, allocates the expected next revision, requires the submitted revision to equal it, appends the validated record, validates the whole document, persists it, and re-reads before returning.

- [ ] **Step 6: Run backend regressions and commit**

Run: `python -m unittest tests_backend.test_radial_registry tests_backend.test_rpc tests_backend.test_main -v`

Run: `python -m unittest discover -s tests_backend -p "test_*.py"`

Expected: all PASS.

Commit: `feat: persist generated radial layout metadata`

---

### Task 3: Strict frontend registry boundary and read-only Steam Input adapter

**Files:**
- Create: `src/domain/steamInput/decoder.ts`
- Create: `src/infra/radialLayoutRpc.ts`
- Create: `src/infra/steamInput/runtimeFingerprint.ts`
- Create: `src/infra/steamInput/adapter.ts`
- Create: `tests/steam-input-decoder.test.ts`
- Create: `tests/radial-layout-rpc.test.ts`
- Create: `tests/steam-input-adapter.test.ts`

**Interfaces:**
- Consumes: Task 1 types and Task 2 wire responses.
- Produces: `decodeRadialLayoutRegistry(value: unknown): RadialLayoutRegistryV1`.
- Produces: `radialLayoutRpc.getRegistry()` and `radialLayoutRpc.record(record)`.
- Produces: `fingerprintSteamInputShape(shape: SteamInputMethodShape, digest: Sha256Digest): Promise<string>`.
- Produces: `createSteamInputLayoutAdapter(dependencies): SteamInputLayoutAdapter` with `probe`, `inspectSelectedLayout`, `createSeparateLayout`, and `openConfigurator`.

Define these contracts in `types.ts` and import them into the adapter:

```ts
export interface SteamInputMethodShape {
  getConfig: boolean;
  exportConfig: boolean;
  startEditing: boolean;
  saveEditing: boolean;
  stopEditing: boolean;
  setActionSet: boolean;
  setActivator: boolean;
  setBinding: boolean;
  setSourceMode: boolean;
  setSelected: boolean;
  showConfigurator: boolean;
  responsePrimitiveKeys: string[];
}

export type SteamInputCapabilityResult =
  | { status: "unavailable"; diagnostic: string }
  | { status: "readonly"; snapshot: SelectedLayoutSnapshot }
  | { status: "writable"; snapshot: SelectedLayoutSnapshot };

export interface CreateRadialLayoutRequest {
  source: SelectedLayoutSnapshot;
  plan: SteamInputRadialPlanV1;
  generatedLayoutName: string;
}

export interface CreatedLayout {
  sourceLayoutId: string;
  generatedLayoutId: string;
  generatedLayoutName: string;
  selectedLayoutIdAfterSave: string;
}
```

- [ ] **Step 1: Write failing strict decoder and RPC tests**

Reject extra fields, unsafe IDs/names, non-safe AppIDs, malformed hashes/timestamps, duplicate records, non-distinct IDs, unknown statuses, and arbitrary diagnostic text. Assert transport exceptions map to `RadialLayoutRpcError` with bounded codes.

- [ ] **Step 2: Confirm decoder/RPC RED, implement, and reach GREEN**

Run: `node_modules/.bin/vitest.cmd run tests/steam-input-decoder.test.ts tests/radial-layout-rpc.test.ts`

Expected before implementation: missing-module failures. Implement exact-key decoders matching Task 2 and rerun until all PASS.

- [ ] **Step 3: Write failing read-only adapter tests**

Inject an object that records every call. The read-only probe may inspect method presence and call only `GetConfigForAppAndController(appId, 0)`. Assert it never calls:

```ts
[
  "ExportCurrentControllerConfiguration",
  "StartEditingControllerConfigurationForAppIDAndControllerIndex",
  "SetEditingControllerConfigurationActionSet",
  "SetEditingControllerConfigurationInputActivator",
  "SetEditingControllerConfigurationInputBinding",
  "SetEditingControllerConfigurationSourceMode",
  "SaveEditingControllerConfiguration",
  "SetSelectedConfigForApp",
  "RegisterForControllerConfigInfoMessages",
]
```

Test missing methods, thrown/rejected reads, non-Neptune summary, unknown response shape, and a synthetic recognized read-only summary. `createSeparateLayout` must return `unsupported_runtime` without calling any method until a writable profile exists.

- [ ] **Step 4: Implement the narrow adapter and shape fingerprint**

Declare only the methods used by the adapter and type every private return as `unknown`. Convert private values into a bounded summary before they leave the adapter:

```ts
export interface SelectedLayoutSnapshot {
  appId: number;
  controllerIndex: 0;
  controller: "steam_deck_builtin";
  sourceLayoutId: string;
  sourceLayoutName: string;
  runtimeFingerprint: string;
}
```

The runtime fingerprint is SHA-256 over canonical JSON containing method-presence booleans, primitive response-key names, primitive type names, controller classification, and schema version. It contains no values from the private response.

`openConfigurator(appId)` calls only `SteamClient.App.ShowControllerConfigurator(appId)` after positive safe-integer validation.

- [ ] **Step 5: Run Task 3 gates and commit**

Run: `node_modules/.bin/vitest.cmd run tests/steam-input-decoder.test.ts tests/radial-layout-rpc.test.ts tests/steam-input-adapter.test.ts`

Run: `node_modules/.bin/tsc.cmd --noEmit`

Run: `node_modules/.bin/tsc.cmd --noEmit -p tsconfig.test.json`

Expected: all PASS and no `any` escaping `src/infra/steamInput/adapter.ts`.

Commit: `feat: add fail-closed Steam Input probe adapter`

---

### Task 4: Preview UI, sanitized probe export, and probe artifact

**Files:**
- Create: `trainer_relay/steam_input_probe.py`
- Create: `tests_backend/test_steam_input_probe.py`
- Modify: `trainer_relay/rpc.py`
- Modify: `main.py`
- Modify: `tests_backend/test_rpc.py`
- Modify: `tests_backend/test_main.py`
- Modify: `trainer_relay/diagnostics.py`
- Modify: `tests_backend/test_diagnostics.py`
- Create: `src/hooks/useSteamInputRadialMenu.ts`
- Create: `src/components/SteamInputRadialMenu.tsx`
- Create: `tests/steam-input-radial-controller.test.ts`
- Create: `tests/steam-input-radial-menu.test.ts`
- Modify: `src/views/RelayPage.tsx`
- Modify: `tests/relay-page.test.ts`
- Modify: `package.json`
- Modify: `tests_packaging/test_package_layout.py`
- Modify: `docs/GUIA-INSTALACAO-TESTES-E-LOGS.md`
- Modify: `docs/notes/2026-08-29-trainer-relay-handoff.md`

**Interfaces:**
- Produces RPC `export_steam_input_probe(data)` returning `{ path, bytesWritten }`.
- Produces `useSteamInputRadialMenu({ appId, identity, controls, adapter, rpc })`.
- Produces a read-only user flow: plan preview, unavailable reason, safe probe export, and `Open Steam controller configurator`.

- [ ] **Step 1: Write failing sanitized probe validation/export tests**

The frontend may submit only this exact report:

```python
{
    "schemaVersion": 1,
    "appId": 123456789,
    "identity": "gog:1482265668",
    "controller": "steam_deck_builtin",
    "controllerIndex": 0,
    "runtimeFingerprint": "c" * 64,
    "sourceLayoutIdHash": "d" * 64,
    "sourceLayoutNameLength": 17,
    "methodShape": {
        "getConfig": True,
        "exportConfig": True,
        "startEditing": True,
        "saveEditing": True,
        "setSelected": True,
        "showConfigurator": True,
    },
    "responsePrimitiveKeys": ["controller_type", "url"],
}
```

Reject raw payload/value fields, account IDs, source URL/name, arbitrary nested objects, more than 64 primitive keys, extra fields, and output above 16 KiB. Test atomic export to `TrainerRelay-steam-input-probe-YYYYMMDD-HHMMSS.json` with mode-independent LF and no diagnostics-journal insertion of the report.

- [ ] **Step 2: Implement probe export RPC and bounded diagnostics**

Add `steam_input` diagnostic events for `probe_completed`, `preview_created`, `authority_changed`, and `configurator_opened`. Event details are restricted to AppID, counts, hash prefixes, bounded result code, and correlation ID. Add `export_steam_input_probe` to `RelayRpc` and `Plugin`; it writes only the validated report.

- [ ] **Step 3: Write failing controller/state-machine tests**

Test `unavailable`, `ready`, `confirming`, `generating`, `created`, `stale`, and `failed`. In the probe build, no writable profile exists, so `generating` must be unreachable and the primary actions are `Export safe probe report` and `Open Steam controller configurator`.

At confirmation-time revalidation, change each of AppID, identity, trainer hash, catalog fingerprint, source layout ID, controller, and runtime fingerprint and assert `authority_changed` with zero adapter mutation calls.

- [ ] **Step 4: Implement the hook and Decky-native preview UI**

Reuse `ConfirmModal`, `DialogButton`, `Field`, `Focusable`, and existing notices. Show command/page counts and skipped reasons. The generated-layout button is disabled with the explicit reason `Steam Input runtime not physically validated` until Task 6 installs a matching profile.

Mount the component in `RelayPage` only when the shortcut is supported and `cheatControls.response.status === "ready"`. Do not add generation to Quick Access in this release.

- [ ] **Step 5: Make probe-version packaging RED then GREEN**

Change the expected version to `0.1.0-experimental.21.probe.1`, observe packaging failure, then synchronize `package.json`, `main.py`, documentation, and package tests. Build `TrainerRelay.zip` without a writable runtime profile.

- [ ] **Step 6: Run Task 4 gates, inspect ZIP, update handoff, and commit**

Run: `python -m unittest tests_backend.test_steam_input_probe tests_backend.test_rpc tests_backend.test_main tests_backend.test_diagnostics -v`

Run: `node_modules/.bin/vitest.cmd run tests/steam-input-radial-controller.test.ts tests/steam-input-radial-menu.test.ts tests/relay-page.test.ts`

Run: `python -m unittest discover -s tests_backend -p "test_*.py"`

Run: `node_modules/.bin/biome.cmd check src tests vitest.config.ts`

Run: `node_modules/.bin/tsc.cmd --noEmit`

Run: `node_modules/.bin/tsc.cmd --noEmit -p tsconfig.test.json`

Run: `node_modules/.bin/vitest.cmd run`

Run: `node_modules/.bin/rollup.cmd -c`

Run: `python -m unittest discover -s tests_packaging -p "test_*.py"`

Run: `python scripts/package_trainer_relay.py`

Run: `git diff --check`

Expected: all tests PASS; ZIP is installable but exposes no generation action for an unvalidated runtime.

Commit: `feat: add read-only Steam Input radial probe`

Push the branch so the probe ZIP can be installed on the Deck.

---

### Task 5: Hard physical checkpoint and sanitized Neptune runtime fixture

**Files:**
- Create only after evidence: `tests/fixtures/steam-input/neptune-runtime-v1.json`
- Create only after evidence: `docs/notes/2026-09-02-steam-input-neptune-runtime-v1-evidence.md`
- Modify: `docs/notes/2026-08-29-trainer-relay-handoff.md`

**Interfaces:**
- Consumes: the Task 4 probe ZIP and the user's existing BioShock 2 Steam Input layout.
- Produces: one synthetic contract fixture and an explicit `PASS_SAFE_CLONE` or `FAIL_SAFE_CLONE` ruling.
- Hard gate: Task 6 is forbidden unless the ruling is `PASS_SAFE_CLONE` with all invariants evidenced.

- [ ] **Step 1: Install and verify the probe build**

Install the Task 4 `TrainerRelay.zip` through Decky developer ZIP installation, restart Decky/Steam, open the BioShock 2 UniFiDeck shortcut, and verify the plugin displays `0.1.0-experimental.21.probe.1` and the correct numeric Steam AppID/`gog:1482265668` identity.

- [ ] **Step 2: Export the safe probe report before any Steam Input edit**

Press `Export safe probe report`. Copy the resulting JSON from `/home/deck/Downloads` to the repository evidence workspace. Confirm manually that it contains no source layout URL/name, account ID, trainer path, complete controller payload, or environment values.

- [ ] **Step 3: Establish before/after layouts through Steam's UI**

In Steam's controller configurator, record the currently selected source layout name and identifier shown by Steam. Export a new personal copy through Steam's own UI, name it `Trainer Relay Probe — BioShock 2`, and configure only its left trackpad as a two-item radial test: `NUMLOCK` and `NUMPAD1`, with physical click activation and no touch-release command. Do not apply it until the source identifier and source layout have been recorded.

- [ ] **Step 4: Capture lifecycle evidence without registering config-info messages**

Using CEF DevTools, record only calls/returns for the methods already allowlisted by Task 3 while Steam performs the UI-driven export/edit/save. Do not invoke `RegisterForControllerConfigInfoMessages`, `SetSelectedConfigForApp`, or a setter manually. Save the trace outside diagnostics, redact account IDs and complete payload values, and retain method order, argument primitive shapes, returned primitive key names, URL-scheme hashes, and selected-layout identifiers before/after.

- [ ] **Step 5: Decide the safety gate**

Record `PASS_SAFE_CLONE` only if evidence proves all of these:

1. Steam creates a distinct personal-layout identifier before radial setters mutate it.
2. The source selected-layout identifier remains unchanged throughout export, edit, and save.
3. The generated copy can be targeted without `SetSelectedConfigForApp` and without editing the source.
4. The saved result can be re-read and identified distinctly.
5. Stop/edit cleanup leaves Steam's configurator functional.

If any item is absent, record `FAIL_SAFE_CLONE`, keep only the read-only fallback, update the handoff, and stop this plan. Do not infer or approximate a private call sequence.

- [ ] **Step 6: Create a synthetic fixture only after PASS**

Create `tests/fixtures/steam-input/neptune-runtime-v1.json` with schema version, runtime fingerprint, method order, primitive argument shapes, source/generated URL schemes replaced with `autosave://synthetic-source` and `personal://synthetic-generated`, and a minimal synthetic left-trackpad radial payload containing `NUMLOCK` and `NUMPAD1`. Exclude user names, account IDs, timestamps, arbitrary bindings, and all non-left-trackpad values except structural hashes proving preservation.

- [ ] **Step 7: Validate, document, commit, and push the evidence**

Validate the fixture with a temporary strict test in `tests/steam-input-adapter.test.ts`; the test must reject extra keys and raw captured values.

Run: `node_modules/.bin/vitest.cmd run tests/steam-input-adapter.test.ts`

Run: `git diff --check`

Expected: PASS and no raw capture file in `git status`.

Commit: `test: add sanitized Neptune Steam Input contract fixture`

---

### Task 6: Fingerprinted Neptune clone profile and invariant harness

**Files:**
- Create: `src/infra/steamInput/profiles/neptuneRuntimeV1.ts`
- Modify: `src/infra/steamInput/adapter.ts`
- Modify: `src/domain/steamInput/decoder.ts`
- Modify: `tests/steam-input-adapter.test.ts`
- Consume: `tests/fixtures/steam-input/neptune-runtime-v1.json`

**Interfaces:**
- Consumes: Task 5 `PASS_SAFE_CLONE` fixture and Task 1 `SteamInputRadialPlanV1`.
- Produces: `neptuneRuntimeV1Profile: SteamInputRuntimeProfile`.
- Produces: `createSeparateLayout(request: CreateRadialLayoutRequest): Promise<CreatedLayout>` only for the exact fixture fingerprint.

The writable API remains private to the profile and exposes only methods proven
by the fixture:

```ts
export interface WritableSteamInputApi {
  GetConfigForAppAndController(appId: number, controllerIndex: 0): Promise<unknown> | unknown;
  ExportCurrentControllerConfiguration(
    controllerIndex: 0,
    appId: number,
    exportType: number,
    title: string,
    description: string,
    metadata: string,
  ): Promise<unknown>;
  StartEditingControllerConfigurationForAppIDAndControllerIndex(
    appId: number,
    controllerIndex: 0,
  ): Promise<unknown>;
  SetEditingControllerConfigurationActionSet(controllerIndex: 0, payload: unknown): Promise<unknown> | unknown;
  SetEditingControllerConfigurationInputActivator(controllerIndex: 0, payload: unknown): Promise<unknown> | unknown;
  SetEditingControllerConfigurationInputBinding(controllerIndex: 0, payload: unknown): Promise<unknown> | unknown;
  SetEditingControllerConfigurationSourceMode(controllerIndex: 0, payload: unknown): Promise<unknown> | unknown;
  SaveEditingControllerConfiguration(controllerIndex: 0, sharedConfig: false): Promise<unknown> | unknown;
  StopEditingControllerConfiguration(controllerIndex: 0): Promise<unknown> | unknown;
}
```

- [ ] **Step 1: Write failing profile-selection tests**

Assert the exact fixture fingerprint selects `neptuneRuntimeV1Profile`. A one-character fingerprint change, missing method, changed primitive shape, non-Neptune controller, controller index other than `0`, or changed source-layout ID returns `unsupported_runtime` with zero write calls.

- [ ] **Step 2: Write the failing successful-sequence test from the fixture**

Use a recording fake API. Assert the profile performs exactly the method sequence evidenced in Task 5, with the fixture's primitive argument shapes. Before every mutation, the source ID must equal the confirmed preview source. After save, `inspectSelectedLayout` must still return that source ID, and the created ID must equal `personal://synthetic-generated` and differ from source.

- [ ] **Step 3: Write failing layout-transform tests**

Given fourteen commands, assert three page definitions, physical-click activators only, no release activator, correct Steam keyboard codes for `NUMLOCK`, numpad keys, `F1..F24`, navigation actions without keyboard bindings, and byte/structural equality for every captured non-left-trackpad subtree hash.

- [ ] **Step 4: Implement the profile minimally from the captured contract**

Implement the profile as a closed translation table, not a generic protobuf/VDF editor:

```ts
export interface SteamInputRuntimeProfile {
  readonly fingerprint: string;
  createSeparateLayout(
    api: WritableSteamInputApi,
    request: CreateRadialLayoutRequest,
  ): Promise<CreatedLayout>;
}
```

Decode every private return through fixture-backed exact-key guards. Map only the existing finite hotkey allowlist to the exact captured Steam keyboard enums. Reject any field or chord the profile cannot encode. Stop editing in `finally` using only the evidenced cleanup call.

- [ ] **Step 5: Write failure-injection tests for every mutation boundary**

Make each export/edit/set/save/re-read operation throw, reject, return malformed data, return the source ID as generated ID, or change the selected source ID. Assert no automatic retry, no `SetSelectedConfigForApp`, bounded diagnostics, and best-effort stop-edit cleanup only when editing actually started.

- [ ] **Step 6: Run Task 6 gates and commit**

Run: `node_modules/.bin/vitest.cmd run tests/steam-input-adapter.test.ts tests/steam-input-planner.test.ts`

Run: `node_modules/.bin/tsc.cmd --noEmit`

Run: `node_modules/.bin/tsc.cmd --noEmit -p tsconfig.test.json`

Expected: all PASS for the exact profile and fail-closed for every other fingerprint.

Commit: `feat: add fingerprinted Neptune layout clone profile`

---

### Task 7: Confirmed generation flow, stale registry, and configurator handoff

**Files:**
- Modify: `src/hooks/useSteamInputRadialMenu.ts`
- Modify: `src/components/SteamInputRadialMenu.tsx`
- Modify: `src/infra/radialLayoutRpc.ts`
- Modify: `tests/steam-input-radial-controller.test.ts`
- Modify: `tests/steam-input-radial-menu.test.ts`
- Modify: `tests/radial-layout-rpc.test.ts`
- Modify: `src/views/RelayPage.tsx`
- Modify: `tests/relay-page.test.ts`
- Modify: `trainer_relay/diagnostics.py`
- Modify: `tests_backend/test_diagnostics.py`

**Interfaces:**
- Consumes: Tasks 1, 2, 3, and 6.
- Produces: the full routed-page `ready -> confirming -> generating -> created` flow.
- Produces: registry-based `stale` detection and a retry that only reopens the configurator.

- [ ] **Step 1: Write failing authority revalidation tests**

Prepare a preview, then mutate one authority field at a time. Assert generation is rejected before the first writable adapter call. Include AppID, identity, trainer hash, canonical catalog digest, controller, source layout ID, and runtime fingerprint.

- [ ] **Step 2: Write failing successful-flow tests**

Assert user confirmation is mandatory, only one generation runs, and the literal BioShock fixture produces `Trainer Relay — BioShock 2 — aaaaaaaa — r1`. Adapter success is recorded through the backend before opening the configurator, and the registry record contains no private payload.

If registry persistence fails after adapter success, display generated name/ID and do not call the adapter again. If configurator opening fails, keep `created` and expose `Open configurator` retry that performs no generation or persistence.

- [ ] **Step 3: Write failing stale/revision tests**

Load records with matching and changed AppID, identity, trainer hash, catalog fingerprint, controller/runtime fingerprint. Assert only the complete match is current. Regeneration requests revision `lastMatchingRevision + 1` and never overwrites or removes prior records.

- [ ] **Step 4: Implement the state machine and confirmation UI**

Use one `busy` flag plus a monotonic operation token to ignore late results after unmount/identity change. The modal lists source name, trainer hash prefix, command/page counts, skipped counts, target input, and `Physical click only`. Its OK handler first re-runs the read-only probe and recomputes the canonical catalog digest, then calls the profile.

- [ ] **Step 5: Add generation diagnostics with tests first**

Allowlist `generation_started`, `generation_completed`, `generation_failed`, `selection_invariant_failed`, `registry_recorded`, and `layout_stale`. Details contain only AppID, revision, page/command counts, runtime/hash prefixes, correlation ID, and bounded result code.

- [ ] **Step 6: Run Task 7 gates and commit**

Run: `node_modules/.bin/vitest.cmd run tests/steam-input-radial-controller.test.ts tests/steam-input-radial-menu.test.ts tests/radial-layout-rpc.test.ts tests/relay-page.test.ts`

Run: `python -m unittest tests_backend.test_diagnostics -v`

Run: `node_modules/.bin/biome.cmd check src tests vitest.config.ts`

Run: `node_modules/.bin/tsc.cmd --noEmit`

Run: `node_modules/.bin/tsc.cmd --noEmit -p tsconfig.test.json`

Expected: all PASS.

Commit: `feat: prepare separate Steam Input radial layouts`

---

### Task 8: Experimental candidate, full gates, and physical validation

**Files:**
- Modify: `package.json`
- Modify: `main.py`
- Modify: `tests_packaging/test_package_layout.py`
- Modify: `README.md`
- Modify: `CONTEXT.md`
- Modify: `docs/GUIA-INSTALACAO-TESTES-E-LOGS.md`
- Modify: `docs/STEAM-DECK-VALIDATION.md`
- Modify: `docs/notes/2026-08-29-trainer-relay-handoff.md`

**Interfaces:**
- Produces: deterministic `TrainerRelay.zip` version `0.1.0-experimental.21`.
- Produces: physical PASS/FAIL evidence without creating a tag or stable release.

- [ ] **Step 1: Make version/package assertions RED**

Change package expectations to `0.1.0-experimental.21` and require the runtime-profile source/build output already included by the normal frontend bundle. Observe failure before changing production version strings.

- [ ] **Step 2: Synchronize version and documentation**

Document left-trackpad physical-click behavior, six-command pagination, explicit Steam review/application, source-layout preservation, stale regeneration, probe/fingerprint limits, diagnostics privacy, fallback, and rollback by reselecting the original layout. State that unsupported Steam client builds expose no generation action.

- [ ] **Step 3: Run every local gate**

Run: `python -m unittest discover -s tests_backend -p "test_*.py"`

Run: `python -m compileall main.py trainer_relay tests_backend scripts`

Run: `node_modules/.bin/biome.cmd check src tests vitest.config.ts`

Run: `node_modules/.bin/tsc.cmd --noEmit`

Run: `node_modules/.bin/tsc.cmd --noEmit -p tsconfig.test.json`

Run: `node_modules/.bin/vitest.cmd run`

Run: `node_modules/.bin/rollup.cmd -c`

Run: `python -m unittest discover -s tests_packaging -p "test_*.py"`

Run: `python scripts/package_trainer_relay.py`

Run: `git diff --check`

Expected: zero failures. Record exact test counts, ZIP entry count, ZIP SHA-256, and version.

- [ ] **Step 4: Inspect archive and install on the Deck**

Verify the ZIP contains no probe raw capture, account data, active layout VDF, or attachment. Install through Decky developer ZIP installation and restart Decky/Steam.

- [ ] **Step 5: Run the physical generation gate**

For BioShock 2:

1. Record the selected source layout identifier and behavior.
2. Prepare the radial layout and verify the preview reports every eligible cheat and expected page count.
3. Generate; confirm the source remains selected and unchanged.
4. Open Steam's configurator, review, and manually apply the generated layout.
5. Touch and release every sector without clicking; assert zero trainer hotkeys.
6. Physically click one cheat per page; assert exactly one corresponding command each.
7. Navigate previous/next across every page; assert no cheat command from navigation.
8. Exercise NumLock, numpad, function-key, and modifier examples.
9. Verify every non-left-trackpad game binding remains identical.
10. Restart Steam and run UniFiDeck Force Sync; assert Trainer Relay does not reapply anything.
11. Reselect the original source layout and verify exact prior behavior.
12. Export diagnostics and inspect privacy boundaries.

- [ ] **Step 6: Record result, handoff, commit, and push**

Update `docs/STEAM-DECK-VALIDATION.md` with each observed PASS/FAIL, Steam client/runtime fingerprint, plugin ZIP hash, and any fallback. Update the handoff with tests, artifact, GitHub state, remaining limitations, rollback, and exact resume step.

Commit: `release: package experimental Steam Input radial menu`

Push `feat/trainer-relay`. Do not create a tag or GitHub Release unless every physical item passes and the user separately authorizes publication.

---

## Execution boundary

Tasks 1–4 can run locally and produce a safe probe build. Task 5 requires the
user's Steam Deck and is a mandatory stop. Tasks 6–8 may proceed only after the
evidence document says `PASS_SAFE_CLONE`. A `FAIL_SAFE_CLONE` result is a valid,
safe terminal outcome: ship or retain the read-only preview/configurator
fallback and do not attempt an alternate private mutation path under this plan.

## Primary API evidence

- Decky's current `Input` type exposes read/edit/save/select calls but leaves
  many payloads opaque and explicitly warns against config-info registration:
  <https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/globals/steam-client/Input.ts>
- Decky's current `App` type exposes `ShowControllerConfigurator(appId)`:
  <https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/globals/steam-client/App.ts>
- Valve documents developer export/dump flows, not external mutation of a
  user's active non-Steam shortcut layout:
  <https://partner.steamgames.com/doc/features/steam_controller/action_manifest_file>
