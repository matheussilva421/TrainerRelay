# Trainer window diagnostic handoff

User confirmed Mortal Shell remained playable but the trainer window was not
visible. The .19 export proves a trainer process, not a visible usable window.

Implemented `0.1.0-experimental.21.windows.1`: automatic, read-only X11 metadata
snapshot on the first running-session poll at least 10 seconds after trainer
launch, only while persistent diagnostics are enabled. Runs off the event loop.
Stores `window_snapshot` in the existing journal/TXT and frontend event decoder.

Queries only the game process's DISPLAY with host xprop, finite property argv,
no shell, no window titles, no focus/mapping changes. Captures client window IDs,
active window, numeric PID/STEAM_GAME, WM_STATE and hidden atom. Up to eight
windows, 250 ms per command, two-second collection deadline; reports truncation.
Missing display/tool/client-list or query failure is diagnostic, never a reason
to terminate the trainer. It does not install xprop. The probe cannot prove no
trainer window exists on another display; missing EWMH support is reported as
unavailable. Window PID namespace differences also require care when correlating.

Files: new trainer_relay/window_probe.py and tests_backend/test_window_probe.py;
watcher integration/test, backend/frontend diagnostic schema, package/backend
version and packaging assertions. Existing launch environment is unchanged.

Validation: initial missing-module and missing-watcher-integration REDs observed;
focused tests green. Complete backend 261/261 before final extra export test;
final probe/export subset 4/4, frontend 217/217, packaging 7/7, Biome, both
TypeScript checks, compileall, Rollup and diff check passed. Real journal export
test confirms metadata persists to TXT. Physical Deck window query not yet tested.

Next: install TrainerRelay.zip with version .21.windows.1, enable persistent
diagnostics, start Mortal Shell and remain in-game for at least 15 seconds after
trainer launch, then export TXT (may close game first). Read window_snapshot
status before drawing conclusions about visibility/association. A missing xprop
or non-EWMH server requires a different read-only capture path. No Steam Input
radial work or speculative visibility fix is part of this change.

Git: changes are intended for feat/trainer-relay with commit/push in this turn;
local attachment directory excluded. No remote Deck installation performed.

## .windows.2: non-EWMH server fallback

The user supplied TrainerRelay-diagnostics-20260905-211431.txt. Header confirms
.21.windows.1 and enabled diagnostics. At 21:13:15.497 UTC trainer_running was
recorded, then at 21:13:22.488 window_snapshot returned display=:1,
probe_status=client_list_unavailable. Session ended at 21:14:20.321 and owned
group 25664 received SIGTERM at 21:14:20.384. This establishes failure of the
EWMH enumeration method, not absence of a window or the cause of invisibility.

Added xwininfo -root -tree fallback when _NET_CLIENT_LIST is absent. Parse only
leading window IDs, deduplicate them and consult the existing finite property
list. Titles are discarded, including ID-like text inside titles. Existing
two-second deadline, eight-window cap and no-shell/read-only contract remain.
Missing xwininfo reports unavailable rather than zero windows. Tree truncation
is flagged. Only the game's DISPLAY is inspected; other displays remain unknown.

RED reproduced client_list_unavailable instead of expected ok_tree; GREEN
confirmed fallback, ID parsing, privacy and unavailable-tool behavior. Complete
backend 264/264 and packaging 7/7 passed; compileall, Rollup and diff check passed.
No frontend behavior changed. Files changed: window_probe.py, its tests,
main.py/package.json/packaging version assertions and this handoff.

Artifact: TrainerRelay.zip, .21.windows.2, SHA-256
2BAF425B4B92475D87BA790818B58EB4802880FCD8FA2106BCDF025A7E7927FD.
Commit/push target feat/trainer-relay; no device install performed. Next capture:
install .windows.2, keep diagnostics enabled, launch Mortal Shell, wait at least
15 seconds after trainer launch and export TXT. Window invisibility remains
unresolved until actual window metadata can be obtained.
