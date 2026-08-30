# Trainer Relay Persistent Diagnostic Mode Design

## Purpose

Trainer Relay needs a persistent diagnostic mode that explains, on a physical
Steam Deck, why a configured trainer was or was not launched. The current
status RPC deliberately collapses unmatched process candidates into
`waiting_for_game`; that is safe for normal use but insufficient when a real
game process is rejected by one of the executable, environment, store, prefix,
or session checks.

Diagnostic mode must let a remote developer inspect sanitized events live in
CEF DevTools while the game is open. It must also let the Deck user create one
TXT report from the plugin without opening Konsole. Enabling diagnostics is a
persistent user choice: it remains enabled across plugin, Steam, and Deck
restarts until explicitly disabled.

## Scope

The feature adds:

- persistent global diagnostic settings;
- a bounded backend event journal;
- explicit process-candidate rejection reasons;
- cursor-based diagnostic RPCs;
- a persistent SharedJSContext-to-DevTools console bridge;
- a separate **Diagnostics** page in the plugin;
- one-click TXT export to `/home/deck/Downloads`;
- confirmed clearing of Trainer Relay diagnostic history.

The feature does not add remote shell access, HTTP log serving, telemetry,
automatic uploads, crash dumps, complete environment capture, trainer output
capture, or logs from UniFiDeck, Steam, Proton, Decky, or other plugins.

## User experience

Trainer Relay navigation gains a separate **Diagnostics** page. It contains:

- a persistent **Diagnostic mode** toggle;
- a conspicuous active/inactive indicator;
- current storage use and the 50 MB limit;
- any diagnostic-storage error;
- the latest 20 events, newest last;
- **Export TXT**;
- **Clear logs**, guarded by confirmation;
- the absolute path of the most recent successful export.

Enabling the toggle begins recording immediately and persists the setting.
Disabling it stops new diagnostic recording and DevTools forwarding but
preserves existing journal files until the user clears them. Clearing removes
only Trainer Relay diagnostic files; it does not disable diagnostics or modify
game configuration, trainers, prefixes, UniFiDeck, or Steam.

Export writes a timestamped file such as:

```text
/home/deck/Downloads/TrainerRelay-diagnostics-2026-08-30-074501.txt
```

An existing filename is never overwritten. A failed export leaves the journal
and any earlier export untouched.

## Configuration

Diagnostic settings are separate from `RelayConfigV1` so the per-game schema
remains stable. They are stored under the dedicated
`diagnostic_settings_v1` settings key:

```ts
interface DiagnosticSettingsV1 {
  schemaVersion: 1;
  enabled: boolean;
}
```

Missing, malformed, or future-version settings decode fail-closed to disabled.
The explicit enabled value survives plugin unload, Steam restart, and Deck
restart. Diagnostic journal files live in a plugin-owned `diagnostics`
directory below `DECKY_PLUGIN_SETTINGS_DIR` so they survive plugin reloads and
remain separate from exported reports.

## Event model

The public event shape is:

```ts
interface DiagnosticEvent {
  sequence: number;
  timestamp: string;
  identity?: LaunchIdentity;
  session?: { pid: number; startTime: number };
  category:
    | "config"
    | "games_map"
    | "process"
    | "umu"
    | "trainer"
    | "lifecycle";
  event: string;
  outcome: "info" | "accepted" | "rejected" | "warning" | "error";
  details: Record<string, string | number | boolean | null>;
}
```

The backend owns sequence allocation and UTC ISO-8601 timestamps. A persisted
generation plus sequence forms an opaque cursor. Clearing the journal advances
the generation, so a stale frontend cursor cannot silently skip events.

The recorder does not accept arbitrary dictionaries from callers. Each event
name has an allowlisted details schema with type and length limits. Keys whose
normalized names contain `token`, `secret`, `password`, `cookie`,
`authorization`, or `credential` are rejected defensively even if a future
caller adds them to the wrong schema.

Permitted technical values include:

- expected and observed executable paths;
- trainer path;
- expected and observed prefix paths;
- resolved `umu-run` and `PROTONPATH` paths;
- `GAMEID`, `STORE`, `WINEPREFIX`, and `PROTONPATH` values;
- PID and `/proc/<pid>/stat` start time;
- exit code, retry count, elapsed milliseconds, and bounded counts.

The recorder never accepts or derives:

