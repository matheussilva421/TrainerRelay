# Resolved glossary

This document is the compact implementation context for the Trainer Relay package. It intentionally separates the supported launch contract from implementation details belonging to UniFiDeck, Proton, and Steam Runtime.

## Launch Identity

The literal `epic:<game_id>` or `gog:<game_id>` argument that identifies a supported UniFiDeck game shortcut.

## Game Session

The unique matching Windows process identified by its PID and `/proc/<pid>/stat` start time. `/proc/<pid>/comm` is only an initial acquisition signal: a game may rename its main thread after startup, so an already anchored session is revalidated by the stable PID/start-time pair together with its executable, prefix, store, and required environment.

## Prefix Anchor

The UniFiDeck compatdata root selected for a launch identity: its configured absolute override, or `~/.local/share/unifideck/prefixes/<game_id>` by default. Proton descendants expose `WINEPREFIX=<root>/pfx`; that transformed child value is valid discovery evidence but must not be passed back to a new `umu-run`. Trainer Relay launches the sidecar with both `WINEPREFIX` and `STEAM_COMPAT_DATA_PATH` set to the selected root. An advanced override that explicitly names the child `pfx` directory is normalized to its parent, while a default game ID literally named `pfx` remains unchanged.

## Owned Sidecar

A trainer process group created and tracked by Trainer Relay; only this group may be terminated by the plugin.

## Container Re-entry

The explicit UMU 1.4.4 contract enabled by `UMU_CONTAINER_NSENTER=1`. The game
launch exposes a pressure-vessel launcher service keyed by the MD5 of the
compatdata-root prefix. The owned sidecar uses the same root and flag so UMU
can call `steam-runtime-launch-client` and run the trainer through that service
with `PROTON_VERB=runinprefix`. A session launched without the flag is rejected
as `container_reentry_missing` and must be restarted after preparation.
Before spawning, Trainer Relay resolves the launch client using UMU's runtime
location precedence and requires the exact bus for that prefix to exist. A
missing, unsupported, or unqueryable service fails closed without a sidecar.

## Legacy Configuration

The existing CheatDeck launch-option assignments, especially `PROTON_REMOTE_DEBUG_CMD` and `PRESSURE_VESSEL_FILESYSTEMS_RW`, which may be migrated only after explicit confirmation and persistence verification.

## Implementation references

- Frontend contract and typed RPC adapter: `src/domain/relay/` and `src/infra/relayRpc.ts`.
- Backend watcher and process ownership: `trainer_relay/watcher.py`, `trainer_relay/process.py`, and `trainer_relay/runner.py`.
- Packaging entry point: `scripts/package_trainer_relay.py`.
- Architecture decision: `docs/adr/0001-session-watcher.md`.
- Physical-device validation: `docs/STEAM-DECK-VALIDATION.md`.

## Explicit boundary

The release promises a shared Wine prefix and uses the explicit container
re-entry behavior implemented by UniFiDeck's bundled UMU 1.4.4. It does not
claim a generic Proton or pressure-vessel API outside that bounded UMU contract.
The watcher validates the game was prepared for re-entry and refuses to guess
when evidence conflicts.
