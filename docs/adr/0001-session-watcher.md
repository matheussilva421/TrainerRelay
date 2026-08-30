# ADR 0001: Session watcher boundary

## Status

Accepted

## Context

Trainer Relay must start an owned trainer sidecar for a supported UniFiDeck
shortcut without coupling trainer failure to the game. The game is launched
outside the plugin, so the plugin needs an independent way to identify the
correct Windows process and observe when that session ends.

## Decision

Use a one-second polling watcher over `/proc`. A candidate is valid only when
it matches the expected executable, the expected prefix anchor, and the
required launch environment. The watcher records the candidate identity as
the pair of PID and `/proc/<pid>/stat` start time; a changed start time is a
new process, even when Linux has reused the PID. Exactly one valid candidate
is required. No candidate produces `waiting_for_game`, while multiple
candidates fail closed as `ambiguous`.

The executable-like process name is required when acquiring a new session so
UMU, pressure-vessel, Python, Wine helpers, and other wrappers cannot inherit
their way into acceptance. Once acquired, the same PID/start-time pair may be
revalidated after `/proc/<pid>/comm` changes, because a Windows game can rename
its main Linux thread. That exception never applies to another PID or a
recycled start time, and the full executable, prefix, store, required
environment, and legacy-option checks remain mandatory.

The v1 compatibility boundary is the same Wine prefix plus UMU's explicit
same-prefix container re-entry service when using the bundled UMU 1.4.4. The
watcher does not alter the game process, its process group, or its launch
lifecycle.

The process scanner may observe `WINEPREFIX=<anchor>/pfx` because Proton
rewrites the variable for Windows descendants. A fresh `umu-run` instead
expects the compatdata anchor. The owned sidecar therefore receives
`WINEPREFIX=<anchor>`, `STEAM_COMPAT_DATA_PATH=<anchor>`, and finally
`PROTON_VERB=runinprefix`. It also omits the descendant's
`STEAM_COMPAT_CLIENT_INSTALL_PATH`, which UMU derives for the new invocation.
The scanner still accepts either anchor shape as evidence, but the launch
boundary never feeds transformed child values back into UMU.

Trainer Relay prepares supported shortcuts with `UMU_CONTAINER_NSENTER=1`
after explicit confirmation and AppDetails verification. The same flag is set
on the owned sidecar. UMU hashes the prefix into its launcher-service bus name,
then uses `steam-runtime-launch-client` to re-enter that service and applies
`runinprefix`. A matching game process without the flag is rejected as stale
configuration, because a sidecar cannot retroactively create the service for
an already-running game.

## Alternatives considered

### Launch-time coupling

Injecting the trainer into the game launch would provide direct ordering, but
would require changing UniFiDeck or Steam launch behavior and would make a
trainer failure part of game startup. It violates the independent-failure
boundary.

### Steam or UniFiDeck event integration

Listening to a product-specific event stream could reduce polling, but it
would still need `/proc` validation to establish the actual Windows process,
prefix, and stable PID identity. No stable event contract is part of this
release, so the additional dependency is not justified.

### PID-only discovery

A PID without its process start time can attach to an unrelated process after
PID reuse. It is not safe for a watcher that owns a trainer lifecycle.

### Fresh second container

Launching the trainer through a separate `umu-run` was safe for the game but
failed physically with exit code 1 in repeated GOG tests. UMU 1.4.4's explicit
launcher-service re-entry path is now required instead.

## Consequences

- The watcher is simple, testable with controlled `/proc` fixtures, and does
  not require a new integration with Steam or UniFiDeck.
- Detection can lag a launch or exit by at most one polling interval under
  normal conditions.
- Ambiguous or incomplete discovery never starts a trainer, preserving the
  fail-closed behavior.
- The plugin must retain the observed PID/start-time pair and revalidate the
  game session before retries and shutdown.
- Automatic retry is based on whether `running` was actually observed, not on
  whether the next one-second poll happened just before or after a fixed
  three-second timestamp.
- Future event integration may optimize wakeups, but it must preserve the
  same process, prefix, and ownership checks.