- a complete environment;
- a complete command line;
- `PROTON_REMOTE_DEBUG_CMD` content;
- cookies, credentials, tokens, authorization headers, or secrets;
- trainer stdout or stderr;
- unrelated process paths or details.

## Process-discovery diagnostics

Normal discovery behavior remains fail-closed. Diagnostic mode observes the
same scan and cannot make a rejected candidate eligible.

The process evaluator returns a structured internal decision for each process,
rather than only candidate-or-none. Stable, safe reason codes include:

- `proc_entry_unreadable`;
- `pid_reused_during_scan`;
- `missing_required_environment`;
- `game_id_mismatch`;
- `store_mismatch`;
- `prefix_mismatch`;
- `executable_mismatch`;
- `legacy_settings_present`;
- `candidate_accepted`.

Logging every unrelated Linux process would be noisy and invasive. Detailed
candidate events are emitted only for a relevant process, defined as one that
matches at least one game anchor: expected executable basename, expected
`GAMEID`, expected store plus prefix, or the launch identity token. Unrelated
processes contribute only to bounded scan-summary counts.

Each scan emits or updates a `process_scan_summary` containing process count,
readable count, relevant-candidate count, accepted count, and counts grouped by
safe rejection code. Relevant candidates get one detailed accepted or rejected
event containing only allowed fields. Multiple accepted stable sessions remain
`ambiguous`; diagnostics describe the candidates but never choose one.

The existing status states remain unchanged. When no process is accepted,
`get_relay_status` may expose the strongest safe rejection reason as its
diagnostic code, while the diagnostic journal retains the complete sanitized
decision trail. This improves observability without changing launch behavior.

## Other runtime diagnostics

The journal records state-changing or decision-relevant events at these
boundaries:

- plugin load, unload, and diagnostic toggle;
- configuration decode and persist result;
- `games.map` read, parse, identity lookup, and expected executable;
- process scan summary and relevant candidate decisions;
- prefix derivation or override selection;
- bundled and PATH `umu-run` resolution result;
- trainer argv construction metadata without shell text or complete env;
- spawn success/failure and owned process-group ID;
- three-second running confirmation;
- early exit, automatic retry scheduling, manual retry, and exit code;
- game-session replacement or end;
- owned-group SIGTERM and bounded SIGKILL escalation.

Every game session is correlated by PID plus start time. Every event that can
be associated with a launch identity carries that identity.

## Storage and rotation

The journal uses newline-delimited JSON internally. It consists of five files
of at most 10 MiB each, for a hard total limit of 50 MiB:

```text
diagnostics.0.ndjson  # active
diagnostics.1.ndjson
diagnostics.2.ndjson
diagnostics.3.ndjson
diagnostics.4.ndjson  # oldest
```

Before an append would cross 10 MiB, rotation removes `diagnostics.4.ndjson`,
renames `.3` to `.4`, `.2` to `.3`, `.1` to `.2`, and `.0` to `.1`, then
creates a new `diagnostics.0.ndjson` active file.
Rotation uses plugin-owned paths only and atomic replace operations where the
filesystem permits them. Startup validates file names and ignores malformed
lines rather than failing the plugin.

Consecutive events with the same identity, session, category, event, outcome,
and details share one fingerprint. The first event is written immediately.
Repeats are counted in memory and emitted as a bounded `event_repeated` summary
when the fingerprint changes, after 30 seconds, before export, when diagnostics
are disabled, and on plugin unload. State transitions, different rejection
reasons, and errors are never collapsed together.

A disk or permission failure must not interrupt the watcher. The recorder
disables further disk writes for the current failure episode, exposes one
bounded `diagnostic_storage_unavailable` status in memory, and retries only on
an explicit settings change, clear, export, or plugin restart. It never logs
its own storage failure recursively.

## RPC contract

The backend adds typed methods:

```ts
interface DiagnosticSettingsResponse {
  settings: DiagnosticSettingsV1;
  bytesUsed: number;
  byteLimit: 52428800;
  eventCount: number;
  storageDiagnostic: string | null;
  lastExportPath: string | null;
}

interface DiagnosticEventsRequest {
  cursor?: string;
  limit?: number; // backend clamps to 1..200
}

interface DiagnosticEventsResponse {
  generation: number;
  nextCursor: string;
  cursorReset: boolean;
  events: DiagnosticEvent[];
}
```

RPC names:

