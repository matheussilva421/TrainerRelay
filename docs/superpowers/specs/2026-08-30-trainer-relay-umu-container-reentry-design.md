# Trainer Relay UMU container re-entry design

Date: 2026-08-30
Status: implemented locally; physical validation pending

## Evidence and problem

Trainer Relay `.16` found and retained the correct BioShock 2 GOG process,
reconstructed the correct compatdata root, and left the game intact. Both
trainer attempts still made a fresh `umu-run` exit with code 1. Copying the
same trainer beside the game executable produced the same result, refuting the
install-path hypothesis.

UniFiDeck bundles UMU 1.4.4. That version implements an explicit re-entry path:
`UMU_CONTAINER_NSENTER=1` makes the initial container expose a launcher
service, hashes `WINEPREFIX` into its app bus identity, and lets a later
invocation use `steam-runtime-launch-client` to run through that service with
`runinprefix`.

## Design

Trainer Relay prepares every configured Epic/GOG shortcut with exactly one
`UMU_CONTAINER_NSENTER=1` assignment. It uses the existing source-preserving
launch-option parser, asks for confirmation, persists the game configuration
disabled, writes the proposed AppDetails source, re-reads it, and enables only
after exact verification. A plain `gog:<id>` or `epic:<id>` source is expanded
to `UMU_CONTAINER_NSENTER=1 %command% <identity>`.

The process watcher accepts a real game only if the inherited flag is exactly
`1`. A matching game lacking it is `invalid_config` with diagnostic
`container_reentry_missing`; no sidecar starts. This prevents attaching to a
game that predates preparation.

The owned sidecar receives the validated compatdata root as `WINEPREFIX` and
`STEAM_COMPAT_DATA_PATH`, removes inherited
`STEAM_COMPAT_LAUNCHER_SERVICE`, forces `UMU_CONTAINER_NSENTER=1`, and assigns
`PROTON_VERB=runinprefix` last. It continues using structured argv and its own
process group. Trainer failure never changes or terminates the game.

Persistent diagnostics force `UMU_LOG=info`, not `1`. UMU's debug mode logs
the complete derived environment. INFO still exposes the decisive
`Re-entering container through bus` or `Failed to find bus name` messages.
Only bounded, sanitized output tails are journaled after process exit.

## Fail-closed behavior

- No selected trainer: no launch-option write.
- Unsafe or unparseable options: preparation blocked.
- Write or AppDetails mismatch: configuration remains disabled.
- Game missing re-entry flag: `invalid_config`, no trainer.
- UMU bus unavailable after five bounded probes: `invalid_config`, no trainer;
  game remains active. A trainer that actually spawned and exits early receives
  one automatic retry, then `failed`.
- Plugin unload or game exit: only the Trainer Relay-owned group is signaled.

## Acceptance

Local gates must prove source preservation, canonical assignment replacement,
plain identity conversion, process rejection without the flag, sidecar
environment ordering, bounded output capture, privacy, and packaging. Physical
GOG success requires the diagnostic sequence to show the same-prefix re-entry
message followed by `trainer_running`. Epic remains a separate gate.
