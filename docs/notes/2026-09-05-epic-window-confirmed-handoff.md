# Mortal Shell trainer window confirmed

Source: TrainerRelay-diagnostics-20260905-212713.txt, supplied by user with
MVIMG_20260905_182443.jpg. Export version .21.windows.2, diagnostics enabled.

At 21:26:00.844 UTC trainer_spawned recorded owned group 28403. Container re-entry
confirmed after 2062 ms. At 21:26:04.499 trainer_running recorded after 3622 ms.
At 21:26:11.492 window_snapshot returned ok_tree on DISPLAY=:1, 26 tree windows,
truncated=true (eight inspected). Correlation with candidate events establishes:

- 0x2600003, PID 28345, WM_STATE Normal: Dungeonhaven-Win64 game process.
- 0x3c00001, PID 28489, WM_STATE Normal: Mortal Shell trainer process.
- 0x3c00002 also belongs to PID 28489.
- PID 28477 belongs to EOS overlay, not trainer.

This proves the trainer creates an X11 window on the game's display. Normal is
a WM_STATE property, not proof of visible pixels, focus, or Steam switchability.
STEAM_GAME was not captured as a numeric CARDINAL for either game or trainer;
that alone does not prove incorrect association. Active window is unknown and
the snapshot is partial. Session ended at 21:26:53.420.

Photo predates this launch (~18:24 local, versus 18:26 launch). It shows enabled
and a preparation prompt together. Source useRelayPageController.tsx sets that
message after selecting a trainer; it is not proof of a backend preparation
failure. Cheat controls awaiting a safe response is a separate UI symptom whose
RPC response is not established by this TXT.

No code change is justified yet for focus/association. Next user observation:
does Steam's in-game window list show the trainer as well as Mortal Shell?
If yes, inspect activation/focus behavior; if no, inspect Gamescope association
metadata and Steam window registration. Do not equate running/WM_STATE Normal
with visible or force-focus globally.

Changes: this handoff only. Checks: correlated exact PIDs and timeline, inspected
message source; no automated tests needed for documentation. Git target:
feat/trainer-relay, documentation commit/push. No new ZIP or device changes.
