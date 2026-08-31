# Trainer Relay — cheat introspection feasibility

**Date:** 2026-08-31  
**Scope:** research only; FLiNG trainers first, especially `BioShock 2 Remastered v1.0-Update 2 Plus 15 Trainer`, and the first-party trainers under `C:\Users\slvma\Downloads\Github\Mods`.  
**Safety boundary:** no trainer executable was executed, and no copyrighted FLiNG binary was reverse-engineered in this investigation.

## Executive conclusion

The requested behavior — automatically discovering *every* cheat label, its keyboard shortcut, and its live enabled/disabled state directly from an arbitrary Windows trainer executable — is not a generic capability available through Decky, UniFiDeck, Proton, UMU, or Windows.

The feasible split is:

- **FLiNG:** labels and hotkeys can be supplied by official documentation or a manually curated, version/hash-bound adapter. They cannot be safely and completely inferred from an arbitrary FLiNG `.exe`. Live state is not externally observable through a generic interface.
- **First-party trainers in this repository:** static labels, hotkeys, and coverage are already available from the repository's JSON profiles. Live state is available inside the trainer's own process, but the current trainer does not expose it to Trainer Relay. A small owner-designed manifest plus state/control protocol would make this reliable.
- **Arbitrary other trainers:** show no controls unless a trusted manifest or adapter exists. UI automation and key injection may be offered only as explicitly best-effort actions, never as authoritative discovery or state reporting.

Therefore the product contract should be **manifest-driven introspection**, not “parse every trainer.” The UI must distinguish `known from manifest`, `curated adapter`, `observed through owner protocol`, `best effort`, and `unknown`.

## Capability matrix

| Capability | Arbitrary FLiNG `.exe` | Exact FLiNG adapter | Current first-party trainers | First-party trainer with owner protocol |
|---|---|---|---|---|
| Cheat labels | No reliable source | Yes, static and version-bound | Yes, from profile JSON | Yes |
| Advertised option completeness | No guarantee | Only the covered build/documentation | Profile-defined, not executable-discovered | Yes, if manifest is authoritative |
| Keyboard shortcuts | No generic query | Yes, if documented/confirmed | Yes, from `CheatDefinition.Hotkey` | Yes |
| Current enabled/disabled state | No | No authoritative state | Only inside the trainer | Yes, with acknowledgement/state channel |
| Enable/disable command | No safe generic command | Key injection is best-effort only | Not from current Relay boundary | Yes, with explicit command acknowledgement |
| Proof that the game effect is active | No | No | Trainer-owned memory verification only | Yes, if trainer reports a verified result |

“Process is alive” is not a cheat state. “Key event was injected” is not a successful toggle. A stable UI label is not proof that the corresponding patch exists in the game.

## What the current stack actually exposes

### Trainer Relay and CheatDeck

The current Trainer Relay implementation contains configuration and lifecycle RPCs — `get_relay_config`, `set_relay_game_config`, `get_relay_status`, and `retry_relay` — in `src/infra/relayRpc.ts`. `src/domain/relay/types.ts` contains only the launch identity, trainer path, prefix override, and relay lifecycle states. There is no trainer catalog, cheat command, or cheat-state RPC.

