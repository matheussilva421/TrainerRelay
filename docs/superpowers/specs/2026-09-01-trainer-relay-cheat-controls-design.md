# Trainer Relay Cheat Controls Design

**Date:** 2026-09-01  
**Status:** approved for implementation  
**Scope:** Decky sidebar cheat controls for a running Trainer Relay session

## Goal

Let the user trigger known FLiNG trainer hotkeys and user-defined fallback hotkeys from the Decky sidebar without keeping a third Windows process resident. The same interfaces also admit cooperative trainers that can report authoritative state, but the release must never infer state from a successful key injection.

## Product contract

Trainer Relay exposes controls only for the single stable game session it already owns. A command is accepted only when all of the following remain true at dispatch time:

- the relay identity is a literal `epic:<id>` or `gog:<id>`;
- the relay status is `running`;
- the game session still has the same PID and `/proc/<pid>/stat.starttime`;
- the configured trainer process still belongs to Trainer Relay;
- the effective Wine prefix and verified UMU container-reentry bus still match the running session;
- the selected cheat resolves to a bounded, validated command.

If any condition fails, nothing is launched and the RPC returns a bounded diagnostic code.

### FLiNG and manual controls

For a recognized FLiNG build, Trainer Relay calculates SHA-256 over the configured trainer and resolves an exact hash-bound adapter. The adapter supplies display names and normalized hotkeys. Unknown hashes fail closed for automatic discovery.

The user can add manual controls for an unrecognized or incompletely catalogued trainer. Each manual control is bound to the current trainer SHA-256. Replacing the trainer makes those controls unavailable until the user explicitly recreates or rebinds them. Manual controls contain only a label and a normalized hotkey; they cannot contain executable paths, command-line arguments, scripts, shell text, or arbitrary virtual-key numbers.

Both FLiNG and manual controls are command-only. After a successful helper exit the UI displays `Comando enviado; estado desconhecido`. It never displays enabled or disabled.

### Cooperative controls

A future or user-owned trainer may expose the versioned `TrainerRelay Cooperative Control v1` protocol. Its descriptor provides trainer/build identity, a bounded cheat catalog, supported operations, current states, monotonic revision, and a per-session capability token. Commands receive an acknowledgement tied to a command ID and state revision.

Only an acknowledgement from that trainer may produce `enabled` or `disabled`. Missing, malformed, stale, unauthenticated, or mismatched protocol data produces `unknown` and disables authoritative toggles. This implementation supplies the Relay-side model and transport boundary; legacy trainers remain command-only until they implement the protocol.

## Architecture

### 1. Catalog and persistence

`CheatControlsConfigV1` is stored separately from `RelayConfigV1` so existing relay configurations do not migrate or become unreadable.

```ts
type HotkeyModifier = "ctrl" | "alt" | "shift";

interface NormalizedHotkey {
  modifiers: HotkeyModifier[];
  key: string;
}

interface ManualCheatControl {
  id: string;
  label: string;
  hotkey: NormalizedHotkey;
}

interface ManualTrainerControls {
  trainerSha256: string;
  cheats: ManualCheatControl[];
}

interface CheatControlsConfigV1 {
  schemaVersion: 1;
  games: Record<LaunchIdentity, ManualTrainerControls>;
}
```

IDs are backend-generated lowercase UUIDs. Labels are trimmed UTF-8 text of 1–80 characters with control characters rejected. Each identity may store at most 64 manual controls.

The key allowlist is symbolic and finite: `A`–`Z`, `0`–`9`, `F1`–`F24`, `NUMPAD0`–`NUMPAD9`, `MULTIPLY`, `ADD`, `SUBTRACT`, `DECIMAL`, `DIVIDE`, `INSERT`, `DELETE`, `HOME`, `END`, `PAGEUP`, `PAGEDOWN`, `UP`, `DOWN`, `LEFT`, `RIGHT`, `SPACE`, `TAB`, `ENTER`, `BACKSPACE`, `PAUSE`, `CAPSLOCK`, `SCROLLLOCK`, and `NUMLOCK`. Modifiers are a duplicate-free canonical subset ordered `ctrl`, `alt`, `shift`.

Static adapters live in a versioned JSON catalog packaged read-only with the plugin. Each record contains adapter ID, exact SHA-256, PE architecture, trainer label, optional supported launch identities, and cheat descriptors. Duplicate IDs, hashes, or cheat IDs invalidate the whole catalog at startup.

### 2. Ephemeral Windows input helper

`TrainerRelay.InputHelper.exe` is a small native Win32 console application built for x86 and x64. It accepts only structured numeric arguments produced by the backend:

```text
TrainerRelay.InputHelper.exe --protocol 1 --key <allowlisted VK> --modifiers <bitmask> --hold-ms 40
```

The helper validates every argument, creates a deterministic `INPUT` array, presses modifiers in canonical order, presses the main key, waits 40 ms, releases the main key, releases modifiers in reverse order, and exits. On a partial `SendInput`, it sends a best-effort release sequence before returning a non-zero bounded exit code. It emits one bounded JSON line containing protocol version, accepted input count, expected input count, and result code. It does not inspect processes, accept paths, open sockets, remain resident, or use XTest.

