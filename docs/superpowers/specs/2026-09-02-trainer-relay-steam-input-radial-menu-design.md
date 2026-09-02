# Trainer Relay Steam Input Radial Menu Design

**Date:** 2026-09-02
**Status:** approved in chat; pending written-spec review
**Scope:** assisted generation of a separate Steam Input layout for the built-in Steam Deck controller

## Goal

Let the user prepare a Steam Input radial menu from the cheats already exposed by
Trainer Relay. The generated layout uses the **left trackpad**, selects a radial
item by touch, and sends that item's command only when the user physically
clicks the trackpad. Trainers with more controls are split across multiple
pages.

This is an optional convenience. Trainer Relay's Quick Access controls remain
the primary, version-resilient interface. The feature never silently replaces
the active personal layout and never claims that sending a hotkey changed a
cheat's state.

## Product contract

The first release supports only the built-in Steam Deck controller and a single
supported UniFiDeck shortcut whose current numeric Steam AppID, literal
`epic:<id>` or `gog:<id>` launch identity, trainer SHA-256, and cheat catalog are
stable throughout generation.

The user starts the flow with `Prepare Steam Input radial menu`. Trainer Relay
shows a preview containing:

- the current game and launch identity;
- the source layout name or identifier;
- trainer label and abbreviated SHA-256;
- number of generated command items and radial pages;
- skipped controls and bounded reasons;
- the explicit statement that the left trackpad changes only in the generated
  copy.

After confirmation, Trainer Relay creates a **new personal layout** named:

```text
Trainer Relay — <game> — <trainer hash prefix> — r<revision>
```

The plugin then opens Steam's normal controller configurator. The generated
layout is not selected or applied by Trainer Relay. The user reviews and applies
it through Steam. The source layout remains untouched and is the rollback path.

If the client cannot prove that it can create a separate layout without
altering the selected layout, generation is unavailable and the plugin only
offers `Open Steam controller configurator`.

## Alternatives considered

### Clone into a separate personal layout — selected

Clone the current layout, replace only the left-trackpad binding in the clone,
save the result under a new name, and open the normal configurator. This
preserves the user's game-specific bindings while keeping application and
rollback under explicit user control.

### Create a generic layout from scratch — rejected

A generic template is easier to generate but can discard game-specific
bindings, action sets, gyro, and controller preferences. It does not satisfy the
preservation requirement.

### Mutate or automatically select the active layout — deferred

Steam exposes private editing surfaces to its own UI, but not a public,
versioned contract for Decky plugins. Silent mutation or selection introduces
layout corruption, Steam Cloud conflict, and update-compatibility risks. It is
outside this release and requires a separate experimental design and physical
evidence.

## Architecture

### 1. Pure radial-plan domain

A pure TypeScript module converts a decoded `ReadyCheatControls` snapshot into
an immutable plan. It has no access to Steam globals and is independently
testable.

```ts
interface SteamInputCommandItem {
  itemId: string;
  cheatId: string;
  label: string;
  hotkey: SymbolicHotkey;
}

interface SteamInputRadialPage {
  page: number;
  items: SteamInputCommandItem[];
  previousPage?: number;
  nextPage?: number;
}

interface SteamInputRadialPlanV1 {
  schemaVersion: 1;
  appId: number;
  identity: LaunchIdentity;
  trainerSha256: string;
  catalogFingerprint: string;
  controller: "steam_deck_builtin";
  input: "left_trackpad";
  activation: "physical_click";
  pages: SteamInputRadialPage[];
}
```

The plan accepts only the existing finite symbolic hotkey allowlist. Empty,
invalid, or command-disabled controls are skipped with a bounded reason. One
hotkey creates one radial command. When a cheat exposes multiple valid
alternative hotkeys, each alternative becomes a separate item and its formatted
key is appended to the label so no key choice is hidden.

Labels are normalized to bounded plain text. Item IDs, trainer paths, arbitrary
Steam payloads, and free-form commands are never accepted from the UI.

### 2. Deterministic pagination

Each page reserves eight stable radial sectors. Six sectors hold cheat
commands; the final two are navigation sectors. The previous control is absent
on page 1 and the next control is absent on the last page, but their sector
positions remain reserved so cheat positions never move between revisions.

Navigation changes only the radial page and does not emit a keyboard command.
The plan starts on page 1 whenever the generated layout becomes active. Page
switching is represented through isolated Steam Input action-set pages; every
page inherits or clones the source layout's non-trackpad bindings and differs
only in the left-trackpad radial definition. The concrete adapter must prove
that switching pages does not stack layers or alter other bindings before the
layout is offered.

The physical interaction is fixed:

- touching or moving on the left trackpad selects and previews a sector;
- releasing the finger sends no command;
- physically clicking sends exactly the selected cheat hotkey or page action;
- an unselected click and every empty sector send nothing.

### 3. Steam Input capability adapter

