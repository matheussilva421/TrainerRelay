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

## Forced-compat regression recovery and experimental.25 deployment

The user restored normal Mortal Shell launching by clearing Steam's **Force the
use of a specific Steam Play compatibility tool** checkbox on the UniFiDeck
shortcut. Read-only runtime verification then confirmed the healthy topology:
the Steam reaper and UniFiDeck/UMU descendants were all in
`app-steam-app2476768691-12654.scope`, used `DISPLAY=:1`, and Gamescope exposed
app2476768691 plus the 1280x800 Mortal Shell window. The regression was caused
by the diagnostic compatibility-tool API trial: restoring the GE-Proton11-6
name still left Force Compat enabled on the UniFiDeck launcher. Do not set a
compatibility tool on this shortcut again. UniFiDeck itself supplies GE-Proton
to UMU; wrapping the launcher with Steam Proton changes the launch context.

The black FLiNG surface was reduced independently. A disposable copied prefix
proved that `umu-run explorer.exe /desktop=TrainerRelay,800x680 <trainer>`
creates an opaque `TrainerRelay - Wine Desktop` parent containing a 780x640
`FLiNG Trainer` child. The transient service was stopped and the validated
temporary prefix `/home/deck/.cache/trainerrelay-diagnostics/mortal-shell-prefix.T1Zgi4`
was removed; the real UniFiDeck prefix was not copied back or modified by that
cleanup. Review of the current official CheatDeck source confirmed it only
uses Proton's `PROTON_REMOTE_DEBUG_CMD` path and has no non-Steam/Gamescope
window repair; its non-Steam issue #26 is closed as not planned. Those legacy
variables were not restored to the UniFiDeck shortcut.

TDD added an Epic-only Wine virtual-desktop launch. `OwnedTrainerRunner.spawn`
now accepts `virtual_desktop`; the watcher requests it only for identities with
the `epic:` scheme. GOG retains the exact direct `umu-run <trainer>` argv. The
version is `0.1.0-experimental.25`. Focused RED failed on the missing argument
and Epic routing, then passed after the minimum implementation. Validation:
69 runner/watcher tests pass; all 291 backend tests pass; 217 frontend tests in
30 files pass; lint, both TypeScript checks, Rollup build, and 7 packaging tests
pass. The normal `pnpm run check` wrapper could not verify/download pnpm 11.5.0
from the registry, so the already-installed pinned binaries were invoked
directly for the equivalent frontend gates.

Artifact `artifacts/TrainerRelay-v0.1.0-experimental.25.zip` has 34 entries,
774223 bytes and SHA-256
`94D8521318987F9C2546F3A1DD1DF7761F76DB6DFC5B80AE8BA7B95D92463BA5`.
PC and Deck hashes matched. Before installation, the exact `.22` folder and
settings were archived under
`/home/deck/Downloads/TrainerRelay-rollback-20260906-0921/` with SHA256SUMS.
Decky's authenticated `utilities/install_plugin`/confirm flow installed `.25`.
Journal records clean unload of `.22`, installation/load of `.25`; loader and
frontend report `.25`, and a read-only backend RPC returned schemaVersion1 with
the two configured games preserved. The game was closed during deployment.

Next physical gate: launch Mortal Shell normally from Steam with Force Compat
still unchecked. Verify the game remains on DISPLAY=:1, the new Epic trainer is
hosted in `TrainerRelay - Wine Desktop`, Gamescope offers a usable second
window, and the FLiNG controls visibly render. Do not claim fixed until the user
confirms the controls and at least one safe interaction path. If startup or the
trainer regresses, stop only Trainer Relay and restore the preserved `.22`
archive through a controlled Decky reinstall; do not alter UniFiDeck, Proton,
the real prefix, or the shortcut compatibility checkbox.
