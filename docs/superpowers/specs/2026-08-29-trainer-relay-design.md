# Trainer Relay Design

## Goal

Trainer Relay is a Decky Loader plugin derived from CheatDeck and published as
an independent product. It configures and owns trainer sidecars only for Epic
and GOG shortcuts created by UniFiDeck. CheatDeck remains responsible for
games whose Windows executable is launched directly by Steam.

## Contract

- A supported launch identity is exactly `epic:<game_id>` or `gog:<game_id>`.
- A supported shortcut executes `unifideck-launcher` and contains one supported
  launch identity as a literal argument.
- The v1 compatibility contract is the same Wine prefix plus the explicit
  launcher-service re-entry implemented by UniFiDeck's bundled UMU 1.4.4.
- A game session is the unique matching Windows process identified by PID and
  `/proc/<pid>/stat` start time.
- Trainer failure must never prevent, terminate, or modify the game session.
- Trainer Relay may terminate only the process group it created.

## Configuration and UI

Configuration schema version 1 stores one entry per launch identity with an
enabled flag, absolute `.exe` trainer path, and optional absolute prefix
override. Unsupported shortcuts display an explanation and no controls.

Supported shortcuts expose trainer selection, enablement, prefix override,
sanitised diagnostics, current state, and manual retry. States are `disabled`,
`waiting_for_game`, `launching`, `running`, `retrying`, `failed`, `ambiguous`,
and `invalid_config`.

When legacy CheatDeck assignments are present, the UI offers a confirmed
migration. Migration removes only `PROTON_REMOTE_DEBUG_CMD` and
`PRESSURE_VESSEL_FILESYSTEMS_RW`, preserves all unrelated source, re-reads
Steam AppDetails, and enables the relay only after verifying the persisted
launch options.

After a trainer is selected, the same verified write path ensures the shortcut
has exactly one `UMU_CONTAINER_NSENTER=1` assignment. A game that was already
running before preparation must be restarted.

## Runtime

The backend reads `~/.local/share/unifideck/games.map`, derives the default
prefix `~/.local/share/unifideck/prefixes/<game_id>`, and polls `/proc` once per
second. A candidate must match the expected executable, expected prefix,
required environment, and stable PID start time. Zero candidates means wait;
multiple candidates means fail closed as ambiguous.
The game process must also prove it inherited `UMU_CONTAINER_NSENTER=1`;
otherwise discovery reports `container_reentry_missing` and launches nothing.

The backend resolves UniFiDeck's bundled `umu-run`, falling back to PATH only
when the result is unique. It copies an allowlisted environment, removes
`PROTON_REMOTE_DEBUG_CMD`, sets `PROTON_VERB=runinprefix`, and launches the
trainer without a shell in a new process group.
It removes inherited launcher-service state, sets
`UMU_CONTAINER_NSENTER=1`, and lets UMU 1.4.4 re-enter the same-prefix
pressure-vessel service with `steam-runtime-launch-client`.

A trainer that survives three seconds is running. Premature exit triggers one
automatic retry after two seconds while the same game session remains alive.
Further retries are manual. On game exit or plugin unload, the owned process
group receives SIGTERM, then SIGKILL after five seconds if necessary.

## Release boundary

The initial release is `v0.1.0-experimental.1`. Local automated gates and ZIP
inspection must pass before publication. Stable promotion additionally
requires guided tests on a real Steam Deck with one Epic and one GOG title.
No upstream PR is part of this work.