All private Steam client interaction is isolated behind a narrow adapter. No
React component or domain module reads opaque Steam payloads directly.

```ts
interface SteamInputLayoutAdapter {
  probe(appId: number): Promise<SteamInputCapabilityResult>;
  inspectSelectedLayout(appId: number): Promise<SelectedLayoutSnapshot>;
  createSeparateLayout(request: CreateRadialLayoutRequest): Promise<CreatedLayout>;
  openConfigurator(appId: number): Promise<void>;
}
```

The adapter feature-probes the required Steam client methods, built-in
controller identity, source layout identifier, export/clone lifecycle, save
result, and selected-layout identifier. It uses only an explicitly supported
runtime fingerprint backed by captured Steam Deck fixtures and contract tests.
Unknown or changed method shapes fail closed.

`createSeparateLayout` must enforce this sequence:

1. read and retain the selected source-layout identifier;
2. clone/export the source into a new editing target;
3. apply the bounded radial plan only to that target;
4. save under a new personal-layout name;
5. read the selected-layout identifier again;
6. succeed only when the generated layout has a distinct identifier and the
   selected source identifier is unchanged.

If step 5 or 6 cannot be proven, the operation reports failure, records the
generated identifier when available for cleanup, and never attempts a second
save or automatic selection. Direct edits to active VDF files, opaque
protobuf fabrication without a validated fixture, and controller-config
message registrations carrying Decky's breakage warning are prohibited.

### 4. Generated-layout registry

Trainer Relay stores only bounded metadata about layouts it generated. It does
not persist the source layout payload or arbitrary Steam data.

```ts
interface GeneratedRadialLayoutV1 {
  appId: number;
  identity: LaunchIdentity;
  trainerSha256: string;
  catalogFingerprint: string;
  steamRuntimeFingerprint: string;
  sourceLayoutId: string;
  generatedLayoutId: string;
  generatedLayoutName: string;
  revision: number;
  createdAt: string;
}

interface RadialLayoutRegistryV1 {
  schemaVersion: 1;
  layouts: GeneratedRadialLayoutV1[];
}
```

Identifiers and names are length-bounded and decoded strictly. The registry is
separate from `RelayConfigV1` and `CheatControlsConfigV1`. It is updated only
after the adapter proves a distinct saved layout and an unchanged selection.
Registry loss never removes or selects a Steam layout.

A layout becomes stale when AppID, identity, trainer SHA-256, catalog
fingerprint, controller identity, or supported Steam runtime fingerprint
changes. Regeneration creates a higher revision; it never overwrites an earlier
generated layout.

### 5. Frontend flow

The routed Trainer Relay page owns generation. Quick Access may show status and
an `Open configuration` shortcut, but does not start a multi-step generation
while a game command is in flight.

The page states are:

- `unavailable`: unsupported controller/runtime, unstable identity, no source
  layout, or no eligible hotkeys;
- `ready`: a preview can be produced;
- `confirming`: the user is reviewing the exact plan summary;
- `generating`: controls are locked to one operation;
- `created`: a separate layout was proven and the Steam configurator can open;
- `stale`: a previous layout exists but its authority fingerprint changed;
- `failed`: a bounded error occurred and no automatic retry is performed.

The UI never labels radial entries as enabled or disabled. Adapter and manual
controls remain `state unknown`; authoritative cooperative state remains visible
only in Trainer Relay's own live UI because Steam Input menu labels are static.

### 6. Data flow and authority checks

At confirmation and immediately before cloning, the feature re-reads the active
AppID, launch identity, cheat-controls snapshot, trainer SHA-256, catalog
fingerprint, controller identity, source layout identifier, and runtime
fingerprint. Any mismatch invalidates the preview and requires the user to
prepare it again.

The final flow is:

```text
active AppID + AppDetails
        -> strict UniFiDeck identity
        -> decoded cheat controls
        -> pure radial plan and preview
        -> user confirmation
        -> authority revalidation
        -> capability adapter clones separate layout
        -> selection/source invariants verified
        -> bounded registry record
        -> Steam controller configurator opens
        -> user optionally applies the layout
```

No trainer command is sent during preparation, generation, page preview, or
layout selection.

## Failure behavior

- Unsupported Steam client or missing private method: generation unavailable;
  open the normal configurator only.
- Non-built-in controller or no left trackpad: generation unavailable.
- Unsupported shortcut, racing AppID, changed identity, changed trainer hash,
  or changed catalog: invalidate preview and do nothing.
- Unknown trainer build with no manual controls: no eligible radial plan.
- Invalid or unsupported hotkey: skip it and show the bounded reason before
  confirmation.
- Source layout cannot be identified or cloned: abort before save.
- Source selection changes during generation: fail, do not select or retry, and
  surface manual recovery instructions.