Both PE files are packaged under `bin/`. The backend selects architecture from the configured trainer's PE header and validates the packaged helper SHA-256 against a generated manifest before launching it.

### 3. Command runner

The backend launches the helper with `shell=False` through the same resolved `umu-run`, effective prefix, Proton path, host D-Bus session, `UMU_CONTAINER_NSENTER=1`, and `PROTON_VERB=runinprefix` already verified for the trainer. The helper runs in its own Linux process group owned by Trainer Relay and has a five-second timeout. Timeout or cancellation terminates only that helper group.

The runner requires the expected container re-entry marker, a zero exit code, valid bounded JSON, and equal accepted/expected counts. These prove only that Wine accepted the input events, not that the trainer applied a cheat.

At most one command may be in flight for an identity. A second command returns `command_busy`. The backend records correlation ID, adapter/manual source, bounded result, duration, and session identity without recording the trainer path, environment, capability token, or arbitrary stdout/stderr.

### 4. RPCs

The backend adds typed, sanitised RPCs:

- `get_cheat_controls({ identity })`
- `add_manual_cheat_control({ identity, trainerSha256, label, hotkey })`
- `remove_manual_cheat_control({ identity, cheatId })`
- `send_cheat_command({ identity, cheatId })`

`get_cheat_controls` returns one of `unavailable`, `waiting`, or `ready`. A ready response includes the exact trainer SHA-256, source (`adapter`, `manual`, or `cooperative`), descriptors, capability flags, and bounded per-cheat state.

`send_cheat_command` returns:

```ts
interface CheatCommandResult {
  commandId: string;
  identity: LaunchIdentity;
  cheatId: string;
  outcome: "requested" | "failed" | "rejected";
  state: "unknown" | "enabled" | "disabled";
  diagnostic: { code: string } | null;
}
```

FLiNG/manual success is `outcome: "requested", state: "unknown"`. Only a valid cooperative acknowledgement may return enabled or disabled.

### 5. Decky UI

The routed game configuration page gains a `Cheat controls` section showing catalog source, trainer hash prefix, and manual-control management. Adding a manual control uses Decky-native focused fields and a finite key selector; no free-form path or command field exists.

The Quick Access sidebar becomes session-aware. When exactly one relay session is running it lists its cheats as native `ButtonItem` rows. FLiNG/manual rows show the label, hotkey, and last bounded result. Cooperative rows may use toggles only while authoritative state is fresh. When zero or multiple eligible sessions exist, the sidebar is read-only and explains why.

All controls remain controller/touch accessible. A button disables while its command is in flight. Errors are surfaced as bounded user messages and diagnostic codes.

### 6. Diagnostics

The diagnostic recorder adds category `command` and allowlisted events for catalog load/rejection, manual-control changes, command rejection, helper spawn/completion/timeout, and cooperative acknowledgement/staleness. Exported logs contain no environment dump, absolute trainer path, capability token, or helper raw output.

## Failure behavior

- Unknown trainer hash: automatic catalog unavailable; manual fallback remains possible after explicit creation.
- Changed trainer hash: old manual controls are hidden and commands rejected.
- Missing/corrupt helper or manifest mismatch: command rejected before UMU.
- Session ended/recycled/ambiguous: command rejected before UMU.
- UMU re-entry missing: command rejected without launching a fallback outside the container.
- Helper timeout/non-zero/malformed output: helper group is stopped, trainer and game remain untouched.
- Input accepted but cheat unchanged: UI remains `unknown`; this is not reported as success of the cheat.
- Cooperative protocol stale or invalid: fall back to command-only controls only if a separately valid adapter/manual definition exists; otherwise disable controls.

## Testing

Python unit and integration tests cover hotkey normalization, config persistence, exact-hash catalog resolution, PE architecture selection, helper manifest verification, session gating, structured argv, no-shell execution, one-command concurrency, timeout group ownership, bounded output parsing, sanitized diagnostics, and cooperative acknowledgement freshness.

C helper tests cover valid sequences, argument rejection, partial-send cleanup, bounded JSON, and x86/x64 PE generation. They use an injectable `SendInput` boundary for host tests; the physical Wine behavior remains a Steam Deck gate.

Vitest covers RPC decoders, manual editor validation, native focused rows, session-aware sidebar states, disabled/busy behavior, and the distinction between `requested/unknown` and authoritative cooperative states.

Packaging tests require both helper PEs, their manifest, the adapter catalog, deterministic archive entries, and matching plugin versions. CI builds both helpers before frontend/package gates.

Physical Steam Deck validation requires one recognized FLiNG build and one manual control. The test proves: only an ephemeral third process, correct UMU re-entry, key delivery, no stuck modifiers, game/trainer survival on failure, helper cleanup, and `unknown` UI semantics. Cooperative `enabled/disabled` is not considered validated until a modified trainer implements and passes the v1 protocol.

## Explicit exclusions

- XTest, X11 injection, Wayland injection, `uinput`, root privileges, and Decky root flags.
- Arbitrary scripts, shell/eval, trainer arguments, arbitrary virtual-key numbers, or memory patching by Trainer Relay.
- Claiming FLiNG cheat state from `SendInput` return values.
- Keeping a generic Windows helper resident.
- Automatically enabling cheats at game start.
- Modifying FLiNG binaries.
