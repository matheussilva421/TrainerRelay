# Current session: reentry preparation absent

Direct authenticated read-only SSH investigation, experimental.22 still installed.

- Current game PID24119 Dungeonhaven.ex/start64943 rejected with container_reentry_missing. Current process environ allowlist confirms UMU_CONTAINER_NSENTER absent, DISPLAY=:1, SteamGameId/SteamAppId=0.
- Steam shortcuts.vdf read-only parsed row app2476768691 Mortal Shell: Exe points to Unifideck launcher; LaunchOptions exactly epic:0055e45ce7654c55aade646467349e83. Preparation absent on disk too. No assertion yet about who removed it or when.
- Config remains enabled with expected Mortal Shell trainer path. No trainer/umu launch events after plugin_loaded at 10:37:35 UTC. Prior successful launch events belong to earlier boot/session, not current one.
- PID24251/window0x3400003 identified by diagnostics as EOSOverlayRenderer-Win64-Shipping.exe, CrBrowserMain. It is unmapped, not evidence of a trainer window.
- Therefore current failure is launch blocked by missing preparation, distinct from earlier observed trainer visibility failure. Do not deploy .24 as a proven cure or mutate the overlay.
- No code changes, deployment, process termination, window writes or automated tests. Existing pending test and attachments untouched.
- Next human checkpoint: user save and close game normally. Then reprepare exact shortcut through existing verified Steam API flow, preserving options; verify readback and launch fresh session. Capture actual trainer/window before further correction. Investigate persistence separately if preparation disappears again.
- Research agent01a0765b-0b06-7260-9ed1-6462ea2f42b2 assigned bounded lifecycle analysis, notified current evidence; output docs/notes/2026-09-06-running-lifecycle-research.md pending. Do not duplicate work.
- Temporary SSH key/service remain enabled by user authorization, cleanup required at completion; see temporary-ssh-key handoff. No credentials collected.
- Git: documentation-only commit/push follows. Objective remains incomplete.

## Game closed checkpoint

## Fresh launch after preparation

### Physical association trial: insufficient

User confirms trainer absent from selection. Direct trial verified exact trainer cmdline/prefix/PID25860 and stable start time, WM_NAME FLiNG Trainer, window0x3600001. STEAM_GAME absent before trial; xprop set to2476768691 succeeded and read back. Fresh CEF m_mapAppWindows still contained only [39845891] for app2476768691, not trainer window56623105. Thus setting STEAM_GAME on the already-created window alone is insufficient; do NOT install .24 as a validated fix. Rolled back only added STEAM_GAME after checking owner and value; readback not found confirms restoration. No cheats/focus/package changes. Next investigate Gamescope/Steam window registration beyond this property, using primary source and controlled runtime evidence; persistent implementation remains unproven.

User launched again. Direct SSH confirms game PID25706 Dungeonhaven.ex, shipping PID25712, trainer PID25860 Mortal Shell v1, all with UMU_CONTAINER_NSENTER=1 and DISPLAY=:1. Journal at 11:04:12 UTC records verified service and trainer_spawned, 11:04:15 reentry_confirmed, 11:04:16 trainer_running. This validates launch preparation for this session, NOT reboot persistence.

Actual X11 trainer window0x3600001 is titled FLiNG Trainer, PID25860, 780x640 at250,80; WM_STATE Normal, xwininfo Map State IsViewable, normal window type, no transient owner or NET_WM_STATE, STEAM_GAME absent. Game window0x2600003 remains separate. Unlike the prior unmapped EOS window, this is an identified trainer window. Steam switcher association, user-visible selection and cheat function remain unverified. No window properties/focus changed or cheats activated. Next check Steam switcher recognition/user selection; do not conflate X11 IsViewable with Gamescope foreground visibility. No automated tests executed.

Preparation completed after game close confirmation: CEF SharedJSContext BB4C83EBC1E2031A227465B047DB217D rediscovered. RegisterForAppDetails confirmed exact expected launcher and options. Guarded SetAppLaunchOptions changed only app2476768691 from `epic:0055e45ce7654c55aade646467349e83` to `UMU_CONTAINER_NSENTER=1 %command% epic:0055e45ce7654c55aade646467349e83`. A subsequent AppDetails callback returned exact expected new value (`verified:true`), and subscription unregistered. This is runtime Steam readback, NOT proof of persistence across reboot or trainer functionality. No package installation, code change, test run, or game restart. Next user launches game normally; agent then checks environment, trainer process and real windows. Rollback via same Steam API to exact recorded original value if needed; do not write live VDF directly.

User confirmed game closed. Direct SSH `ps -p 24119,24126 -o pid,comm` returned no process rows (exit1), confirming those session PIDs ended. No shortcut changes applied yet. CEF target discovery request is pending in tool cell42; do not assume it failed or repeat a mutation. Local Steam API adapter confirms SetAppLaunchOptions and RegisterForAppDetails with strLaunchOptions/strShortcutExe readback, unregister on completion. Prefer this supported existing preparation route over writing shortcuts.vdf while Steam is running. Research note completed and read: running-lifecycle-research.md; it clarifies outer-process status limits but does not explain missing reentry in current session. No tests/production modifications at this checkpoint.

## Black trainer and UniDeck restoration checkpoint

The manual Gamescope association trial produced a second Steam window, but the
user reported that selecting it showed a completely black FLiNG surface with no
controls. An X11 frame capture confirmed a black 1280x800 frame with only the
cursor. The live trainer window was the expected PID25860/window0x3600001; the
trial had set `STEAM_GAME=2476768691` and `_NET_WM_WINDOW_OPACITY=4294967295`.
Therefore window registration alone is not a functional fix, and the proposed
opacity/remap behavior must not be shipped.

Primary-source comparison found Valve Proton issue #9999 reporting the same
class of Decky/FLiNG accessibility regression on newer Proton 11, but this Deck
already has a physically functional BioShock 2 GOG trainer under GE-Proton11-6.
Store causality remains unproved; the Mortal Shell trainer build and its layered
window behavior are material differences.

A temporary A/B proposal changed only Steam app2476768691's forced compatibility
tool to `GE-Proton11-1`; it was never launched in that state. After the user
warned to preserve UniDeck, the setting was immediately restored to
`GE-Proton11-6-x86_64`. Live AppDetails and Steam config.vdf now both confirm
that exact restored tool, priority250. Live AppDetails also confirms the
critical shortcut launch option remains exactly
`UMU_CONTAINER_NSENTER=1 %command% epic:0055e45ce7654c55aade646467349e83`.
No prefix migration or file deletion occurred.

An attempted programmatic `RunGame` used the wrong launch context and created a
Mortal Shell process on DISPLAY=:0 rather than the prior Steam-controlled
DISPLAY=:1. Gamescope published only app769 and no Mortal Shell focus window.
That malformed attempt was terminated with SIGTERM only to its exact game PIDs;
the user-observed failure was caused by this launch context, not evidence of
prefix damage. A later corrected API launch still did not reproduce the normal
Steam UI context reliably and must not be used again. Current game/trainer PIDs
are stopped. Next human checkpoint: user presses Play normally on Mortal Shell
in the Steam library and leaves the launch running. Confirm DISPLAY=:1 and a
focusable game window before any trainer-only virtual-desktop experiment.

Temporary local diagnostic scripts were deleted and the unrelated unfinished
window-probe test draft was removed. The remote SSH key/service still require
cleanup only after the full objective is complete. No production implementation
or package is currently a validated fix.