- Generated layout is not distinct: fail and do not record it.
- Save succeeds but registry persistence fails: report the generated layout ID
  and name locally in the UI, open no automatic selection path, and allow the
  user to find or remove it in Steam.
- Configurator fails to open: preserve the generated layout record and provide
  a retry button that only reopens the configurator.
- Steam Cloud later changes selection: never reapply automatically.

Every failure leaves the game, trainer, source layout, and selected layout
untouched by Trainer Relay's follow-up actions.

## Diagnostics and privacy

Diagnostics add category `steam_input` with bounded events for probe result,
preview creation, confirmation, authority mismatch, clone start/completion,
selection invariant, registry update, stale detection, and configurator open.

Logs may contain numeric AppID, launch identity, trainer hash prefix, runtime
fingerprint, counts, revision, bounded adapter code, and correlation ID. They
must not contain the full source/generated configuration payload, trainer path,
Steam account identifier, cloud token, environment dump, or arbitrary private
Steam response. The existing 50 MB diagnostic rotation policy remains
unchanged.

## Testing

### TypeScript and Vitest

- eligibility and strict decoding for AppID, identity, trainer hash, controller,
  and runtime capabilities;
- deterministic six-command pagination, stable navigation sectors, empty
  sectors, and multiple-hotkey expansion;
- left-trackpad binding with physical-click activation and no touch-release
  command;
- preservation of every non-left-trackpad binding in captured fixtures;
- source/generated identifier separation and unchanged selected-layout
  invariant;
- authority revalidation immediately before generation;
- stale detection and monotonic revision naming;
- preview, confirmation, busy, failure, created, and configurator-retry states;
- no authoritative cheat-state claim in generated labels;
- strict registry decoding and bounded diagnostics.

The private adapter uses recorded, sanitized fixtures for each explicitly
supported runtime fingerprint. Contract tests fail when required fields or
method shapes change. No generic `any` payload is allowed to escape the adapter.

### Python

- `RadialLayoutRegistryV1` validation, bounded persistence, corruption fallback,
  revision allocation, and no coupling to existing relay/cheat configs;
- diagnostic event allowlist and redaction;
- package inclusion of any versioned, non-secret adapter fixtures required at
  runtime.

### Physical Steam Deck gate

Before release, validate against the exact supported Steam client build:

- current source-layout ID is captured and remains selected after generation;
- generated layout appears only under the intended UniFiDeck shortcut;
- applying it changes only the generated copy's left trackpad;
- touch and release never send a trainer hotkey;
- physical click sends exactly one selected hotkey;
- previous/next navigation reaches every page without sending a cheat;
- NumLock, numpad, function keys, and supported modifiers work with the game in
  focus;
- all non-left-trackpad game controls remain unchanged;
- trainer/game processes and Trainer Relay command semantics remain unaffected;
- restarting Steam and Force Sync do not cause Trainer Relay to reapply a
  layout;
- reselecting the original layout restores the exact prior behavior;
- diagnostics contain no configuration payload or account data.

The feature stays experimental and unavailable by default for unvalidated Steam
runtime fingerprints. Passing unit tests without this physical gate is not
evidence that the layout is installable or functional on the Deck.

## Delivery stages

1. Implement the pure planner, registry, UI preview, diagnostics, and a
   read-only Steam Input capability/source-layout probe.
2. Capture and sanitize the exact runtime/export/edit fixtures on the user's
   Steam Deck without saving or selecting a layout.
3. Implement the isolated clone adapter against that fingerprint and prove the
   source-selection invariants with fixtures.
4. Package an experimental build and run the complete physical gate.
5. Keep unsupported runtimes on the read-only `Open configurator` fallback.

The implementation is not considered complete after stage 1. Functional menu
generation requires stages 2 through 4 on a real Steam Deck.

## Explicit exclusions

- Silent selection, activation, replacement, deletion, or cloud publication of
  a Steam Input layout.
- Direct modification of active Steam VDF files.
- Generic support for external controllers without a left trackpad.
- Touch-release activation; a physical left-trackpad click is the only command
  activator.
- Editing right trackpad, gyro, buttons, triggers, paddles, or game bindings.
- Inferring cheat enabled/disabled state from a Steam Input hotkey.
- XTest, X11/Wayland injection, `uinput`, root privileges, shell/eval, memory
  patching, or a resident helper.
- Automatic cheat activation, automatic layout regeneration, or automatic
  reapplication after Steam/Cloud changes.

## References

- [Valve: Action Manifest Files](https://partner.steamgames.com/doc/features/steam_controller/action_manifest_file)
- [Valve: In-Game Actions File](https://partner.steamgames.com/doc/features/steam_controller/iga_file)
- [Decky frontend Steam Input types](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/globals/steam-client/Input.ts)
- [Decky frontend Steam App types](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/globals/steam-client/App.ts)
- [Trainer Relay research: Steam Input radial-menu automation](../../research/2026-09-02-steam-input-radial-menu-automation.md)