The current `TrainerFilePicker` is intentionally a path selector. This is consistent with the original CheatDeck implementation: [`ToggleFilePicker.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/components/ToggleFilePicker.tsx#L420-L435) accepts a value and `onBrowse`, and its `ToggleFilePicker` render uses a disabled `TextField` plus `DialogButton onClick={onBrowse}` ([`#L478-L608`](https://github.com/SheffeyG/CheatDeck/blob/main/src/components/ToggleFilePicker.tsx#L478-L608)). It does not inspect the selected executable.

CheatDeck's [`LaunchOptionDefinition`](https://github.com/SheffeyG/CheatDeck/blob/main/src/domain/options.ts#L969-L979) and launch-option parser deal with environment, prefix, and argument options. Its context-menu patch routes to the game page through `Navigation.Navigate` ([`patch.tsx`, `spliceArtworkItem`](https://github.com/SheffeyG/CheatDeck/blob/main/src/patch.tsx#L527-L558)). These are launch/UI concerns, not a trainer metadata protocol.

### Decky, UniFiDeck, UMU, Proton, and the container

Decky provides a plugin process, environment variables, Python module loading, and method dispatch. In [`SandboxedPlugin.initialize`](https://raw.githubusercontent.com/SteamDeckHomebrew/decky-loader/main/backend/decky_loader/plugin/sandboxed_plugin.py#L51-L127), it loads the plugin and starts its message server; [`SandboxedPlugin.on_new_message`](https://raw.githubusercontent.com/SteamDeckHomebrew/decky-loader/main/backend/decky_loader/plugin/sandboxed_plugin.py#L178-L200) dispatches calls by method name. No Windows trainer introspection semantics are defined there.

UniFiDeck's [`docs/launch-options.md`](https://github.com/mubaraknumann/unifideck/blob/staging/docs/launch-options.md#how-a-unifideck-game-launches) documents the `store:game_id` token (`epic:<id>`/`gog:<id>`), launcher hand-off, and environment inheritance. It does not define a catalog or state channel for a sidecar. The local Trainer Relay watcher consequently identifies the game/prefix/session; it does not identify cheats.

UMU's [`set_env`](https://raw.githubusercontent.com/Open-Wine-Components/umu-launcher/1.4.4/umu/umu_run.py#L192-L301) prepares `WINEPREFIX`, `STEAM_COMPAT_DATA_PATH`, `PROTONPATH`, and related runtime values. Its [`build_command`](https://raw.githubusercontent.com/Open-Wine-Components/umu-launcher/1.4.4/umu/umu_run.py#L331-L383) can re-enter a matching container service and set `PROTON_VERB=runinprefix`. Proton's [`init_session`](https://raw.githubusercontent.com/ValveSoftware/Proton/experimental_11.0/proton#L1558-L1568) establishes the Wine prefix, [`run_proc`](https://raw.githubusercontent.com/ValveSoftware/Proton/experimental_11.0/proton#L1902-L1905) executes a structured process, and the `runinprefix` branch runs Wine with the supplied arguments ([`#L1962-L1978`](https://raw.githubusercontent.com/ValveSoftware/Proton/experimental_11.0/proton#L1962-L1978)). None of these APIs describe a trainer's controls or internal state.

Valve's Steam Runtime design documentation describes container/runtime separation ([`possible-designs.md`](https://github.com/ValveSoftware/steam-runtime/blob/master/doc/possible-designs.md)). Re-entering the same prefix/container improves execution compatibility; it does not create an introspection API.

## FLiNG: BioShock 2 Remastered focus

FLiNG's first-party archive lists **BioShock 2 Remastered Trainer** as a trainer entry ([official archive](https://flingtrainer.com/uncategorized/my-trainers-archive/comment-page-2/#list-of-trainers)). That is human-facing documentation and an archive index, not a machine-readable manifest contract. The official material does not give Trainer Relay a supported way to query an already-running trainer for its full catalog or state.

The repository contains the following local evidence, which must be treated as adapter input rather than as FLiNG-owned metadata:

- `Games/Bioshock2Remastered/Trainer/profiles/bioshock2-fling.json` has six profile entries: Infinite Health, Infinite EVE, Infinite Items/Ammo, No Reload, Infinite Money, and Infinite ADAM. It stores local `Name` and `Hotkey` fields and descriptions that associate the mapping with FLiNG behavior.
- `Games/Bioshock2Remastered/Trainer/profiles/bioshock2-fling-replay.json` adds a local Max Wallet entry and marks several other features as not reproduced. Its hotkey values are `auto`, so it cannot be used as a discovered FLiNG keyboard map.
- `Games/Bioshock2Remastered/fling-report.json` is a derived local static-analysis report. It lists imported Windows APIs, virtual-key values, and process names, but it is not an official FLiNG manifest and does not prove that an option is active in the game.
- `Games/Bioshock2Remastered/Trainer/README.md` and `Games/Bioshock2Remastered/README.md` explicitly document the replay prototype as rejected/research-only and warn that static extraction or compilation does not validate in-game behavior.

### Verified local FLiNG inventory and wrapper evidence

Static file hashing found two distinct FLiNG builds in the local `Mods` repository:

- BioShock 2 Remastered +15: SHA-256 `313CE3E30029BC88A27113ED2224AB8F66A8D62C82670C3508BD60AF07157401`;
- BioShock Infinite +15: SHA-256 `4AED63DB45D25CC61ACC94369F60C841C9F4252B86F88B4760B259F1AB552474`.

`Tools/FlingDeckWrapper` already models the useful adapter boundary. Its `FlingProfile` binds a vendor filename, window title, expected SHA-256, 15 named options, their key chords, and `Home` as disable-all. Its tests verify the exact option sets and hashes for both local binaries. The wrapper sends known chords through `SendInput`; its own UI explicitly says `estado do cheat não é observável`. This is direct repository evidence that the static catalog is reusable, but a stateful Decky toggle cannot be inferred from that wrapper.

The current static extractor at `Tools/Bioshock2FlingExtract/extract_fling.py` was also exercised without launching either trainer. Both files reached the PE import parser and failed with `NameError: name 'thunk_rva' is not defined`. The previously generated `Games/Bioshock2Remastered/fling-report.json` remains historical evidence, but the broken extractor must not become a production discovery path until it is repaired under tests and its output is validated independently.

There is also an important mapping ambiguity: the local FLiNG-derived profile displays `F1`–`F6`, while its descriptions refer to FLiNG `Numpad1`–`Numpad6` virtual keys. Trainer Relay must not silently normalize these into a claim about the original executable. An exact BioShock 2 adapter could display the documented/confirmed key as `Numpad1`, etc., record the source and trainer hash, and require user confirmation; it still could not claim live `enabled`/`disabled` state without cooperation from the trainer.

The local replay profile also demonstrates why “discover every cheat” is not equivalent to finding strings or a key table: it separates reproduced and unreproduced features and identifies dependencies such as a speed-hack component. A curated adapter needs explicit coverage and exclusions.

## First-party trainers under `Mods`

The source tree has editable profile families for BioShock 2 Remastered, BioShock Remastered, Crysis 2 Remastered, Crysis 3 Remastered, Forza Horizon 3, and The Evil Within (including separate Steam/Epic profiles). Excluding release copies, the local inventory contains 9 JSON profiles with 61 declared cheat entries. The source profiles are declarative and safe to read without running a trainer.

In `Games/Bioshock2Remastered/Trainer/src/TrainerProfile.cs`:

- `TrainerProfile.Load` and `LoadFromJson` load a profile;
- `TrainerProfile.Cheats` is the catalog;
- `CheatDefinition` contains `Id`, `Name`, `Hotkey`, `ActionType`, patch/signature fields, `Description`, and related behavior metadata.

In `Games/Bioshock2Remastered/Trainer/src/MainForm.cs`:

- `BuildCheatList` creates the visible cards from `_profile.Cheats`;
- `RegisterHotkeys` registers each profile hotkey;
- `WndProc` handles `WM_HOTKEY` and maps it to a `CheatRuntime`;
- `CheatRuntime.IsEnabled` is an in-process boolean;
- `InspectCheatForDebug` reads the game memory and compares expected/applied bytes;
- `CreateCheatCard`, `RequestCheatState`, `ToggleCheat`, and `UpdateRuntimeUi` connect the buttons, memory operation, and displayed state.

`Games/Bioshock2Remastered/Trainer/src/NativeMethods.cs` declares the Win32 hotkey and process-memory primitives. This is strong evidence for a first-party integration: the owner already has the labels, keys, and the code that verifies its own patch. It is not evidence that an external Decky plugin can query those values from the running process.

The safe way to support these trainers is to publish a versioned manifest derived from the same profile, then add an explicit owner-controlled state channel. The trainer should report a session identifier, catalog version, command acknowledgement, and a state such as `enabled`, `disabled`, `failed`, or `unknown`; it should keep memory verification inside the trainer that owns the patch. Relay should never reimplement the trainer's memory logic.

## Why generic Windows mechanisms do not solve this

### Registered hotkeys and key injection

The Windows [`RegisterHotKey`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey) contract lets a process register a `(window/thread, id, modifiers, virtual-key)` combination and receive `WM_HOTKEY`. It does not provide a supported enumeration API for another process's registrations. [`GetAsyncKeyState`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getasynckeystate) reports physical key state and explicitly warns that the recent-press bit is unreliable under preemptive multitasking. [`SendInput`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput) inserts keyboard/mouse events subject to focus and UIPI restrictions; a successful insertion is not a trainer acknowledgement.

Consequences:

- Relay cannot discover a trainer's hotkey table by asking User32.
- Relay can at most send a known key to a known adapter and report `requested`.
- Focus, virtual-key layout, controller-to-keyboard translation, duplicate bindings, and trainer UI state can all make injection ambiguous.

### UI Automation

Microsoft UI Automation provides programmatic access to UI elements **when the application exposes an appropriate provider** ([UI Automation overview](https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiauto-win32)). Control patterns expose supported behavior such as `Invoke`, properties, events, and state ([control patterns](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-controlpatternsoverview)). Custom controls can expose little or nothing; a visible trainer window therefore does not imply a complete automation tree.

UI Automation can be a diagnostic fallback for labels, buttons, and a visible checked/unchecked indicator if a particular trainer exposes them. It cannot reliably discover hidden options, registered hotkeys, memory patches, or whether the game effect succeeded. It is unsuitable as the default FLiNG integration, especially for custom-rendered or minimized trainers.

### Process/memory inspection and binary analysis

Reading another process's memory can detect a *known* patch for a *known* game/build, but it cannot reconstruct a complete semantic catalog, the original UI labels, or the trainer's intended hotkey behavior. It is version-sensitive, affected by Wine/container boundaries, and risks conflicting with the trainer's ownership of patch lifecycle.

For FLiNG, binary parsing, decompilation, patch extraction, and memory probing are explicitly excluded from this scope. For first-party trainers, the owner may continue verifying its own patches internally and expose the result through a designed protocol. Trainer Relay should not turn arbitrary `.exe` files into memory-inspection targets.

## Recommended product contract

1. **Static catalog:** accept only a trusted manifest/adapter. Bind it to game identity, trainer filename, version when known, and preferably a SHA-256. For the BioShock 2 FLiNG case, use a manually reviewed adapter with explicit provenance and coverage; do not label it “discovered from the executable.”
2. **First-party catalog:** generate or ship a manifest from `TrainerProfile`/`CheatDefinition` at build time. Include labels, canonical hotkey display, supported game build, conflicts, dependencies, and unsupported/unknown entries.
3. **Live state:** add a first-party protocol only to trainers whose source is owned. The protocol must acknowledge the same session, expose state timestamps, and distinguish `unknown`/`stale` from `disabled`. A log line alone is not a state API.
4. **Controls:** expose enable/disable buttons only when the adapter has a defined command path. For FLiNG without cooperation, a known hotkey may be offered as “send key / result unknown,” not as a stateful toggle.
5. **Fail closed:** no manifest or adapter means no cheat controls. Do not infer state from trainer process lifetime, window text, key injection return value, or an unverified memory pattern.
6. **Diagnostics:** log metadata provenance, adapter/hash match, command requested, acknowledgement (if any), and state age. Never export complete process environments, credentials, or arbitrary trainer output.

## Final verdict

Automatic introspection is **feasible for the user's own trainers after adding an explicit manifest and runtime protocol**. It is **partially feasible for the exact FLiNG BioShock 2 trainer only as a curated static adapter** based on first-party documentation and user confirmation. It is **not feasible or safe as a generic executable feature**, and the live enabled/disabled state cannot be promised for FLiNG.

This report recommends changing the feature request from “discover every cheat directly from the trainer” to “show a trusted catalog and live state only when the trainer publishes one.” That preserves the convenient Decky UI while keeping unknown FLiNG behavior, Wine/Proton boundaries, and game safety explicit.

## Primary-source ledger

- FLiNG official archive: <https://flingtrainer.com/uncategorized/my-trainers-archive/comment-page-2/>
- CheatDeck `ToggleFilePicker`: <https://github.com/SheffeyG/CheatDeck/blob/main/src/components/ToggleFilePicker.tsx>
- CheatDeck `options.ts`: <https://github.com/SheffeyG/CheatDeck/blob/main/src/domain/options.ts>
- CheatDeck `patch.tsx`: <https://github.com/SheffeyG/CheatDeck/blob/main/src/patch.tsx>
- Decky Loader `SandboxedPlugin`: <https://raw.githubusercontent.com/SteamDeckHomebrew/decky-loader/main/backend/decky_loader/plugin/sandboxed_plugin.py>
- UniFiDeck `docs/launch-options.md`: <https://github.com/mubaraknumann/unifideck/blob/staging/docs/launch-options.md>
- UMU `umu/umu_run.py` 1.4.4: <https://raw.githubusercontent.com/Open-Wine-Components/umu-launcher/1.4.4/umu/umu_run.py>
- Valve Proton `proton` (`experimental_11.0`): <https://raw.githubusercontent.com/ValveSoftware/Proton/experimental_11.0/proton>
- Valve Steam Runtime `doc/possible-designs.md`: <https://github.com/ValveSoftware/steam-runtime/blob/master/doc/possible-designs.md>
- Microsoft `RegisterHotKey`: <https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey>
- Microsoft `GetAsyncKeyState`: <https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getasynckeystate>
- Microsoft `SendInput`: <https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput>
- Microsoft UI Automation overview: <https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiauto-win32>
- Microsoft UI Automation control patterns: <https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-controlpatternsoverview>