- `get_diagnostic_settings`;
- `set_diagnostics_enabled`;
- `get_diagnostic_events`;
- `export_diagnostics`;
- `clear_diagnostics`.

All inputs and outputs are decoded conservatively. Export returns the created
absolute path and byte count. Clear returns refreshed settings/statistics and
a new cursor generation. RPC errors use bounded codes rather than raw Python
exceptions.

## Live DevTools bridge

While diagnostic mode is enabled, a frontend bridge in Trainer Relay's
persistent SharedJSContext polls `get_diagnostic_events` once per second with
its own cursor. Each new sanitized event is emitted as:

```text
[TrainerRelay:diagnostic] <event object>
```

The bridge starts when the plugin frontend loads, survives navigation away
from the Diagnostics page, and stops on plugin unload or when diagnostics are
disabled. Cursor reset after clearing or rotation is handled explicitly. RPC
failure uses bounded exponential backoff up to ten seconds and emits one
console warning per failure episode rather than flooding the console.

The Diagnostics page has an independent cursor and requests only the events it
needs. Opening or closing the page does not control backend recording.

## TXT export

Export first flushes any repeat summary, then streams journal files from oldest
to newest into a temporary file under `/home/deck/Downloads`. The final TXT has
a short header containing plugin version, export timestamp, diagnostic mode,
byte usage, and privacy notice. Each following line is human-readable and
machine-searchable:

```text
2026-08-30T10:45:01.123Z #412 process rejected executable_mismatch identity=gog:1482265668 pid=1234 ...
```

Details are serialized deterministically. The temporary output is atomically
renamed only after a successful close. Exports are not counted against the
50 MiB journal limit and are never deleted by **Clear logs**.

## Failure handling

- Malformed diagnostic settings disable recording.
- Malformed journal lines are skipped and counted in statistics.
- Journal failure never affects game discovery or trainer lifecycle.
- Live-poll failure never disables the backend recorder.
- Export failure preserves the journal and reports a safe error code.
- Clear failure reports a safe error and preserves files it could not remove.
- A stale cursor returns `cursorReset: true` and a current cursor.
- Disabled diagnostics return no new events but retain prior history.
- Plugin unload flushes repeat summaries before closing storage when possible.

## Testing strategy

Backend TDD covers:

- settings decode, persistence, and disabled default;
- event schema allowlists, value bounds, and prohibited-key rejection;
- five-file rotation and the exact 50 MiB ceiling;
- startup recovery from malformed lines and partial rotation state;
- repeat consolidation and flush boundaries;
- generation/cursor behavior, pagination, and stale cursor reset;
- export ordering, deterministic text, collision handling, atomic replacement,
  and preservation on failure;
- clear scope and confirmation-independent backend behavior;
- storage failure isolation from the watcher;
- fake `/proc` decisions for every rejection reason, PID reuse, relevant
  candidate filtering, aggregate summaries, unique acceptance, and ambiguity;
- UMU, spawn, retry, running, shutdown, and session-correlation events;
- proof that forbidden environment keys and raw command lines never enter
  journal or export output.

Frontend TDD covers:

- separate Diagnostics navigation;
- persistent toggle and fail-closed settings errors;
- last-20 event rendering and empty state;
- cursor polling, cursor reset, cleanup, and bounded backoff;
- SharedJSContext console forwarding with the required prefix;
- byte-use display and 50 MB limit;
- export success/error and returned path;
- confirmed clear and refreshed generation;
- no actionable diagnostics controls on unsupported or unavailable backends.

Integration tests use fake executables and a temporary `/proc` tree to prove
that a rejected real-game pattern produces the expected live event and TXT
line without exposing forbidden data. Existing backend, frontend, build, and
package gates remain mandatory.

## Release and physical acceptance

The feature is delivered as `v0.1.0-experimental.13`; stable promotion remains
forbidden. The Deck gate uses the current GOG BioShock 2 Remastered shortcut:

1. enable diagnostic mode and confirm it survives a plugin/Steam restart;
2. launch the game and observe live DevTools events without Konsole;
3. identify the exact candidate rejection or successful trainer transition;
4. export the TXT from the plugin and verify its path and contents;
5. clear logs and confirm only journal files are removed;
6. validate trainer launch, one instance, retry safety, and selective shutdown;
7. repeat the functional path with one Epic shortcut.

The temporary unauthenticated CEF LAN forward remains a development aid only
and must be stopped after validation. Diagnostic mode itself does not expose a
network listener.
