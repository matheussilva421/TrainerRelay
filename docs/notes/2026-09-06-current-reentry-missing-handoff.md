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

Preparation completed after game close confirmation: CEF SharedJSContext BB4C83EBC1E2031A227465B047DB217D rediscovered. RegisterForAppDetails confirmed exact expected launcher and options. Guarded SetAppLaunchOptions changed only app2476768691 from `epic:0055e45ce7654c55aade646467349e83` to `UMU_CONTAINER_NSENTER=1 %command% epic:0055e45ce7654c55aade646467349e83`. A subsequent AppDetails callback returned exact expected new value (`verified:true`), and subscription unregistered. This is runtime Steam readback, NOT proof of persistence across reboot or trainer functionality. No package installation, code change, test run, or game restart. Next user launches game normally; agent then checks environment, trainer process and real windows. Rollback via same Steam API to exact recorded original value if needed; do not write live VDF directly.

User confirmed game closed. Direct SSH `ps -p 24119,24126 -o pid,comm` returned no process rows (exit1), confirming those session PIDs ended. No shortcut changes applied yet. CEF target discovery request is pending in tool cell42; do not assume it failed or repeat a mutation. Local Steam API adapter confirms SetAppLaunchOptions and RegisterForAppDetails with strLaunchOptions/strShortcutExe readback, unregister on completion. Prefer this supported existing preparation route over writing shortcuts.vdf while Steam is running. Research note completed and read: running-lifecycle-research.md; it clarifies outer-process status limits but does not explain missing reentry in current session. No tests/production modifications at this checkpoint.
