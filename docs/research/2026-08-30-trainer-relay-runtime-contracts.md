# Trainer Relay runtime contracts — primary-source research

Date: 2026-08-30

## Question

Which process and runtime signals are safe to use when Trainer Relay launches a
Windows trainer beside a UniFiDeck game, and what explains the BioShock 2
session ending immediately after the trainer was spawned?

## Findings

### `/proc/<pid>/comm` is mutable, not a session identity

Linux exposes a thread's `comm` value through `/proc/<pid>/comm`. A thread can
change this value, threads in one process may have different values, and Linux
truncates it to 15 visible characters. Therefore `comm` is useful as a strict
initial discriminator, but it cannot invalidate an already established game
session by itself. The stable identity in Trainer Relay remains the PID plus
field 22 (`starttime`) from `/proc/<pid>/stat`.

Primary source:

- [Linux `proc_pid_comm(5)`](https://man7.org/linux/man-pages/man5/proc_pid_comm.5.html)

The physical diagnostic export confirms this exact behavior. PID `57719` with
start time `2457048` was accepted twice as `Bioshock2HD.exe`; the executable,
prefix, store, and required environment stayed unchanged, but `comm` became
`Main Game Threa`. The old watcher then emitted `session_ended` and terminated
only its trainer group.

### UniFiDeck treats inherited wrapper environment as insufficient evidence

UniFiDeck's own `/proc` scanner documents that `WINEPREFIX` is inherited by the
whole UMU chain, including Python, pressure-vessel, and other wrappers. Its
scanner therefore scopes by exact `WINEPREFIX` and extracts a Windows `.exe`
image from process command-line data rather than treating every environment
match as a game process. This supports Trainer Relay's fail-closed initial
acquisition: prefix and environment alone are not enough.

Primary sources:

- [UniFiDeck `wrapper_clients.py`](https://github.com/mubaraknumann/unifideck/blob/staging/py_modules/unifideck/launcher/proton/handlers/wrapper_clients.py)
- [UniFiDeck launch-options contract](https://github.com/mubaraknumann/unifideck/blob/staging/docs/launch-options.md)
- [UniFiDeck Proton environment builder](https://github.com/mubaraknumann/unifideck/blob/staging/py_modules/unifideck/launcher/proton/infrastructure/core.py)

UniFiDeck also owns `PROTONPATH`, `WINEPREFIX`, `GAMEID`, `STORE`, and
`PROTON_VERB` for the actual launch. `GAMEID` may be the generic `umu-0`, so the
shortcut's GOG/Epic identifier must not be equated with the UMU database ID.

### `runinprefix` is the correct sidecar verb

UMU documents that a second executable in an already active Wine prefix must
use `PROTON_VERB=runinprefix` or `run`; it also warns that the remaining Proton
configuration should match the first process. Proton and GE-Proton implement
`runinprefix` by invoking Wine directly inside the selected compatibility
prefix rather than waiting for a fresh wineserver lifecycle.

Primary sources:

- [UMU FAQ: multiple processes in one prefix](https://github.com/Open-Wine-Components/umu-launcher/wiki/Frequently-asked-questions-%28FAQ%29)
- [UMU manual](https://github.com/Open-Wine-Components/umu-launcher/blob/main/docs/umu.1.scd)
- [Valve Proton source](https://github.com/ValveSoftware/Proton/blob/experimental/proton)
- [GE-Proton source](https://github.com/GloriousEggroll/proton-ge-custom/blob/master/proton)

Trainer Relay consequently copies only approved runtime categories from the
accepted game process, removes `PROTON_REMOTE_DEBUG_CMD`, and assigns
`PROTON_VERB=runinprefix` last. It invokes `[umu-run, trainer.exe]` with
`shell=False` in a process group it owns.

### The supported boundary remains the Wine prefix

UMU creates a Steam Runtime container for its invocation. No cited public
contract offers a generic way for an unrelated Decky backend to attach a new
host process to an already-running pressure-vessel container. The defensible
v1 promise is therefore same Wine prefix and equivalent Proton/UMU settings,
not formal identity with the game's existing container.

Primary sources:

- [UMU project description](https://github.com/Open-Wine-Components/umu-launcher)
- [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader)
- [Decky plugin template and ZIP layout](https://github.com/SteamDeckHomebrew/decky-plugin-template)

## Implementation consequence

1. Acquire a new session strictly: executable, full resolved executable path,
   prefix, store, required environment, and stable PID/start time must agree.
2. Revalidate an acquired session by the same stable signals. Permit `comm` to
   change only for the exact previously accepted PID/start-time pair.
3. Do not extend that exception to another PID or a recycled start time.
4. Preserve ambiguity and legacy-option checks; a second valid session still
   fails closed.
5. Emit a bounded `candidate_revalidated` event so physical validation can
   distinguish a legal thread rename from a new process or session loss.

This is a narrow correction to session revalidation. It does not loosen
initial wrapper filtering, alter UniFiDeck, or claim pressure-vessel attachment.
