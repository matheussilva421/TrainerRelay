# Trainer Relay

[![Build](https://img.shields.io/github/actions/workflow/status/matheussilva421/TrainerRelay/trainer-relay-build.yml?branch=main&label=build)](https://github.com/matheussilva421/TrainerRelay/actions/workflows/trainer-relay-build.yml)
[![License: GPL 3.0](https://img.shields.io/github/license/matheussilva421/TrainerRelay)](./LICENSE)

Trainer Relay is an independent [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) plugin for launching Windows trainer sidecars alongside Epic and GOG shortcuts created by [UniFiDeck](https://github.com/mubaraknumann/unifideck).

Trainer Relay is complementary to [CheatDeck](https://github.com/SheffeyG/CheatDeck): keep CheatDeck for games launched directly by Steam, and use Trainer Relay for the supported UniFiDeck shortcuts. Trainer Relay does not modify UniFiDeck, Decky Loader, Proton, or Steam Runtime.

## Status and scope

This repository publishes `v0.1.0-experimental.2`. It is an experimental release pending validation on a physical Steam Deck. The v1 contract is the same Wine prefix, not a formal guarantee that the trainer runs inside the same pressure-vessel container as the game.

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
2. Download **`TrainerRelay.zip`** from the [experimental release](https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.2).
3. In Decky Loader's developer settings, install the downloaded ZIP.

Download the plugin archive, not GitHub's automatically generated `Source code.zip`. Do not try to install or validate the Decky ZIP on Windows; use the package-layout checks in this repository and install it only on the Steam Deck.

## Configure a game

1. Open the UniFiDeck shortcut's game details in Game Mode.
2. Open the **Trainer Relay** menu.
3. Select an absolute Windows `.exe` trainer. Trainer Relay validates that it is a regular file and rejects relative paths, `.bat` files, and arguments.
4. Leave **Enable Trainer Relay** off until the path is selected and any migration prompt has been reviewed.
5. Optionally set an absolute prefix override. When empty, Trainer Relay uses `~/.local/share/unifideck/prefixes/<game_id>`.
6. Enable the relay and launch the shortcut.

Trainer Relay waits for the matching `unifideck-launcher` process, resolves the actual Windows executable from `/proc`, verifies the prefix and launch identity, and then starts the trainer through UniFiDeck's `umu-run` with `PROTON_VERB=runinprefix`. It never invokes a shell or evaluates user-provided command text.

## Legacy launch-option migration

Earlier CheatDeck setups may have used `PROTON_REMOTE_DEBUG_CMD` and `PRESSURE_VESSEL_FILESYSTEMS_RW` in Steam launch options. Trainer Relay can identify these two legacy variables and show the trainer it found before offering migration.

The migration preserves `%command%`, the `epic:<game_id>` or `gog:<game_id>` token, and unrelated launch options. It removes only the two legacy assignments. After saving, Trainer Relay re-reads AppDetails and enables the new configuration only when the expected text is confirmed.

If CheatDeck reintroduces either legacy variable, Trainer Relay fails closed and reports `invalid_config`. Remove or migrate the legacy options before trying again. If the proposed trainer is not the one intended for the shortcut, cancel the migration and configure the path manually.

## Runtime safety

The watcher is deliberately fail-closed:

- zero matching processes means `waiting_for_game`;
- more than one matching candidate means `ambiguous`, and no trainer starts;
- PID reuse is rejected using `/proc/<pid>/stat` start time;
- the game, prefix, environment allowlist, and launch identity must agree;
- a trainer is considered running only after it remains alive for three seconds;
- one automatic retry is allowed after a two-second delay while the same game session remains active;
- later retries require the manual **Retry** action;
- shutdown signals only the process group created by Trainer Relay, waits five seconds, then force-terminates that same group if necessary.

The game is left untouched if the trainer fails, is ambiguous, or exits prematurely. Trainer Relay does not terminate the game, `wineserver`, global UMU processes, or another trainer.

## Diagnostics, privacy, and rollback

The plugin logs state transitions and bounded diagnostics, not complete process environments. It does not intentionally log credentials, cookies, tokens, or raw launch-option values. The environment copied to the trainer is an explicit allowlist; `PROTON_REMOTE_DEBUG_CMD` is never copied and `PROTON_VERB=runinprefix` is set last.

For the physical-device checklist, see [`docs/STEAM-DECK-VALIDATION.md`](docs/STEAM-DECK-VALIDATION.md). For the architectural decision, see [`docs/adr/0001-session-watcher.md`](docs/adr/0001-session-watcher.md).

To roll back, disable the per-game Trainer Relay configuration or uninstall the plugin from Decky Loader. Restore the original CheatDeck setup only after removing the Trainer Relay configuration; the game remains independently launchable throughout.

## Troubleshooting

- **Unsupported shortcut:** confirm the launch options contain exactly one literal `epic:<game_id>` or `gog:<game_id>` token supplied by UniFiDeck.
- **`waiting_for_game`:** launch the shortcut from UniFiDeck and allow the launcher to reach the game process before pressing Retry.
- **`ambiguous`:** close duplicate launcher/game instances and try again. Trainer Relay will not guess.
- **`invalid_config`:** remove the legacy variables, or complete the migration prompt and verify the resulting launch options.
- **`failed`:** confirm the `.exe` is absolute and readable, the prefix exists, and the trainer supports the game's Wine environment.
- **Trainer window not visible:** switch between open windows with the Steam button; this plugin does not force window focus.

Please include the status and diagnostic code when reporting a bug. Do not attach complete `/proc` environments, credentials, or private launch options.

## Acknowledgments

Trainer Relay is derived from the [CheatDeck](https://github.com/SheffeyG/CheatDeck) project by SheffeyG. It is an independent project and is not officially affiliated with or endorsed by CheatDeck, SheffeyG, UniFiDeck, or Decky Loader.

This project is licensed under the [GNU GPL v3 or later](./LICENSE).
