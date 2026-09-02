# Trainer Relay

[![Build](https://img.shields.io/github/actions/workflow/status/matheussilva421/TrainerRelay/trainer-relay-build.yml?branch=main&label=build)](https://github.com/matheussilva421/TrainerRelay/actions/workflows/trainer-relay-build.yml)
[![License: GPL 3.0](https://img.shields.io/github/license/matheussilva421/TrainerRelay)](./LICENSE)

Trainer Relay is an independent [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) plugin for launching Windows trainer sidecars alongside Epic and GOG shortcuts created by [UniFiDeck](https://github.com/mubaraknumann/unifideck).

Trainer Relay is complementary to [CheatDeck](https://github.com/SheffeyG/CheatDeck): keep CheatDeck for games launched directly by Steam, and use Trainer Relay for the supported UniFiDeck shortcuts. Trainer Relay does not modify UniFiDeck, Decky Loader, Proton, or Steam Runtime.

## Status and scope

The current read-only probe build is `v0.1.0-experimental.21.probe.1`. It remains experimental pending validation on a physical Steam Deck. The v1 contract uses the same Wine prefix plus the explicit container re-entry path implemented by UniFiDeck's bundled UMU 1.4.4. This build also requires UMU's exact re-entry confirmation before reporting the trainer as running.

Supported:

- UniFiDeck shortcuts carrying one literal `epic:<game_id>` or `gog:<game_id>` token.
- One absolute `.exe` trainer per supported shortcut.
- The default UniFiDeck prefix or an explicit absolute prefix override.

Not supported in v1:

- Ubisoft, Amazon, Battle.net, or generic launchers.
- `.bat` files, trainer arguments, multiple simultaneous sessions, or trainer injection.
- Changes to UniFiDeck, Proton, Steam Runtime, or upstream repositories.

## Installation

1. Enable Developer Mode in Steam Deck settings.
2. Download the locally produced **`TrainerRelay.zip`** artifact. No GitHub release/tag for `v0.1.0-experimental.21.probe.1` will be published before the physical Steam Deck gate passes.
3. In Decky Loader's developer settings, install the downloaded ZIP.

Download the plugin archive, not GitHub's automatically generated `Source code.zip`. Do not try to install or validate the Decky ZIP on Windows; use the package-layout checks in this repository and install it only on the Steam Deck.

## Configure a game

1. Open the UniFiDeck shortcut's game details in Game Mode.
2. Open the **Trainer Relay** menu.
3. Use the focused folder button to browse the Deck and select an absolute Windows `.exe` trainer. The path field is read-only; Trainer Relay rejects relative paths, `.bat` files, and arguments.
4. Confirm **Prepare UMU container re-entry**. Trainer Relay adds exactly one
   `UMU_CONTAINER_NSENTER=1` assignment, re-reads AppDetails, and enables only
   after Steam confirms the expected launch options.
5. Optionally set an absolute prefix override. When empty, Trainer Relay uses `~/.local/share/unifideck/prefixes/<game_id>`.
6. If the game was already open, close and relaunch it after preparation.

Trainer Relay resolves the expected executable from UniFiDeck's mapping,
selects the actual Windows process from `/proc`, verifies the prefix and launch
identity, and then starts the trainer through UniFiDeck's `umu-run`. UMU locates
the same-prefix launcher-service bus, re-enters the game's container with
`steam-runtime-launch-client`, and uses `PROTON_VERB=runinprefix`. It never
invokes a shell or evaluates user-provided command text.

## Legacy launch-option migration

Earlier CheatDeck setups may have used `PROTON_REMOTE_DEBUG_CMD` and `PRESSURE_VESSEL_FILESYSTEMS_RW` in Steam launch options. Trainer Relay can identify these two legacy variables and show the trainer it found before offering migration.

The migration preserves `%command%`, the `epic:<game_id>` or `gog:<game_id>`
token, and unrelated launch options. It removes only the two legacy
assignments and adds `UMU_CONTAINER_NSENTER=1`. After saving, Trainer Relay
re-reads AppDetails and enables the new configuration only when the expected
text is confirmed.

If CheatDeck reintroduces either legacy variable, Trainer Relay fails closed and reports `invalid_config`. Remove or migrate the legacy options before trying again. If the proposed trainer is not the one intended for the shortcut, cancel the migration and configure the path manually.

## Cheat controls

When a supported UniFiDeck game is running, the routed game page and Quick
Access panel show the trainer's available controls. Recognized FLiNG builds are
matched by the selected trainer's exact SHA-256; unknown builds expose a manual
fallback bound to that same hash. Manual entries accept a label plus a finite
symbolic key/modifier selector—never raw virtual-key numbers, trainer arguments,
scripts, or shell text.

FLiNG and manual buttons launch a tiny native Win32 `SendInput` helper through
the already verified UMU context. The helper releases the full chord and exits;
it is not a resident third executable. A successful request is displayed as
**Comando enviado; estado desconhecido** because input acceptance cannot prove
that a closed trainer applied the cheat. Only a fresh acknowledgement from a
cooperative trainer may render an authoritative enabled/disabled toggle.

No XTest, X11/Wayland injection, `uinput`, root flag, DLL injection, arbitrary
memory writes, or free-form command input is used. If the running app, trainer
hash, process session, prefix, container bus, helper hash, or cooperative state
cannot be revalidated, the control fails closed and the game is left intact.

## Runtime safety

The watcher is deliberately fail-closed:

- zero matching processes means `waiting_for_game`;
- more than one matching candidate means `ambiguous`, and no trainer starts;
- PID reuse is rejected using `/proc/<pid>/stat` start time;
- the executable-like process name is required for initial acquisition, but a
  previously accepted `PID + starttime` remains valid if the game renames its
  main thread while executable, prefix, store, and required environment stay
  unchanged;
- the game, prefix, environment allowlist, and launch identity must agree;
- the accepted game process must contain `UMU_CONTAINER_NSENTER=1`; otherwise
  the plugin reports `container_reentry_missing` and launches nothing;
- before spawn, the plugin resolves the matching UMU runtime launch client and
  queries it through the Steam/Deck user session bus, never the game's nested
  pressure-vessel bus, and requires the exact same-prefix service to be listed;
  otherwise it reports one bounded `container_reentry_*` result for that game
  session and launches nothing until manual Retry or a new session;
- the `umu-run` sidecar receives the selected UniFiDeck compatdata root, not the
  child process's Proton-expanded `<root>/pfx` value;
- a trainer is considered running only after it remains alive for three seconds;
- one automatic retry is allowed after a two-second delay when the trainer exits
  before the watcher has observed it in `running`, while the same game session
  remains active;
- later retries require the manual **Retry** action;
- shutdown signals only the process group created by Trainer Relay, waits five seconds, then force-terminates that same group if necessary.

The game is left untouched if the trainer fails, is ambiguous, or exits prematurely. Trainer Relay does not terminate the game, `wineserver`, global UMU processes, or another trainer.

## Diagnostics, privacy, and rollback

Experimental `.13` adds a separate **Diagnostics** page. Diagnostic mode is off by default; once enabled it remains enabled across restarts until you turn it off. The page shows the latest 20 sanitized events, storage use, any bounded storage code, and the last TXT export path. The journal rotates through five 10 MiB files for a hard 50 MiB limit.

**Export TXT** writes a timestamped report atomically to `/home/deck/Downloads`. **Clear logs** removes only Trainer Relay's rotating journal and metadata after confirmation; it does not remove exported TXT files. While diagnostic mode is enabled, the same sanitized events appear in CEF DevTools under the filter `[TrainerRelay:diagnostic]`.

Allowed technical values are limited to identity/session anchors, expected and observed executable/prefix paths, trainer and `umu-run` paths, `GAMEID`, `STORE`, `WINEPREFIX`, `PROTONPATH`, bounded counts, exit codes, and timing. The journal rejects complete environments, complete command lines, credentials, cookies, tokens, authorization data, and legacy debug-command content. When a spawned process exits, it may retain at most a 1,024-character sanitized tail from each inherited UMU stdout/stderr pipe; because Proton/Wine children can inherit those pipes, review that small tail before sharing an export. The environment copied to the trainer is a separate explicit allowlist; `PROTON_REMOTE_DEBUG_CMD` is never copied, the UMU-derived `STEAM_COMPAT_CLIENT_INSTALL_PATH` is not replayed, and `PROTON_VERB=runinprefix` is set last.

Cheat-command diagnostics record only bounded event/result codes, command and
cheat identifiers, the existing session anchor, source category, revision and
timing. Capability tokens, full helper output, complete environments, arbitrary
paths supplied by a response, and cooperative endpoint details are not exposed.

For the physical-device checklist, see [`docs/STEAM-DECK-VALIDATION.md`](docs/STEAM-DECK-VALIDATION.md). For the architectural decision, see [`docs/adr/0001-session-watcher.md`](docs/adr/0001-session-watcher.md).

To roll back, disable the per-game Trainer Relay configuration or uninstall the plugin from Decky Loader. Restore the original CheatDeck setup only after removing the Trainer Relay configuration; the game remains independently launchable throughout.

## Troubleshooting

- **Unsupported shortcut:** confirm the launch options contain exactly one literal `epic:<game_id>` or `gog:<game_id>` token supplied by UniFiDeck.
- **Legacy migration blocks a plain Epic/GOG token:** install `v0.1.0-experimental.5` or newer; `.4` incorrectly required `%command%` while planning migration.
- **Controls receive focus but pressing A does nothing:** install `v0.1.0-experimental.12`. In `.11`, the Python package was outside Decky's required `py_modules` directory, so the backend failed to import and the UI remained in a disabled loading state. `.12` repairs the installed layout and reports an unavailable backend after five seconds instead of loading forever. Relay enablement remains fail-closed until legacy launch options are repaired.
- **The game opens but the trainer remains at `waiting_for_game`:** install `.14`, enable the persistent mode on the **Diagnostics** page, reproduce once, then export the TXT. Look for `candidate_rejected` and its bounded reason such as `prefix_mismatch`, `process_name_mismatch`, `store_mismatch`, or `executable_mismatch`. `.14` accepts UniFiDeck's valid `GAMEID=umu-0` while still rejecting UMU wrappers and Wine helper processes.
- **`waiting_for_game`:** launch the shortcut from UniFiDeck and allow the launcher to reach the game process before pressing Retry.
- **`ambiguous`:** close duplicate launcher/game instances and try again. Trainer Relay will not guess.
- **`invalid_config (container_reentry_missing)`:** complete UMU container
  preparation, close the currently running game, and launch it again.
- **`invalid_config (container_reentry_bus_missing)`:** the prepared game did
  not expose the exact same-prefix service after at most five launch-client
  invocations across all host-session candidates; restart it and
  export Diagnostics. `container_reentry_unsupported` or
  `container_reentry_probe_failed` means the runtime/client could not be
  identified or queried safely. `.18` records a bounded failure class, probe
  exit code, attempt count, and bus source without retaining stderr or a full
  environment.
- **Other `invalid_config`:** remove the legacy variables, or complete the migration prompt and verify the resulting launch options.
- **`failed`:** confirm the `.exe` is absolute and readable, the prefix exists, and the trainer supports the game's Wine environment.
- **Trainer window not visible:** switch between open windows with the Steam button; this plugin does not force window focus.

Please include the exported diagnostic TXT, status, and diagnostic code when reporting a bug. Do not attach complete `/proc` environments, credentials, or private launch options.

## Acknowledgments

Trainer Relay is derived from the [CheatDeck](https://github.com/SheffeyG/CheatDeck) project by SheffeyG. It is an independent project and is not officially affiliated with or endorsed by CheatDeck, SheffeyG, UniFiDeck, or Decky Loader.

This project is licensed under the [GNU GPL v3 or later](./LICENSE).
