# Resolved glossary

This document is the compact implementation context for the Trainer Relay package. It intentionally separates the supported launch contract from implementation details belonging to UniFiDeck, Proton, and Steam Runtime.

## Launch Identity

The literal `epic:<game_id>` or `gog:<game_id>` argument that identifies a supported UniFiDeck game shortcut.

## Game Session

The unique matching Windows process identified by its PID and `/proc/<pid>/stat` start time.

## Prefix Anchor

The Wine prefix selected for a launch identity: its configured absolute override, or `~/.local/share/unifideck/prefixes/<game_id>` by default.

## Owned Sidecar

A trainer process group created and tracked by Trainer Relay; only this group may be terminated by the plugin.

## Legacy Configuration

The existing CheatDeck launch-option assignments, especially `PROTON_REMOTE_DEBUG_CMD` and `PRESSURE_VESSEL_FILESYSTEMS_RW`, which may be migrated only after explicit confirmation and persistence verification.

## Implementation references

- Frontend contract and typed RPC adapter: `src/domain/relay/` and `src/infra/relayRpc.ts`.
- Backend watcher and process ownership: `trainer_relay/watcher.py`, `trainer_relay/process.py`, and `trainer_relay/runner.py`.
- Packaging entry point: `scripts/package_trainer_relay.py`.
- Architecture decision: `docs/adr/0001-session-watcher.md`.
- Physical-device validation: `docs/STEAM-DECK-VALIDATION.md`.

## Explicit boundary

The release promises a shared Wine prefix selected from UniFiDeck's game mapping. It does not promise generic attachment to the game's pressure-vessel container because Proton and Steam Runtime do not expose a stable public API for that operation. The watcher therefore validates only the evidence available to the plugin and refuses to guess when evidence conflicts.
